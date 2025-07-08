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

Create a config file at ~/.forestsens/config.json:

```json
{
    "base_url": "https://forestsens.api.url",
    "apitoken": "your_api_token"
}
```
Ensure your OCI config is available at ~/.oci/config or passed as a dictionary.

## 🧪 Usage Example

```python
from ForestSensAPI import ForestSensAPI

# Initialize the API client
api = ForestSensAPI()

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

