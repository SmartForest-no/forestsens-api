# ForestSensAPI

ForestSensAPI is a Python client for interacting with Smartforests [ForestSens](https://forestsens.com) platform API utilizing the OCI SDK for efficient file uploads. It allows users to manage batch jobs, upload files, retrieve results, and monitor processing status through a simple and extensible interface.

Currently under development with our partners, the API will be available for public use in the near future. For questions or contributions, please contact us at [forestsens@nibio.no](mailto:forestsens@nibio.no).

## 🚀 Features

- Initialize and start batch jobs
- Upload files to OCI Object Storage using PAR URLs
- Retrieve and download batch results
- Monitor batch status
- Supports configuration via JSON and OCI config files

## 📦 Installation

```bash
pip install -r requirements.txt
```
## ⚙️ Configuration

### API Configuration

ForestSensAPI requires a `base_url` and an `apitoken` for authentication. These can be provided directly when initializing the client, or via a configuration file.

**Recommended:** Create a config file at `~/.forestsens/config.json`:

```json
{
    "base_url": "https://forestsens.api.url",
    "apitoken": "your_api_token"
}
```

- If you do not provide `base_url` and `apitoken` directly to the client, the library will look for this file by default.
- You can override the config file location by passing the `api_config_path` parameter.

### OCI Configuration (Optional, for Object Storage)

To enable file uploads to Oracle Cloud Infrastructure (OCI) Object Storage, you must provide OCI credentials. There are two ways to do this:

1. **Using a config file (default):**
   - Place your OCI config at `~/.oci/config` (standard OCI CLI format).
   - Optionally, specify a different path with the `oci_config_path` parameter.
   - You can also select a profile (default is `"DEFAULT"`) using the `oci_profile` parameter.

2. **Using a Python dictionary:**
   - Pass a dictionary with the required OCI credentials to the `oci_config` parameter.

**Example OCI config file (`~/.oci/config`):**
```
[DEFAULT]
user=ocid1.user.oc1..exampleuniqueID
fingerprint=20:3b:97:...
key_file=/path/to/oci_api_key.pem
tenancy=ocid1.tenancy.oc1..exampleuniqueID
region=eu-frankfurt-1
```


## 🧪 Usage Example

### Initialize from Config File

```python
from ForestSensAPI import ForestSensAPI

# Initialize the API client (reads from ~/.forestsens/config.json)
api = ForestSensAPI()
```

### Initialize with Config Passed Directly

```python
from ForestSensAPI import ForestSensAPI

# Initialize with API credentials passed directly
api = ForestSensAPI(
    base_url="https://forestsens.api.url",
    apitoken="your_api_token"
)
```

### Initialize with OCI Configuration

```python
from ForestSensAPI import ForestSensAPI

# Initialize with API and OCI credentials
api = ForestSensAPI(
    base_url="https://forestsens.api.url",
    apitoken="your_api_token",
    oci_config_path="~/.oci/config",        # or omit to use default
    oci_profile="DEFAULT"                    # or specify a different profile
)

# Or, pass OCI config as a dictionary
oci_config = {
    "user": "ocid1.user.oc1..exampleuniqueID",
    "fingerprint": "20:3b:97:...",
    "key_file": "/path/to/oci_api_key.pem",
    "tenancy": "ocid1.tenancy.oc1..exampleuniqueID",
    "region": "eu-frankfurt-1"
}

api = ForestSensAPI(
    base_url="https://forestsens.api.url",
    apitoken="your_api_token",
    oci_config=oci_config
)
```

### Run a Batch

```python
# Run a batch
batch = api.run_batch(
    algorithm=26,
    input_path="path/to/data",
    name="MyBatch"
)
print(batch["status"])

# Download results
api.download_results(batch_id=batch["id"], output_dir="results")
```

