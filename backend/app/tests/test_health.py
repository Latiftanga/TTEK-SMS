"""
Phase 0 smoke tests.
These run in CI to confirm the app starts and basic infrastructure works.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch


@pytest.fixture
async def client():
    """Async test client with mocked Redis and DB."""
    with (
        patch("app.core.redis.init_redis", new_callable=AsyncMock),
        patch("app.core.redis.close_redis", new_callable=AsyncMock),
    ):
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_returns_env(client):
    response = await client.get("/health")
    data = response.json()
    assert "env" in data


@pytest.mark.asyncio
async def test_unknown_route_returns_404(client):
    response = await client.get("/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_docs_available_in_development(client):
    """Docs should be available in development mode."""
    response = await client.get("/docs")
    assert response.status_code == 200
