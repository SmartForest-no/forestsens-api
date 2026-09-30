"""Upload a whole folder of drone photos and run a multi-step pipeline against it.

Unlike example_batch.py's single-file, single-node "Orthophoto (fast)" run, this uses
"Tree species detector" -- a real multi-node chain (orthomosaic -> tile -> detect) -- to
show that the folder-upload/run() shortcut works the same way regardless of how many
steps the pipeline actually has under the hood.

Requires a real API key -- see Readme.md's "Getting an API key" section, then either
export FORESTSENS_GATEWAY_HOST/FORESTSENS_API_KEY or write them to
~/.forestsens/config.json (see Readme.md).
"""

from forestsens import Client

PHOTOS_DIR = "path/to/your/photos"  # a real local folder of .jpg drone photos

client = Client()

pipeline = client.find_pipeline("Tree species detector")
print(f"Running {pipeline} against every photo in {PHOTOS_DIR}...")

# upload_files (called internally by run()) uploads every top-level file in PHOTOS_DIR --
# not recursive, and it skips dotfiles. Point it at a flat folder of photos from one flight.
paths = client.run(
    pipeline,
    PHOTOS_DIR,
    dest_dir="downloads",
    name="my drone survey",
    on_progress=print,  # logs each status change: queued -> running -> complete
)

print("Done. Downloaded:")
for path in paths:
    print(f"  {path}")
