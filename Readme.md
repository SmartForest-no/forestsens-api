# forestsens

Python client for the [ForestSens](https://forestsens.com) API. **v2 -- a real rewrite, not
compatible with anything earlier**: the platform moved off the old Oracle APEX API onto a new
OCI-hosted one (different auth, different batch/upload shapes), so this client's entire surface
changed to match. Earlier versions of this repo were never published as a package, so there's
nothing to pin against -- this is effectively the first real release.

v2 deliberately covers the core workflow only: **upload a dataset, run a batch, download the
results.** Managing API keys, browsing detections/segments/tree-inventory tables, and other
admin-area functionality aren't included yet -- see the [ForestSens
roadmap](https://github.com/SmartForest-no/ForestSens/blob/main/ROADMAP.md) for what's planned
next.

> Note: this package's import name (`forestsens`) is unrelated to the identically-named internal
> package in the main [ForestSens platform repo](https://github.com/SmartForest-no/ForestSens) --
> that one is never published anywhere (local install only for the backend service itself), so
> there's no real collision, just a shared name worth knowing about.

## Install

```bash
pip install forestsens
```

## Configuration

You need a **gateway host** (where the ForestSens API lives) and an **API key** (`fs_...`) --
mint a key via the web UI's Account page (self-service, requires a real login first; this client
only ever *uses* an existing key, it can't create one for you).

Three ways to provide them, in priority order:

1. **Directly to `Client()`:**
   ```python
   from forestsens import Client
   client = Client(gateway_host="xxxx.apigateway.eu-frankfurt-1.oci.customer-oci.com", api_key="fs_...")
   ```
2. **Environment variables:**
   ```bash
   export FORESTSENS_GATEWAY_HOST=xxxx.apigateway.eu-frankfurt-1.oci.customer-oci.com
   export FORESTSENS_API_KEY=fs_...
   ```
3. **A config file** at `~/.forestsens/config.json`:
   ```json
   { "gateway_host": "xxxx.apigateway.eu-frankfurt-1.oci.customer-oci.com", "api_key": "fs_..." }
   ```

## Usage

```python
from forestsens import Client, BatchFailedError

client = Client()

# Discover a pipeline to run.
pipelines = client.list_pipelines(sense="drone")
pipeline = pipelines[0]

# Upload one or more local files -- handles small files (direct upload)
# and large files (resumable chunked upload) the same way.
upload_id = client.upload_files(["orthophoto.tif"])

# Run a batch and wait for it to finish.
batch = client.create_batch(pipeline["id"], [{"slot": "input", "upload_id": upload_id}])
try:
    batch = client.wait_for_batch(batch["id"])
except BatchFailedError as exc:
    print(f"Batch failed: {exc.message}")
    raise

# Download whatever artifacts the batch produced.
paths = client.download_artifacts(batch["id"], dest_dir="downloads")
```

See [`examples/example_batch.py`](examples/example_batch.py) for the full runnable version, and
[`docs/forestsens_api_reference.md`](docs/forestsens_api_reference.md) for the underlying REST API
this client wraps.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```
