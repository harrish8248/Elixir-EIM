# Elixir EIM - Operational Runbook

## 1. Health & Liveness Checks
- **Liveness:** `GET /api/v1/system/health/live` (HTTP 200)
- **Readiness:** `GET /api/v1/system/health/ready` (checks PostgreSQL, Redis, MinIO, OPA)
- **Product Info:** `GET /api/v1/system/info`

## 2. Common Operations with `elixir-admin`
```bash
# Run schema migrations
elixir-admin migrate

# Verify audit trail integrity
elixir-admin verify-audit-chain

# Rebuild search indexes
elixir-admin reindex --all

# Export tenant configuration
elixir-admin export-config --tenant-id <UUID> --out-file config.json

# Import tenant configuration
elixir-admin import-config --tenant-id <UUID> --in-file config.json --dry-run
```

## 3. Incident Response
- **Audit Verification Failure:** Isolate the database immediately; run `elixir-admin verify-audit-chain` to determine the exact sequence number where the cryptographic hash broke.
- **Malware Quarantine Spike:** Check ClamAV logs and review quarantined documents in `guardrail_events`.
