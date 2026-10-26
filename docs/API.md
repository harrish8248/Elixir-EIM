# Elixir EIM - REST API Specification

## 1. Overview
All Elixir EIM endpoints are prefixed with `/api/v1/`.

## 2. Standard Headers
- `Authorization: Bearer <JWT>`
- `X-Correlation-ID: <UUID>`
- `X-Tenant-ID: <UUID>` (or inferred from JWT)
- `Idempotency-Key: <UUID>` (for write endpoints)

## 3. Standard Response Format
```json
{
  "data": { ... },
  "meta": {
    "requestId": "req_12345",
    "timestamp": "2026-10-26T14:00:00Z",
    "version": "1.0.0"
  }
}
```

## 4. Standard Error Format
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "requestId": "req_12345",
    "timestamp": "2026-10-26T14:00:00Z",
    "details": []
  }
}
```
