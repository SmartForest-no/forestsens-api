"""Run a LiDAR/point-cloud pipeline instead of a drone-imagery one.

The catalog has two sens families with genuinely different input formats: "drone"
pipelines take .jpg imagery, "point" pipelines take .las/.laz point clouds. This example
is the point-cloud side -- list_pipelines(sens="point") only returns pipelines that
accept that format, so there's no need to check format compatibility by hand.

Requires a real API key -- see Readme.md's "Getting an API key" section, then either
export FORESTSENS_GATEWAY_HOST/FORESTSENS_API_KEY or write them to
~/.forestsens/config.json (see Readme.md).
"""

from forestsens import Client

POINT_CLOUD_DIR = "path/to/your/point_clouds"  # a real local folder of .las/.laz files

client = Client()

print("Point-cloud pipelines available:")
for pipeline in client.list_pipelines(sens="point"):
    print(f"  {pipeline}")

pipeline = client.find_pipeline("SegmentAnyTree", sens="point")
print(f"\nRunning {pipeline} against every point cloud in {POINT_CLOUD_DIR}...")

paths = client.run(
    pipeline,
    POINT_CLOUD_DIR,
    dest_dir="downloads",
    name="my point cloud survey",
    on_progress=print,
)

print("Done. Downloaded:")
for path in paths:
    print(f"  {path}")
