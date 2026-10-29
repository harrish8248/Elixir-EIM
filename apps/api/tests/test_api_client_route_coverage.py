"""
Test API Client Route Coverage.
Extracts every endpoint used in apps/web/src/api/client.ts (path pattern)
and asserts that it exists in the backend FastAPI OpenAPI schema.
"""

import re
from pathlib import Path
import pytest
from apps.api.app.main import create_app


def test_every_api_client_endpoint_exists_in_openapi():
    client_ts_path = Path("apps/web/src/api/client.ts")
    assert client_ts_path.exists(), "apps/web/src/api/client.ts not found"

    content = client_ts_path.read_text(encoding="utf-8")

    # Match all string literals / template strings starting with /api/v1/
    raw_endpoints = set(re.findall(r'["\'`](/api/v1/[^\s"\'`]+)', content))
    assert len(raw_endpoints) >= 25, f"Expected >= 25 endpoints, found {len(raw_endpoints)}"

    app = create_app()
    openapi = app.openapi()
    openapi_paths = set(openapi.get("paths", {}).keys())

    missing = []
    for ep in sorted(raw_endpoints):
        # Strip query params like ?... or ${qs} or ${query}
        base_ep = ep.split("?")[0]
        base_ep = re.sub(r"\$\{(?:qs|query)\}", "", base_ep)

        # Normalize template variables like /documents/${documentId}/versions -> /documents/{param}/versions
        normalized_client = re.sub(r"\$\{[^}]+\}", "{param}", base_ep).rstrip("/")
        if not normalized_client:
            continue

        # Match against openapi path with normalized parameters: /documents/{document_id}/versions -> /documents/{param}/versions
        matched = False
        for op in openapi_paths:
            normalized_op = re.sub(r"\{[^}]+\}", "{param}", op).rstrip("/")
            if normalized_client == normalized_op:
                matched = True
                break

        if not matched:
            missing.append(ep)

    assert not missing, (
        f"The following {len(missing)} endpoints in client.ts do not exist in FastAPI backend OpenAPI:\n"
        + "\n".join(f" - {m}" for m in missing)
    )
