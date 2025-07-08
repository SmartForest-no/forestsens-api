import os
import json
from ForestSensAPI import ForestSensAPI

# ----------------------------
# Configuration
# ----------------------------
#INPUT_PATH = "data/input.tif"      # Path to your input file
INPUT_PATH = None                   # Path to your input file
ALGORITHM_ID = 26                   # Algorithm ID to use
BATCH_NAME = "Test Batch"           # Name of the batch
DOWNLOAD_RESULTS = False            # Set to True to download results

# ----------------------------
# Initialize API
# ----------------------------
api = ForestSensAPI()

# ----------------------------
# Run a batch
# ----------------------------
if INPUT_PATH and ALGORITHM_ID:
    print(f"Running batch with algorithm {ALGORITHM_ID} on {INPUT_PATH}")
    api.run_batch(input_path=INPUT_PATH, algorithm=ALGORITHM_ID, name=BATCH_NAME)

# ----------------------------
# Get latest batches
# ----------------------------
batch_list = api.get_all_batches(3)

print("\nLatest batches:")
print(json.dumps(batch_list, indent=2))

# ----------------------------
# Get last batch
# ----------------------------
batch_list = api.get_all_batches(3)
if not batch_list:
    print("No batches found.")
else:
    latest_batch = batch_list[0]
    batch_id = latest_batch['batch_id']

    print("\nLast batch info:")
    print(json.dumps(latest_batch, indent=2))

    # ----------------------------
    # Get batch status
    # ----------------------------
    status = api.get_batch_status(batch_id)
    print("\nBatch status:")
    print(json.dumps(status, indent=2))

    # ----------------------------
    # Get results
    # ----------------------------
    results = api.get_results(batch_id=batch_id)
    print("\nResults for last batch (batch_id="+str(batch_id)+"):")
    print(json.dumps(results, indent=2))

    # ----------------------------
    # Download results
    # ----------------------------
    if DOWNLOAD_RESULTS:
        print(f"\nDownloading results to 'downloads/'...")
        api.download_results(batch_id=batch_id, output_dir="downloads")
        print("Download complete.")
