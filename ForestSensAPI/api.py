import os
import json
import requests
import concurrent.futures
from urllib.parse import urlparse, urljoin
from typing import Optional, Dict, Any, Union
import logging

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

try:
    import oci
    from oci.object_storage.transfer.upload_manager import UploadManager
    from oci.object_storage.transfer.constants import MEBIBYTE
except ImportError:
    oci = None  # OCI is not available in this environment


class ForestSensAPI:
    def __init__(
        self,
        base_url: Optional[str] = None,
        apitoken: Optional[str] = None,
        oci_config: Optional[Dict[str, Any]] = None,
        api_config_path: Optional[str] = None,
        oci_config_path: Optional[str] = None,
        oci_profile: str = "DEFAULT"
    ):
        """
        Initialize the ForestSensAPI client with API and OCI configuration.
        """
        default_api_config_path = os.path.expanduser("~/.forestsens/config.json")
        config_path = api_config_path or default_api_config_path

        if os.path.isfile(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                base_url = config.get('base_url', base_url)
                apitoken = config.get('apitoken', apitoken)

        if not base_url or not apitoken:
            raise ValueError("base_url and apitoken must be provided either directly or via config file")

        self.base_url = base_url.rstrip('/')
        self.apitoken = apitoken
        self.headers = {
            'apitoken': self.apitoken,
            'Content-Type': 'application/json'
        }

        if oci:
            if isinstance(oci_config, dict):
                self.oci_config = oci_config
            else:
                config_file = oci_config_path or os.path.expanduser("~/.oci/config")
                if os.path.isfile(config_file):
                    self.oci_config = oci.config.from_file(file_location=config_file, profile_name=oci_profile)
                else:
                    raise ValueError("OCI config must be a dict or a valid file path")

            self.object_storage = oci.object_storage.ObjectStorageClient(self.oci_config)

    def get_all_batches(self, n: int = 20) -> Dict[str, Any]:
        """
        Retrieve batches from ForestSens.
        """
        try:
            response = requests.get(f"{self.base_url}/batches", headers=self.headers, params={'n': n})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get batches: {e}")
            raise

    def get_algorithms(self) -> Dict[str, Any]:
        """
        Retrieve available algorithms in ForestSens.
        """
        try:
            response = requests.get(f"{self.base_url}/algorithms", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get algorithms: {e}")
            raise

    def init_batch(self, name: Optional[str] = None, algorithm: int = 26) -> Dict[str, Any]:
        """
        Initialize a new batch with the specified parameters.
        """
        payload = {
            'batch_name': name,
            'algorithm': algorithm
        }
        try:
            response = requests.post(f"{self.base_url}/batches", headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to initialize batch: {e}")
            raise

    def start_batch(self, batch_id: Union[int, str]) -> Dict[str, Any]:
        """
        Start a previously initialized batch by its ID.
        """
        try:
            response = requests.post(f"{self.base_url}/batches/{batch_id}", headers=self.headers, json={})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to start batch {batch_id}: {e}")
            raise

    def get_batch_status(self, batch_id: Union[int, str]) -> Dict[str, Any]:
        """
        Get the status of a batch by its ID.
        """
        try:
            response = requests.get(f"{self.base_url}/batches/{batch_id}", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get status for batch {batch_id}: {e}")
            raise

    def get_results(self, batch_id: Union[int, str]) -> Dict[str, Any]:
        """
        Retrieve result metadata for a given batch.
        """
        try:
            response = requests.get(f"{self.base_url}/batches/{batch_id}/results", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get results for batch {batch_id}: {e}")
            raise

    def download_results(self, batch_id: Union[int, str], output_dir: str = "downloads") -> None:
        """
        Download result files for a given batch using the PAR URL.
        """
        results = self.get_results(batch_id)
        files = results.get("result_files", [])
        par_url = results.get("par_url")

        if not par_url:
            raise ValueError("No PAR URL found for this batch.")

        os.makedirs(output_dir, exist_ok=True)

        for file_info in files:
            filename = file_info["name"]
            file_url = urljoin(par_url, filename)
            local_path = os.path.join(output_dir, filename)

            logger.info(f"Downloading {filename}...")
            try:
                response = requests.get(file_url, stream=True)
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"Saved to {local_path}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to download {filename}: {e}")

    class SimpleProgress:
        """
        A simple progress tracker for file uploads.
        """
        def __init__(self, total_size: int, filename: str):
            self.total = total_size
            self.uploaded = 0
            self.filename = filename

        def __call__(self, bytes_uploaded: int):
            self.uploaded += bytes_uploaded
            percent = (self.uploaded / self.total) * 100
            print(f"\r{self.filename}: {percent:.2f}% uploaded", end='', flush=True)

        def done(self, success: bool = True):
            status = "OK" if success else "FAILED TO UPLOAD"
            print(f"\r{self.filename}: 100.00% uploaded - {status}")
    
    def upload_files(self, upload_url: str, local_path: str) -> None:
        """
        Uploads files to an OCI Object Storage bucket using a pre-authenticated request (PAR) URL.

        Args:
            upload_url (str): The PAR URL provided by the ForestSens API.
            local_path (str): Path to a file or directory to upload.
        """
        if not oci:
            raise ImportError("OCI SDK is not available. Please install `oci` to use this feature.")

        parsed = urlparse(upload_url)
        path_parts = parsed.path.strip('/').split('/')

        namespace = path_parts[1]
        bucket = path_parts[3]
        prefix = '/'.join(path_parts[5:]).rstrip('/') + '/'

        upload_manager = UploadManager(
            self.object_storage,
            allow_parallel_uploads=True,
            parallel_process_count=3
        )

        def upload_one(file_path: str, object_name: str) -> Dict[str, Any]:
            try:
                file_size = os.path.getsize(file_path)
                filename = os.path.basename(file_path)
                progress = self.SimpleProgress(file_size, filename)

                response = upload_manager.upload_file(
                    namespace,
                    bucket,
                    object_name,
                    file_path,
                    part_size=2 * MEBIBYTE,
                    progress_callback=progress
                )

                progress.done(success=True)
                return {
                    "file": filename,
                    "success": True,
                    "etag": response.headers.get("etag")
                }
            except Exception as e:
                filename = os.path.basename(file_path)
                progress = self.SimpleProgress(1, filename)
                progress.done(success=False)
                return {
                    "file": filename,
                    "success": False,
                    "error": str(e)
                }

        if os.path.isdir(local_path):
            all_files = [
                os.path.join(dp, f)
                for dp, _, filenames in os.walk(local_path)
                for f in filenames
            ]
            logger.info(f"Uploading {len(all_files)} files to '{namespace}/{bucket}/{prefix}'...")

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for fp in all_files:
                    rel = os.path.relpath(fp, local_path).replace("\\", "/")
                    oname = prefix + rel
                    futures.append(executor.submit(upload_one, fp, oname))

                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if not result.get("success", False):
                        logger.error(f"Failed to upload {result.get('file', 'Unknown')}: {result.get('error', 'No error message')}")
        else:
            filename = os.path.basename(local_path)
            object_name = prefix + filename
            result = upload_one(local_path, object_name)
            if result["success"]:
                logger.info(f"Uploaded {result['file']} (ETag: {result['etag']})")
            else:
                logger.error(f"Failed to upload {result['file']}: {result['error']}")

    def run_batch(self, algorithm: int, input_path: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs a complete batch process: initializes, uploads files, starts the batch, and checks status.

        Args:
            algorithm (int): Algorithm ID to use.
            input_path (str): Path to input file or directory.
            name (Optional[str]): Optional name for the batch.

        Returns:
            Dict[str, Any]: Batch metadata including ID, start response, and status.
        """
        logger.info("Initializing batch...")
        batch_info = self.init_batch(name=name, algorithm=algorithm)

        upload_url = batch_info["object_storage_url"]
        batch_id = batch_info["batch_id"]

        logger.info("Uploading files...")
        self.upload_files(upload_url, input_path)

        logger.info("Starting batch...")
        start_response = self.start_batch(batch_id)

        logger.info("Checking status...")
        status = self.get_batch_status(batch_id)

        return {
            "batch_id": batch_id,
            "start_response": start_response,
            "status": status
        }


