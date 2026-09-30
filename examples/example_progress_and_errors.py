"""A production-grade reference: step-by-step calls (not run()) with a custom progress
logger and explicit handling of both real failure modes this client can raise.

Use the step-by-step form instead of run() whenever you need more control than the
one-call shortcut gives you -- here, a custom on_progress callback that logs elapsed
time, not just the bare status.

The two exception types matter, and mean different things:
  - ForestSensAPIError: the *request itself* failed (bad auth, a quota exceeded, a
    validation error) -- nothing was necessarily started.
  - BatchFailedError (a subclass of the above): the request succeeded, but the batch it
    started later reached status "failed" -- exc.batch carries full step-level detail
    (each step's own error/log_tail), so you can tell which step broke and why.

Requires a real API key -- see Readme.md's "Getting an API key" section, then either
export FORESTSENS_GATEWAY_HOST/FORESTSENS_API_KEY or write them to
~/.forestsens/config.json (see Readme.md).
"""

import time

from forestsens import BatchFailedError, Client, ForestSensAPIError

INPUT_PATH = "path/to/your/file.tif"
PIPELINE_NAME = "Orthophoto (fast)"

client = Client()
start_time = time.monotonic()


def log_progress(batch) -> None:
    elapsed = time.monotonic() - start_time
    print(f"[{elapsed:6.1f}s] {batch}")  # Batch's own repr: "<id> (<status>)"


try:
    pipeline = client.find_pipeline(PIPELINE_NAME)
    upload_id = client.upload_files(INPUT_PATH)
    batch = client.create_batch(pipeline.id, [{"slot": "input", "upload_id": upload_id}])
    batch = client.wait_for_batch(batch.id, on_progress=log_progress)

except BatchFailedError as exc:
    print(f"\nBatch failed: {exc.message}")
    for step in exc.batch.get("steps") or []:
        if step.get("error"):
            print(f"  step {step['node_id']}: {step['error']}")
            for line in step.get("log_tail") or []:
                print(f"    | {line}")
    raise SystemExit(1)

except ForestSensAPIError as exc:
    # The request itself never got a batch running -- e.g. exc.code == "quota_exceeded"
    # or "validation_error". Nothing to inspect step-by-step; the message says it all.
    print(f"\nRequest failed ({exc.code}): {exc.message}")
    raise SystemExit(1)

print("\nBatch complete. Downloading artifacts...")
for path in client.download_artifacts(batch.id, dest_dir="downloads"):
    print(f"  {path}")
