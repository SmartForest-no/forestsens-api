"""The ForestSens API client -- one class, deliberately kept flat and
simple (v1 scope is upload/batch/download only, see the repo's own
Readme.md). Mirrors two things from the real frontend, which is the
verified reference implementation for how this API actually behaves in
practice (not just its OpenAPI shape): the request/error envelope
handling in forestsens/src/api/client.ts, and the upload orchestration
in forestsens/src/lib/uploadFiles.ts (small-file PUT-to-PAR vs
large-file backend-mediated chunked multipart, resume-aware).
"""

from __future__ import annotations

import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Callable

import requests

from .errors import BatchFailedError, ForestSensAPIError

# Must match forestsens/services/uploads.py's MULTIPART_CHUNK_SIZE_BYTES --
# kept in sync by hand (same as the frontend does), not derived at
# runtime. 16 MiB: real margin under the API Gateway's confirmed 20MB
# request-body ceiling, which every multipart chunk has to pass through
# since pre-authenticated requests don't support multipart at all.
MULTIPART_CHUNK_SIZE_BYTES = 16 * 1024 * 1024

MAX_ATTEMPTS = 3
DEFAULT_CONFIG_PATH = Path.home() / ".forestsens" / "config.json"


def _load_config_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open() as f:
        return json.load(f)


