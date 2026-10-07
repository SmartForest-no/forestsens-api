"""Upload a folder of drone photos and submit a pipeline run against it -- either as one
batch (the whole folder as a single dataset) or as many batches (one per file). Submits
and returns immediately; it does not wait for completion or download results, so batches
in "many" mode run in parallel in the cloud instead of one after another.

Some pipelines take exactly one orthophoto per batch (e.g. "Individual tree crowns
(detectree2)"); others take a whole folder at once (e.g. a multi-step chain like
"Tree species detector"). This script doesn't try to guess which -- set MODE to match
whichever pipeline you're pointing it at, then run it.

Check on a submitted batch later with client.get_batch(batch_id) or
client.wait_for_batch(batch_id).

Requires a real API key -- see Readme.md's "Getting an API key" section, then either
export FORESTSENS_GATEWAY_HOST/FORESTSENS_API_KEY or write them to
~/.forestsens/config.json (see Readme.md).
"""

from pathlib import Path

from forestsens import Client

IMAGE_FOLDER = Path("path/to/your/photos")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff"}
PIPELINE_QUERY = "Tree species detector"  # name, part of a name, or short id -- see find_pipeline
MODE = "one"  # "one" = whole folder as a single batch, "many" = one batch per file

client = Client()

image_paths = sorted(
    p for p in IMAGE_FOLDER.iterdir()
    if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in IMAGE_EXTENSIONS
)
if not image_paths:
    raise SystemExit(f"No matching files found in {IMAGE_FOLDER}")

pipeline = client.find_pipeline(PIPELINE_QUERY)
print(f"Submitting {pipeline} in {MODE!r} mode against {len(image_paths)} file(s) in {IMAGE_FOLDER}...")

if MODE == "one":
    targets = [(IMAGE_FOLDER.name, image_paths)]  # one dataset, every file
elif MODE == "many":
    targets = [(p.stem, [p]) for p in image_paths]  # one dataset per file
else:
    raise SystemExit(f"MODE must be 'one' or 'many', got {MODE!r}")

batch_ids = []
for name, paths in targets:
    upload_id = client.upload_files(paths, name=name)
    batch = client.create_batch(pipeline.id, [{"slot": "input", "upload_id": upload_id}])
    batch_ids.append(batch.id)
    print(f"{name}: submitted batch {batch.id} ({batch.status})")

print(f"\nSubmitted {len(batch_ids)} batch(es). They're running in the cloud now:")
for batch_id in batch_ids:
    print(f"  {batch_id}")
