"""End-to-end example: upload a file, discover a pipeline, run a batch,
wait for it, download whatever artifacts it produces.

Requires a real API key -- ask a ForestSens administrator to issue one
(see Readme.md's "Getting an API key" section), then either export
FORESTSENS_GATEWAY_HOST/FORESTSENS_API_KEY or write them to
~/.forestsens/config.json (see Readme.md).
"""

from forestsens import BatchFailedError, Client

INPUT_PATH = "path/to/your/file.tif"  # a real local file
SENSE = "drone"  # or "point" -- see client.list_pipelines(sense=...)

client = Client()

print("Available pipelines:")
pipelines = client.list_pipelines(sense=SENSE)
for p in pipelines:
    print(f"  {p['id']}  {p['name']}")
if not pipelines:
    raise SystemExit(f"No pipelines found for sense={SENSE!r} -- nothing to run.")
pipeline = pipelines[0]

print(f"\nUploading {INPUT_PATH}...")
upload_id = client.upload_files([INPUT_PATH])
print(f"Upload complete: {upload_id}")

print(f"\nStarting batch against pipeline {pipeline['id']} ({pipeline['name']})...")
# A pipeline's graph (pipeline["graph"]) encodes its expected input slot
# names -- "input" is a common default but isn't guaranteed for every
# pipeline. Check pipeline["graph"] if this raises a validation error.
batch = client.create_batch(pipeline["id"], [{"slot": "input", "upload_id": upload_id}])
print(f"Batch created: {batch['id']} (status={batch['status']})")

print("\nWaiting for batch to finish...")
try:
    batch = client.wait_for_batch(batch["id"], poll_interval=5)
except BatchFailedError as exc:
    print(f"Batch failed: {exc.message}")
    for step in exc.batch.get("steps") or []:
        if step.get("error"):
            print(f"  step {step['node_id']}: {step['error']}")
    raise SystemExit(1)

print("Batch done. Downloading artifacts...")
paths = client.download_artifacts(batch["id"], dest_dir="downloads")
for path in paths:
    print(f"  {path}")
