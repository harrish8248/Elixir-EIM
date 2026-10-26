"""
Pytest Fixtures for Elixir EIM Test Suite.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from apps.api.app.main import app


@pytest_asyncio.fixture
async def async_client():
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
