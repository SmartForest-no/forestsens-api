# ForestSens API reference (subset used by this client)

This describes the real REST endpoints the `forestsens` package wraps -- the subset needed for
upload/batch/download. It is not the full ForestSens API (which also covers tenant/API-key
administration, typed result tables, and more) -- see the [Readme](../Readme.md)'s "Full API
reference" section for the complete, always-current OpenAPI spec.

Every response is wrapped in an envelope: `{"data": ..., "meta": {...}, "error": null | {"code",
"message", "details"}}`. This client raises `forestsens.ForestSensAPIError` whenever `error` is
non-null.

## Authentication

All requests carry `X-Api-Key: fs_...` and go through the dedicated `/v1-key/{path*}` route (not
`/v1/{path*}`, which requires a browser-issued JWT this client never has). An API key is issued by a ForestSens administrator -- see the
[Readme](../Readme.md)'s "Getting an API key" section.

## `GET /v1/pipelines?sense=<sense_code>`

Lists available pipelines. Each has an `id` (pass to `POST /v1/batches` as `pipeline_id`), a
`name`, and a `graph` describing its expected input slots.

## `POST /v1/uploads`

Creates a dataset record. Body: `{"files": [{"filename": str, "mime_type": str|null}], "name":
str|null}`. Response includes each file's `upload_url` -- a pre-authenticated Object Storage URL,
valid only while the upload's `status` is `"uploading"`.

- **Small files** (≤16 MiB): `PUT` the raw file bytes directly to `upload_url`. No auth header --
  the URL is self-authenticating.
- **Large files** (>16 MiB): backend-mediated resumable multipart, since pre-authenticated URLs
  don't support real multipart operations:
  - `POST /v1/uploads/{upload_id}/files/{file_id}/multipart/start` -- returns
    `{"multipart_upload_id", "chunk_size_bytes", "parts": [...]}`; `parts` lists chunks already
    landed (for resuming an interrupted upload).
  - `PUT /v1/uploads/{upload_id}/files/{file_id}/multipart/parts/{n}` -- raw chunk bytes, requires
    `X-Api-Key`.
  - `POST /v1/uploads/{upload_id}/files/{file_id}/multipart/commit` -- finalizes the file (the
    server re-lists parts from storage itself, never trusts a client-submitted list).

## `POST /v1/uploads/{upload_id}/complete`

Marks the upload ready for use as a batch input. Must be called after every file has landed.

## `POST /v1/batches`

Starts a pipeline run. Body: `{"pipeline_id": str, "inputs": [{"slot": str, "upload_id": str}]}`.
Returns a batch record with `status: "queued"`.

## `GET /v1/batches/{batch_id}`

Poll this for status (`queued` -> `running` -> `done`|`failed`), per-step detail (`steps[]`, each
with `status`/`error`/`log_tail`), and a `results` summary of what's available once done.

## `GET /v1/batches/{batch_id}/artifacts?cursor=`

Cursor-paginated list of output files. Each artifact carries a live `download_url` (a fresh
pre-authenticated Object Storage URL, `Accept-Ranges: bytes`) -- no separate "generate a download
link" call needed.
