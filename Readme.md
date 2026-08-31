# forestsens

A Python client for the [ForestSens](https://forestsens.com) API -- a forestry data-processing
service. You upload a dataset (drone imagery, LiDAR point clouds), run it through a processing
pipeline (orthomosaic generation, tree detection, segmentation, wheel-rut assessment, and more),
and retrieve the results. This package wraps the real HTTP API behind a small set of Python calls:
upload a dataset, start a batch, wait for it, download whatever it produced.

## Requirements

- Python >= 3.9
- A ForestSens account and an **API key**. This package doesn't create an account or a key for
  you -- see [Getting an API key](#getting-an-api-key) below.

## Install

Not yet published to PyPI. Install directly from a tagged release:

```bash
pip install git+https://github.com/SmartForest-no/forestsens-api.git@v2.0.0
```

(Or `@main` for the latest commit on the default branch, if you want to track development rather
than pin a release.)

## Getting an API key

An API key (`fs_...`) is what authenticates every call this client makes -- it's a long-lived
ForestSens-native credential (never expires on its own, only revocation ends it), unrelated to
the short-lived OIDC access tokens the web app's own browser login uses internally. You can't
mint one yourself from a blank slate -- ask a **ForestSens administrator** in your organization
to issue one for you; they can acquire one directly from the ForestSens app.

If you want to automate issuing keys (e.g. as part of your own onboarding pipeline), an admin can
also do it as a plain REST call, authenticating with their own existing API key rather than
dealing with OAuth at all:

```bash
curl -X POST "https://mvym2zsszqqwnjdr6ypbzgq7yq.apigateway.eu-frankfurt-1.oci.customer-oci.com/v1/principals/<principal-id-of-the-key's-future-owner>/api-keys" \
  -H "X-Api-Key: <your-own-admin-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"name": "my external client"}'
```

The response's `data.key` is shown **exactly once** -- save it immediately; there's no way to
retrieve it again later (only its prefix, for identification, stays visible afterward). If it's
ever lost or compromised, revoke it and issue a new one.

## Configuration

Every call needs two things: the **gateway host** (where the API lives) and your **API key**.
Provide them however's convenient -- checked in this order:

1. **Directly to `Client()`:**
   ```python
   from forestsens import Client
   client = Client(
       gateway_host="mvym2zsszqqwnjdr6ypbzgq7yq.apigateway.eu-frankfurt-1.oci.customer-oci.com",
       api_key="fs_...",
   )
   ```
2. **Environment variables:**
   ```bash
   export FORESTSENS_GATEWAY_HOST=mvym2zsszqqwnjdr6ypbzgq7yq.apigateway.eu-frankfurt-1.oci.customer-oci.com
   export FORESTSENS_API_KEY=fs_...
   ```
   ```python
   client = Client()
   ```
3. **A config file** at `~/.forestsens/config.json`:
   ```json
   {
     "gateway_host": "mvym2zsszqqwnjdr6ypbzgq7yq.apigateway.eu-frankfurt-1.oci.customer-oci.com",
     "api_key": "fs_..."
   }
   ```

## Usage

```python
from forestsens import Client, BatchFailedError

client = Client()

# Discover a pipeline to run. Each has an id, a name, and a graph describing
# its expected input slot names.
pipelines = client.list_pipelines(sense="drone")  # or "point" for LiDAR pipelines
pipeline = pipelines[0]

# Upload one or more local files. Small files upload directly; large files
# (>=16 MiB) are chunked and resumed transparently -- same call either way.
upload_id = client.upload_files(["orthophoto.tif"], name="my dataset")

# Start a batch and wait for it to finish. "input" is a common slot name but
# isn't guaranteed for every pipeline -- check pipeline["graph"] if this
# raises a validation error.
batch = client.create_batch(pipeline["id"], [{"slot": "input", "upload_id": upload_id}])
try:
    batch = client.wait_for_batch(batch["id"])
except BatchFailedError as exc:
    print(f"Batch failed: {exc.message}")
    for step in exc.batch.get("steps") or []:
        if step.get("error"):
            print(f"  step {step['node_id']}: {step['error']}")
    raise

# Download whatever artifacts the batch produced.
paths = client.download_artifacts(batch["id"], dest_dir="downloads")
```

See [`examples/example_batch.py`](examples/example_batch.py) for the full runnable version.

### Reference

| Method | Returns | Does |
|---|---|---|
| `list_pipelines(sense=None)` | `list[dict]` | Lists available pipelines, optionally filtered by sense (`"drone"`, `"point"`, ...). |
| `upload_files(paths, name=None)` | `str` (upload id) | Uploads one or more local files as a single dataset. |
| `create_batch(pipeline_id, inputs)` | `dict` (batch) | Starts a pipeline run. `inputs` is `[{"slot": str, "upload_id": str}, ...]`. |
| `get_batch(batch_id)` | `dict` (batch) | Fetches a batch's current status/detail. |
| `wait_for_batch(batch_id, poll_interval=5.0, timeout=None)` | `dict` (batch) | Polls until the batch reaches `"complete"` or `"failed"`. Raises `BatchFailedError` on failure. |
| `download_artifacts(batch_id, dest_dir)` | `list[str]` (local paths) | Downloads every artifact the batch produced. |

### Errors

Every call can raise `forestsens.ForestSensAPIError(status, code, message, details)` -- `code` is
a machine-readable string (`"unauthenticated"`, `"not_found"`, `"validation_error"`,
`"quota_exceeded"`, ...), not just an HTTP status. `forestsens.BatchFailedError` is a subclass
raised specifically by `wait_for_batch` when the batch itself reaches `status="failed"` (as
opposed to a transport/request error) -- it carries the full batch dict (`exc.batch`), including
each step's own `error`/`log_tail`, so you can inspect what actually went wrong without a second
call.

## Full API reference

This client wraps a subset of the real ForestSens REST API -- upload, batch, and artifact
download. The complete, always-current API surface is published as an OpenAPI document:

- **Interactive docs**: https://mvym2zsszqqwnjdr6ypbzgq7yq.apigateway.eu-frankfurt-1.oci.customer-oci.com/docs
- **Raw OpenAPI spec**: https://mvym2zsszqqwnjdr6ypbzgq7yq.apigateway.eu-frankfurt-1.oci.customer-oci.com/openapi.json

This client deliberately doesn't cover the whole surface yet -- API-key management and browsing
typed result tables (detections, segments, tree inventory) aren't included. You can always reach
those directly over HTTP with your API key (`X-Api-Key` header, against the same gateway host
prefixed with `/v1-key/` instead of `/v1/`) even though this package doesn't wrap them yet.

## What changed from the old package

Earlier versions of this repository (pre-`2.0.0`) targeted a different, older ForestSens API and
were never actually published as an installable package -- there's nothing real to upgrade from,
but if you're coming from that code, here's what's different:

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

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT -- see [LICENSE](LICENSE).
