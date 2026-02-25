# BRSR PDF Parser — API Routes

This document lists the backend API routes and usage examples for wiring the frontend.

## Authentication

- **POST /auth/signup**
  - Auth: none
  - Body: JSON `{ "email": "user@example.com", "password": "Secret123", "name": "Display Name" }`
  - Success: `{"access_token":"<token>","token_type":"bearer","user":{"id":"<id>","email":"...","name":"..."}}`
  - Notes: Returns a local JWT (HS256). Use this token for protected endpoints.

- **POST /auth/login**
  - Auth: none
  - Body: JSON `{ "email": "user@example.com", "password": "Secret123" }`
  - Success: same shape as signup (returns `access_token`).

## Health

- **GET /health**
  - Auth: none
  - Success: `{ "status": "ok" }`

## Document Upload & Parse

- **POST /documents/upload**
  - Auth: required — header `Authorization: Bearer <token>`
  - Content-Type: `multipart/form-data` with file field name `files` (multiple) or `file` (single)
  - Behavior: uploads the PDF to Supabase and runs the Gemini parse concurrently; the Mongo document is created after parse completes. Response includes document id and status.
  - Success: `{"document_id":"<id>","status":"completed","error_message":null}` or `{"document_id":"<id>","status":"failed","error_message":"..."}`
  - Errors: 400 (non-PDF/empty file), 401 (unauthorized), 422 (invalid multipart), 500 (storage/parse failure)

## Documents — list / detail / batch status

- **GET /documents**
  - Auth: required
  - Response: array of user's documents. Each item: `id`, `file_name`, `status` (`processing|completed|failed`), `created_at`, `parsed_at`.

- **GET /documents/{doc_id}**
  - Auth: required
  - Response: detailed document including `extracted_json` (when completed) and `error_message` (when failed).

- **POST /documents/status**
  - Auth: required
  - Body: JSON `{ "document_ids": ["id1","id2",...] }`
  - Response: array of status objects for the requesting user:
    - `{ "id":"...", "status":"processing|completed|failed", "error_message":"...", "parsed_at":"...", "file_url":"..." }`
  - Notes: Designed for frontend polling to show per-file progress. Poll frequently (e.g., 1s) or batch requests for many files.

## Excel Export

- **POST /documents/excel**
  - Auth: required
  - Body: JSON `{ "document_ids": ["id1","id2",...] }`
  - Behavior: collects `extracted_json` from documents with status `completed`, builds an Excel workbook, and returns it as a file stream.
  - Success: streaming response with `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` and header `Content-Disposition: attachment; filename=section_a.xlsx`.

## Authentication & Headers

- Protected routes require `Authorization: Bearer <token>`.
- Use `multipart/form-data` for uploads, `application/json` for other POSTs.

## Common Response Patterns

- `200 OK`: success.
- `400 Bad Request`: validation issues (non-PDF, missing fields).
- `401 Unauthorized`: missing/invalid token.
- `422 Unprocessable Entity`: payload/type mismatch.
- `500 Internal Server Error`: storage or LLM runtime errors — check server logs and `error_message` on documents.

## Frontend Integration Tips

- Use `/documents/upload` for each file (one request per file). The endpoint returns `document_id` and immediate `status`; set client-side state to `processing`.
- Poll `/documents/status` with the list of IDs to update statuses. Suggested strategy:
  - Poll every 1s for active `processing` items; stop when all items are `completed`/`failed`.
  - If many files, batch and increase interval (2–5s) to reduce load.
- Optional push alternative: implement SSE or WebSocket on the backend and push status updates; the backend can be extended with an SSE endpoint.

## Operational Notes

- Ensure `LOCAL_JWT_SECRET` is at least 32 bytes for secure HMAC. Generate with:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- Confirm `SUPABASE_BUCKET` exists in your Supabase project; uploads fail if the bucket is missing.
- The Gemini LLM client is defensive; failed parses will set `status: "failed"` and an `error_message` in Mongo — display it in the UI so users can retry.

## Examples

Signup:
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"Sec12345","name":"Demo"}'
```

Upload:
```bash
curl -v -X POST http://localhost:8000/documents/upload/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@/full/path/HEIDELBERG_24-25.pdf"
```

Status poll:
```bash
curl -X POST http://localhost:8000/documents/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_ids":["699994a338b1e44ac07e3570"]}'
```

Excel export:
```bash
curl -X POST http://localhost:8000/documents/excel \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_ids":["699994a338b1e44ac07e3570"]}' --output section_a.xlsx
```

---

If you want, I can add a small React snippet that wires uploads and polling, or implement an SSE endpoint for push updates. Which would you like next?
