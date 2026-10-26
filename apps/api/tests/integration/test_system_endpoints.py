"""
Integration Tests for System, Health, Correlation, and Tenancy Middleware.
"""

import pytest
from httpx import AsyncClient

from apps.api.app.platform.branding import BRANDING


@pytest.mark.asyncio
async def test_system_info_endpoint(async_client: AsyncClient):
    """Verify /api/v1/system/info returns accurate branding and metadata."""
    response = await async_client.get("/api/v1/system/info")
    assert response.status_code == 200
    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert body["data"]["name"] == BRANDING.name
    assert body["data"]["shortName"] == BRANDING.short_name
    assert body["data"]["version"] == BRANDING.version
    assert body["data"]["apiVersion"] == "v1"
    assert "activeModules" in body["data"]

    # Meta envelope check
    assert "requestId" in body["meta"]
    assert "X-Correlation-ID" in response.headers


@pytest.mark.asyncio
async def test_system_health_endpoints(async_client: AsyncClient):
    """Verify health and readiness probes."""
    res_live = await async_client.get("/api/v1/system/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "UP"

    res_ready = await async_client.get("/api/v1/system/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "READY"


@pytest.mark.asyncio
async def test_correlation_id_propagation(async_client: AsyncClient):
    """Verify that a client-provided correlation ID is preserved and reflected."""
    custom_cid = "test-corr-id-998877"
    response = await async_client.get(
        "/api/v1/system/info", headers={"X-Correlation-ID": custom_cid}
    )
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == custom_cid
    assert response.json()["meta"]["requestId"] == custom_cid


@pytest.mark.asyncio
async def test_invalid_tenant_id_rejection(async_client: AsyncClient):
    """Verify that a malformed tenant UUID header is rejected cleanly with an error envelope."""
    response = await async_client.get(
        "/api/v1/system/health/unscoped",
        headers={"X-Tenant-ID": "not-a-valid-uuid"},
    )
    assert response.status_code == 422
    # Protected/scoped routes validate tenant UUID
    # Let's test on a path that requires tenant scoping
    response2 = await async_client.get(
        "/api/v1/protected-dummy-path",
        headers={"X-Tenant-ID": "invalid-uuid-string"},
    )
    assert response2.status_code == 422
    err_body = response2.json()
    assert "error" in err_body
    assert err_body["error"]["code"] == "VALIDATION_FAILED"
    assert "requestId" in err_body["error"]
