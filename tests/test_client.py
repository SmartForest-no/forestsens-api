"""Mocks the HTTP layer (unittest.mock.patch), same testing philosophy
this repo's own tests already used before the rewrite -- pytest style,
pointed at the real v2 envelope/endpoint shapes instead of the legacy
API's.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from forestsens import BatchFailedError, Client, ForestSensAPIError


def make_client(**kwargs) -> Client:
    return Client(gateway_host="example.apigateway.oci.customer-oci.com", api_key="fs_test", **kwargs)


def envelope_response(data=None, error=None, status=200, pagination=None):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    body = {"data": data, "meta": {"request_id": "r1", "pagination": pagination}, "error": error}
    resp.json.return_value = body
    resp.content = json.dumps(body).encode()
    return resp


# -- config resolution -------------------------------------------------


def test_client_requires_gateway_host_and_api_key(tmp_path):
    empty_config = tmp_path / "config.json"
    empty_config.write_text("{}")
    with pytest.raises(ValueError):
        Client(config_path=empty_config)


def test_client_reads_config_file(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"gateway_host": "cfg.example.com", "api_key": "fs_cfg"}))
    client = Client(config_path=config)
    assert client.gateway_host == "cfg.example.com"
    assert client.api_key == "fs_cfg"


def test_explicit_args_override_config_file(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"gateway_host": "cfg.example.com", "api_key": "fs_cfg"}))
    client = Client(gateway_host="explicit.example.com", api_key="fs_explicit", config_path=config)
    assert client.gateway_host == "explicit.example.com"
    assert client.api_key == "fs_explicit"


def test_env_vars_override_config_file(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"gateway_host": "cfg.example.com", "api_key": "fs_cfg"}))
    monkeypatch.setenv("FORESTSENS_GATEWAY_HOST", "env.example.com")
    monkeypatch.setenv("FORESTSENS_API_KEY", "fs_env")
    client = Client(config_path=config)
    assert client.gateway_host == "env.example.com"
    assert client.api_key == "fs_env"


# -- URL building / auth header -------------------------------------------------


def test_calls_go_through_v1_key_route_with_api_key_header():
    client = make_client()
    with patch("requests.Session.request") as mock_request:
        mock_request.return_value = envelope_response(data=[{"id": "p1"}])
        client.list_pipelines()
    called_url = mock_request.call_args.args[1]
    called_headers = mock_request.call_args.kwargs["headers"]
    assert called_url == "https://example.apigateway.oci.customer-oci.com/v1-key/pipelines"
    assert called_headers["X-Api-Key"] == "fs_test"


# -- error handling -------------------------------------------------


def test_raises_forestsens_api_error_on_envelope_error():
    client = make_client()
    with patch("requests.Session.request") as mock_request:
        mock_request.return_value = envelope_response(
            error={"code": "not_found", "message": "no such batch", "details": []}, status=404
        )
        with pytest.raises(ForestSensAPIError) as exc_info:
            client.get_batch("nonexistent")
    assert exc_info.value.code == "not_found"
    assert exc_info.value.status == 404


# -- uploads -------------------------------------------------


def test_upload_files_small_file_uses_put_to_par_no_auth_header(tmp_path):
    client = make_client()
    local_file = tmp_path / "flight1.jpg"
    local_file.write_bytes(b"tiny file contents")

    created = {
        "id": "upload-1",
        "files": [{"id": "file-1", "filename": "flight1.jpg", "upload_url": "https://par.example/flight1.jpg"}],
    }

    with patch("requests.Session.request") as mock_request, patch("requests.put") as mock_put:
        mock_request.side_effect = [
            envelope_response(data=created),  # POST /v1/uploads
            envelope_response(data={"id": "upload-1", "status": "ready"}),  # POST .../complete
        ]
        mock_put.return_value = MagicMock(ok=True, status_code=200)

        upload_id = client.upload_files([local_file])

    assert upload_id == "upload-1"
    mock_put.assert_called_once()
    assert mock_put.call_args.args[0] == "https://par.example/flight1.jpg"
    # PAR PUT never carries our own auth -- the URL is self-authenticating.
    assert "headers" not in mock_put.call_args.kwargs


def test_upload_files_large_file_uses_resumable_multipart(tmp_path, monkeypatch):
    client = make_client()
    monkeypatch.setattr("forestsens.client.MULTIPART_CHUNK_SIZE_BYTES", 10)
    local_file = tmp_path / "big.tif"
    local_file.write_bytes(b"0123456789" * 3)  # 30 bytes -> 3 chunks of 10

    created = {
        "id": "upload-1",
        "files": [{"id": "file-1", "filename": "big.tif", "upload_url": "https://par.example/big.tif"}],
    }
    started = {
        "multipart_upload_id": "mp-1",
        "chunk_size_bytes": 10,
        "parts": [{"part_number": 1, "etag": "e1", "size_bytes": 10}],  # part 1 already landed
    }

    with patch("requests.Session.request") as mock_request, patch(
        "requests.Session.put"
    ) as mock_session_put:
        mock_request.side_effect = [
            envelope_response(data=created),  # POST /v1/uploads
            envelope_response(data=started),  # POST .../multipart/start
            envelope_response(data={"id": "upload-1", "status": "ready"}),  # POST .../multipart/commit is via _post too
            envelope_response(data={"id": "upload-1", "status": "ready"}),  # POST .../complete
        ]
        mock_session_put.return_value = envelope_response(
            data={"part_number": 2, "etag": "e2", "size_bytes": 10}
        )

        client.upload_files([local_file])

    # Only parts 2 and 3 uploaded -- part 1 was already reported as done.
    assert mock_session_put.call_count == 2


# -- batches -------------------------------------------------


def test_create_batch_posts_pipeline_and_inputs():
    client = make_client()
    with patch("requests.Session.request") as mock_request:
        mock_request.return_value = envelope_response(data={"id": "batch-1", "status": "queued"})
        batch = client.create_batch("pipeline-1", [{"slot": "input", "upload_id": "upload-1"}])
    assert batch["id"] == "batch-1"
    sent_json = mock_request.call_args.kwargs["json"]
    assert sent_json == {"pipeline_id": "pipeline-1", "inputs": [{"slot": "input", "upload_id": "upload-1"}]}


def test_wait_for_batch_polls_until_done():
    client = make_client()
    with patch("requests.Session.request") as mock_request, patch("time.sleep") as mock_sleep:
        mock_request.side_effect = [
            envelope_response(data={"id": "batch-1", "status": "running"}),
            envelope_response(data={"id": "batch-1", "status": "running"}),
            envelope_response(data={"id": "batch-1", "status": "done"}),
        ]
        batch = client.wait_for_batch("batch-1", poll_interval=0.01)
    assert batch["status"] == "done"
    assert mock_sleep.call_count == 2


def test_wait_for_batch_raises_on_failure():
    client = make_client()
    with patch("requests.Session.request") as mock_request:
        mock_request.return_value = envelope_response(
            data={"id": "batch-1", "status": "failed", "error_message": "step 2 blew up", "steps": []}
        )
        with pytest.raises(BatchFailedError) as exc_info:
            client.wait_for_batch("batch-1", poll_interval=0.01)
    assert exc_info.value.message == "step 2 blew up"
    assert exc_info.value.batch["status"] == "failed"


# -- downloads -------------------------------------------------


def test_download_artifacts_streams_each_artifact_to_dest_dir(tmp_path):
    client = make_client()
    artifacts = [
        {"id": "artifact-1234abcd", "output_type": "results_zip", "format": "zip", "download_url": "https://par.example/a1"},
    ]

    with patch("requests.Session.get") as mock_session_get, patch("requests.get") as mock_get:
        mock_session_get.return_value = envelope_response(data=artifacts, pagination={"next_cursor": None})
        download_resp = MagicMock()
        download_resp.__enter__.return_value = download_resp
        download_resp.raise_for_status.return_value = None
        download_resp.iter_content.return_value = [b"file", b"bytes"]
        mock_get.return_value = download_resp

        written = client.download_artifacts("batch-1", tmp_path)

    assert len(written) == 1
    local_path = tmp_path / "results_zip_artifact.zip"
    assert local_path.exists()
    assert local_path.read_bytes() == b"filebytes"
