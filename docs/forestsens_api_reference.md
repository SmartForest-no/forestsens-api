# ForestSens API Reference

This document describes the REST API endpoints provided by the ForestSens API, as defined in the OpenAPI 3.0 specification.

---

## Endpoints

### `GET /algorithms`

**Description:** List all available algorithms.

**Headers:**
- `apitoken` (string): Your API token.

**Response:**
- `200 OK`: Returns the list of algorithms.

---

### `GET /batches`

**Description:** List all batches.

**Headers:**
- `apitoken` (string): Your API token.

**Request Body:**
```json
{
  "n": "string"
}
```
- `n` (string): Optional parameter to limit the number of batches returned.

**Response:**
- `200 OK`: Returns the list of batches.

---

### `POST /batches`

**Description:** Create a new batch.

**Headers:**
- `apitoken` (string): Your API token.

**Request Body:**
```json
{
  "algorithm": "string",
  "batch_name": "string"
}
```

**Response:**
- `201 Created`: Successfully created the batch.

---

### `GET /batches/{batchid}`

**Description:** Retrieve a specific batch.

**Path Parameters:**
- `batchid` (string): ID of the batch.

**Headers:**
- `apitoken` (string): Your API token.

**Response:**
- `200 OK`: Returns the batch record.

---

### `POST /batches/{batchid}`

**Description:** Start a previously initialized batch.

**Path Parameters:**
- `batchid` (string): ID of the batch.

**Headers:**
- `apitoken` (string): Your API token.

**Response:**
- `201 Created`: Starts the batch process.

---

### `GET /batches/{batchid}/results`

**Description:** Retrieve results for a specific batch.

**Path Parameters:**
- `batchid` (string): ID of the batch.

**Headers:**
- `apitoken` (string): Your API token.

**Response:**
- `200 OK`: Returns the batch results.