class Client:
    def __init__(
        self,
        gateway_host: str | None = None,
        api_key: str | None = None,
        config_path: str | os.PathLike[str] | None = None,
    ) -> None:
        """Config priority: explicit args > environment variables
        (FORESTSENS_GATEWAY_HOST / FORESTSENS_API_KEY) > config file
        (~/.forestsens/config.json, or config_path if given) --
        {"gateway_host": "...", "api_key": "..."}. An API key can only be
        minted via the web UI's self-service Account page (there's no
        bootstrap path that starts from nothing but a key) -- this
        client only ever consumes an existing one.
        """
        file_config = _load_config_file(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)

        self.gateway_host = (
            gateway_host
            or os.environ.get("FORESTSENS_GATEWAY_HOST")
            or file_config.get("gateway_host")
        )
        self.api_key = (
            api_key or os.environ.get("FORESTSENS_API_KEY") or file_config.get("api_key")
        )
        if not self.gateway_host or not self.api_key:
            raise ValueError(
                "gateway_host and api_key must be provided directly, via "
                "FORESTSENS_GATEWAY_HOST/FORESTSENS_API_KEY, or in "
                f"{config_path or DEFAULT_CONFIG_PATH}"
            )
        self.gateway_host = self.gateway_host.rstrip("/")
        self._session = requests.Session()

    # -- low-level request core -------------------------------------------------

    def _url(self, path: str) -> str:
        # Every real API call (as opposed to a pre-authenticated Object
        # Storage URL) goes through /v1-key/*, the one Gateway route that
        # doesn't require a browser JWT -- see infra/api_gateway.tf.
        # Callers of this client only ever pass the plain /v1/... path;
        # this is the one place that prefix gets rewritten.
        assert path.startswith("/v1/"), f"expected a /v1/... path, got {path!r}"
        return f"https://{self.gateway_host}/v1-key{path[len('/v1'):]}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        headers["X-Api-Key"] = self.api_key
        resp = self._session.request(method, self._url(path), headers=headers, **kwargs)
        try:
            body = resp.json()
        except ValueError:
            body = None
        error = body.get("error") if isinstance(body, dict) else None
        if not resp.ok or error:
            if error:
                raise ForestSensAPIError(
                    resp.status_code, error["code"], error["message"], error.get("details")
                )
            raise ForestSensAPIError(resp.status_code, "unknown_error", f"HTTP {resp.status_code}")
        return body["data"] if isinstance(body, dict) and "data" in body else body

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json_body: Any = None) -> Any:
        return self._request("POST", path, json=json_body if json_body is not None else {})

    # -- uploads ------------------------------------------------------------

    def upload_files(self, paths: list[str | os.PathLike[str]], name: str | None = None) -> str:
        """Creates a dataset from one or more local files and returns its
        upload_id. Sequential per file, on purpose -- simpler than the
        frontend's bounded-concurrency pool; a script-driven client
        doesn't need the same UX polish a browser progress bar does.
        Each file (or, for a large file, each chunk) is retried up to
        MAX_ATTEMPTS times with a short backoff before giving up.
        """
        paths = [Path(p) for p in paths]
        created = self._post(
            "/v1/uploads",
            {
                "files": [
                    {"filename": p.name, "mime_type": mimetypes.guess_type(p.name)[0]}
                    for p in paths
                ],
                "name": name,
            },
        )
        upload_id = created["id"]
        file_by_name = {p.name: p for p in paths}

        for file_out in created["files"]:
            local_path = file_by_name[file_out["filename"]]
            size = local_path.stat().st_size
            if size <= MULTIPART_CHUNK_SIZE_BYTES:
                self._upload_small_file(file_out["upload_url"], local_path)
            else:
                self._upload_large_file(upload_id, file_out["id"], local_path, size)

        self._post(f"/v1/uploads/{upload_id}/complete", {})
        return upload_id

    def _with_retry(self, attempt_fn: Callable[[], None]) -> None:
        last_err: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                attempt_fn()
                return
            except Exception as err:  # noqa: BLE001 -- deliberately broad, see retry loop
                last_err = err
                if attempt < MAX_ATTEMPTS:
                    time.sleep(0.5 * attempt)
        assert last_err is not None
        raise last_err

    def _upload_small_file(self, upload_url: str, local_path: Path) -> None:
        # Pre-authenticated Object Storage URL -- no X-Api-Key here, the
        # URL itself is self-authenticating (same reasoning
        # putRawWithProgress in the frontend documents).
        def attempt() -> None:
            with local_path.open("rb") as f:
                resp = requests.put(upload_url, data=f)
            if not resp.ok:
                raise ForestSensAPIError(resp.status_code, "upload_failed", f"HTTP {resp.status_code}")

        self._with_retry(attempt)

    def _upload_large_file(self, upload_id: str, file_id: str, local_path: Path, size: int) -> None:
        base = f"/v1/uploads/{upload_id}/files/{file_id}/multipart"
        started = self._post(f"{base}/start")
        already_done = {p["part_number"] for p in started["parts"]}
        chunk_size = started["chunk_size_bytes"]
        total_parts = -(-size // chunk_size)  # ceil division

        with local_path.open("rb") as f:
            for part_number in range(1, total_parts + 1):
                start = (part_number - 1) * chunk_size
                length = min(chunk_size, size - start)
                if part_number in already_done:
                    continue  # real resume: skip what storage already has

                def attempt(part_number: int = part_number, start: int = start, length: int = length) -> None:
                    f.seek(start)
                    chunk = f.read(length)
                    resp = self._session.put(
                        self._url(f"{base}/parts/{part_number}"),
                        headers={"X-Api-Key": self.api_key},
                        data=chunk,
                    )
                    body = resp.json() if resp.content else None
                    if not resp.ok or (isinstance(body, dict) and body.get("error")):
                        err = (body or {}).get("error") or {}
                        raise ForestSensAPIError(
                            resp.status_code,
                            err.get("code", "unknown_error"),
                            err.get("message", f"HTTP {resp.status_code}"),
                        )

                self._with_retry(attempt)

        self._post(f"{base}/commit")

    # -- pipelines ------------------------------------------------------------

    def list_pipelines(self, sense: str | None = None) -> list[dict[str, Any]]:
        params = {"sense": sense} if sense else None
        return self._get("/v1/pipelines", params=params)

    # -- batches ------------------------------------------------------------

    def create_batch(self, pipeline_id: str, inputs: list[dict[str, Any]]) -> dict[str, Any]:
        """inputs: [{"slot": str, "upload_id": str}, ...] -- see
        list_pipelines()'s returned graph for a given pipeline's expected
        slot names.
        """
        return self._post("/v1/batches", {"pipeline_id": pipeline_id, "inputs": inputs})

    def get_batch(self, batch_id: str) -> dict[str, Any]:
        return self._get(f"/v1/batches/{batch_id}")

    def wait_for_batch(
        self, batch_id: str, poll_interval: float = 5.0, timeout: float | None = None
    ) -> dict[str, Any]:
        """Polls until the batch reaches status "done" or "failed".
        Raises BatchFailedError (carrying the full batch dict, including
        per-step errors/log tails) on failure -- the "one call to get to
        a finished batch" convenience this kind of client should have.
        """
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            batch = self.get_batch(batch_id)
            if batch["status"] == "done":
                return batch
            if batch["status"] == "failed":
                raise BatchFailedError(batch)
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(f"batch {batch_id} did not finish within {timeout}s")
            time.sleep(poll_interval)

    # -- downloads ------------------------------------------------------------

    def download_artifacts(self, batch_id: str, dest_dir: str | os.PathLike[str]) -> list[str]:
        """Downloads every artifact produced by a batch into dest_dir,
        returns the local paths written. Each artifact's download_url is
        already a live pre-authenticated Object Storage URL (minted
        fresh per call) -- no separate "generate a download link" step.
        ArtifactOut carries no filename, so one is derived from
        output_type + format + a short id fragment.
        """
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        cursor = None
        while True:
            params = {"cursor": cursor} if cursor else None
            page = self._request_page(f"/v1/batches/{batch_id}/artifacts", params)
            for artifact in page["items"]:
                # ArtifactOut carries no filename or file extension --
                # `format` (e.g. "cog_tiff", "pmtiles", "laz") is used
                # as-is rather than guessed-mapped to a conventional
                # extension, so this never silently mislabels a file.
                local_path = dest / f"{artifact['output_type']}_{artifact['id'][:8]}.{artifact['format']}"
                self._download_one(artifact["download_url"], local_path)
                written.append(str(local_path))
            cursor = page["next_cursor"]
            if not cursor:
                break
        return written

    def _request_page(self, path: str, params: dict[str, Any] | None) -> dict[str, Any]:
        headers = {"X-Api-Key": self.api_key}
        resp = self._session.get(self._url(path), headers=headers, params=params)
        body = resp.json()
        if not resp.ok or body.get("error"):
            err = body.get("error") or {}
            raise ForestSensAPIError(
                resp.status_code, err.get("code", "unknown_error"), err.get("message", "")
            )
        return {
            "items": body["data"],
            "next_cursor": (body.get("meta", {}).get("pagination") or {}).get("next_cursor"),
        }

    def _download_one(self, url: str, local_path: Path) -> None:
        with requests.get(url, stream=True) as resp:
            resp.raise_for_status()
            with local_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
