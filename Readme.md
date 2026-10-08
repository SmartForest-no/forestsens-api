> **Not yet active.** This README (and the `v2.2.0` tag) describe a client for ForestSens' new,
> OCI-hosted API, which is not yet the production system. If you're integrating with ForestSens
> today, use the [`v1.0.0` release](https://github.com/SmartForest-no/forestsens-api/releases/tag/v1.0.0)
> instead -- the client for the current, active Oracle APEX-based system.

# forestsens

A Python client for the [ForestSens](https://forestsens.com) API -- a forestry data-processing
service. You upload a dataset (drone imagery, LiDAR point clouds), run it through a processing
pipeline (orthomosaic generation, tree detection, segmentation, wheel-rut assessment, and more),
and retrieve the results.

Using an AI coding agent to write your integration? See [`llms.txt`](llms.txt) -- a terse,
structured reference built for that instead of this narrative README.

## Install

```bash
pip install git+https://github.com/SmartForest-no/forestsens-api.git@v2.2.0
```

(Or `@main` for the latest commit on the default branch, if you want to track development rather
than pin a release.)

## Quick start

```python
from forestsens import Client

client = Client()  # reads FORESTSENS_GATEWAY_HOST / FORESTSENS_API_KEY -- see Configuration below

pipeline = client.find_pipeline("Orthophoto (fast)")  # see client.list_pipelines() for the full catalog
paths = client.run(pipeline, "path/to/your/photos", dest_dir="downloads", on_progress=print)
```

That's the whole workflow: upload a file (or a whole folder of them -- non-recursive, top-level
files only), run a pipeline, wait for it, download whatever it produced. `on_progress=print` logs
each status change (`queued` -> `running` -> `complete`) so a long GPU job doesn't look hung.

<details>
<summary>What <code>run()</code> does under the hood, for when you need more control</summary>

```python
from forestsens import BatchFailedError

pipeline = client.find_pipeline("Orthophoto (fast)")

# Upload your data. Large files (>=16 MiB) are chunked and resumed automatically -- same call
# either way, whether you pass one file, a folder, or a list of either.
upload_id = client.upload_files("path/to/your/photos", name="my dataset")

# Start the pipeline and wait for it to finish. "input" is the right slot name for every
# pipeline in the current catalog -- run() assumes it too, by default.
batch = client.create_batch(pipeline.id, [{"slot": "input", "upload_id": upload_id}])
try:
    batch = client.wait_for_batch(batch.id, on_progress=print)
except BatchFailedError as exc:
    print(f"Batch failed: {exc.message}")
    raise

# Download whatever the batch produced.
paths = client.download_artifacts(batch.id, dest_dir="downloads")
```

Use this form instead of `run()` when a pipeline needs more than one input slot, or you want to
inspect or act on the batch mid-flight (cancel it, check intermediate step status, etc.).
</details>

See [`examples/example_batch.py`](examples/example_batch.py) for a full runnable version of both
forms. Three more worked examples -- a whole folder of drone photos, a LiDAR/point-cloud pipeline,
and production-grade progress/error handling -- are indexed in
[`docs/examples.md`](docs/examples.md). The sections below cover how to get a key, configure the
client, and handle errors.

## Getting an API key

An API key (`fs_...`) is what authenticates every call this client makes -- a long-lived
credential that only ends when revoked. Generate one yourself from your **Account** page in the
ForestSens web app. A **ForestSens administrator** can also issue one for you, if you'd rather ask
than self-service.

The key is shown **exactly once** at creation -- save it immediately; there's no way to retrieve
it again later (only its prefix, for identification, stays visible afterward). If it's ever lost or
compromised, revoke it and issue a new one.

## Configuration

Every call needs the **gateway host** (where the API lives) and your **API key**. Pick whichever
of these is convenient -- checked in this order if more than one is set:

```python
# 1. Directly to Client()
from forestsens import Client
client = Client(
    gateway_host="mvym2zsszqqwnjdr6ypbzgq7yq.apigateway.eu-frankfurt-1.oci.customer-oci.com",
    api_key="fs_...",
)
```

```bash
# 2. Environment variables
export FORESTSENS_GATEWAY_HOST=mvym2zsszqqwnjdr6ypbzgq7yq.apigateway.eu-frankfurt-1.oci.customer-oci.com
export FORESTSENS_API_KEY=fs_...
```
```python
client = Client()  # picks up the env vars above
```

```json
// 3. ~/.forestsens/config.json (or pass config_path=... to Client())
{
  "gateway_host": "mvym2zsszqqwnjdr6ypbzgq7yq.apigateway.eu-frankfurt-1.oci.customer-oci.com",
  "api_key": "fs_..."
}
```

## Reference

| Method | Returns | Does |
|---|---|---|
| `list_pipelines(sens=None)` | `list[Pipeline]` | Lists available pipelines, optionally filtered by sens (`"drone"`, `"point"`, ...). `Pipeline` is a real `dict` (`pipeline["id"]` works) with a friendly `.id`/`.name`/`.description` and a clean repr -- printing one shows just its name, not the full internal graph/id payload. |
| `find_pipeline(name, sens=None)` | `Pipeline` | Looks up a single pipeline by its exact display name (e.g. copied from the web UI) instead of filtering/indexing `list_pipelines()` yourself. Raises `LookupError` (with the real available names) if there's no match, or more than one. |
| `upload_files(paths, name=None)` | `str` (upload id) | Uploads a file, a folder (its top-level files, not recursive), or a list mixing either, as a single dataset. |
| `create_batch(pipeline_id, inputs)` | `Batch` | Starts a pipeline run. `inputs` is `[{"slot": str, "upload_id": str}, ...]`. `Batch` is the same friendly-`dict` treatment as `Pipeline` (`.id`/`.status`, `batch["status"]` both work). |
| `get_batch(batch_id)` | `Batch` | Fetches a batch's current status/detail. |
| `list_batches(status=None, upload_id=None, created_by=None, sort="created", direction="desc", limit=20, cursor=None)` | `(list[Batch], next_cursor)` | One page of batches, newest first by default. No pipeline filter -- use `iter_batches` for that. |
| `iter_batches(pipeline=None, **list_batches kwargs)` | generator of `Batch` | Pages through every batch automatically; `pipeline` (a `Pipeline` or bare id) filters to just that pipeline's batches, client-side. Stops paging as soon as you stop iterating -- safe to use with `itertools.islice(..., N)` for "the last N". |
| `wait_for_batch(batch_id, poll_interval=5.0, timeout=None, on_progress=None)` | `Batch` | Polls until the batch reaches `"complete"` or `"failed"`. Raises `BatchFailedError` on failure. `on_progress`, if given, is called once per status change -- pass `on_progress=print` for a one-line log. |
| `run(pipeline, paths, dest_dir, slot="input", name=None, poll_interval=5.0, timeout=None, on_progress=None)` | `list[str]` (local paths) | The common single-input case in one call: upload -> create a batch -> wait -> download. `pipeline` can be a `Pipeline` or a bare id string. |
| `download_artifacts(batch_id, dest_dir)` | `list[str]` (local paths) | Downloads every artifact the batch produced. |

### Errors

Every call can raise `forestsens.ForestSensAPIError(status, code, message, details)` -- `code` is
a machine-readable string (`"unauthenticated"`, `"not_found"`, `"validation_error"`,
`"quota_exceeded"`, ...), not just an HTTP status. `forestsens.BatchFailedError` is a subclass
raised specifically by `wait_for_batch` when the batch itself reaches `status="failed"` (as
opposed to a transport/request error) -- it carries the full batch dict (`exc.batch`), including
each step's own `error`/`log_tail`, so you can inspect what actually went wrong without a second
call.

## What this client doesn't cover

This wraps a subset of the real ForestSens REST API -- upload, batch, and artifact download.
API-key management and browsing typed result tables (detections, segments, tree inventory) aren't
included yet. You can always reach those directly over HTTP with your API key (`X-Api-Key` header,
against the same gateway host prefixed with `/v1-key/` instead of `/v1/`) even though this package
doesn't wrap them.

Interactive docs (`/docs`, `/openapi.json`) aren't publicly exposed on this deployment -- ask a
ForestSens administrator for the full API reference if you need it.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT -- see [LICENSE](LICENSE).

<details>
<summary>What changed from the old (pre-2.0.0) package</summary>

Earlier versions of this repository targeted a different, older ForestSens API and were never
actually published as an installable package -- there's nothing real to upgrade from, but if
you're coming from that code, here's what's different:

| | Old | `2.0.0` |
|---|---|---|
| Auth | `apitoken` header, a single flat token | `X-Api-Key` header, issued per-key by an admin, individually revocable |
| Batch submission | `{"batch_name": str, "algorithm": <numeric id>}` | `{"pipeline_id": str, "inputs": [{"slot": str, "upload_id": str}]}` |
| Upload mechanism | Real OCI SDK (`oci` package), used directly against Object Storage | No `oci` dependency at all -- plain HTTP PUT to a pre-authenticated URL (small files) or a backend-mediated resumable multipart protocol (large files) |
| Endpoints | Flat, unversioned (`/batches`, `/algorithms`) | Versioned (`/v1/...`), envelope-wrapped responses |
| Response shape | Raw JSON, `response.raise_for_status()` | `{"data", "meta", "error"}` envelope, parsed into `ForestSensAPIError` on failure |
| Package name / import | `forestsensapi` | `forestsens` |

If you have code written against the old API, it needs a real rewrite, not a patch -- the auth
mechanism, the request/response shapes, and the upload mechanism all changed.
</details>
