# tests/test_api.py
import unittest
from unittest.mock import patch, MagicMock
from ForestSensAPI import ForestSensAPI
import requests


class TestForestSensAPI(unittest.TestCase):
    def setUp(self):
        self.api = ForestSensAPI()

    @patch("requests.get")
    def test_get_all_batches(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"batches": []}
        result = self.api.get_all_batches()
        self.assertIn("batches", result)

    @patch("requests.get")
    def test_get_algorithms(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"algorithms": []}
        result = self.api.get_algorithms()
        self.assertIn("algorithms", result)

    @patch("requests.get")
    def test_get_batch_status(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"status": "running"}
        result = self.api.get_batch_status(batch_id=123)
        self.assertEqual(result["status"], "running")

    @patch("requests.post")
    def test_init_batch(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"batch_id": 1}
        result = self.api.init_batch(name="test")
        self.assertEqual(result["batch_id"], 1)

    @patch("requests.post")
    def test_start_batch(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"started": True}
        result = self.api.start_batch(batch_id=1)
        self.assertTrue(result["started"])

    @patch("requests.get")
    def test_get_results(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"result_files": [], "par_url": "https://dummy.url"}
        result = self.api.get_results(batch_id=1)
        self.assertIn("result_files", result)
        self.assertIn("par_url", result)

    @patch("requests.get")
    def test_get_all_batches_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("API error")
        with self.assertRaises(requests.exceptions.RequestException):
            self.api.get_all_batches()


if __name__ == '__main__':
    unittest.main()
