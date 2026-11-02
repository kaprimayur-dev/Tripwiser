import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "environment" in data

@pytest.mark.asyncio
async def test_readiness_endpoint_when_healthy():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["services"]["database"] is True
        assert data["services"]["redis"] is True

@pytest.mark.asyncio
async def test_readiness_endpoint_when_db_down():
    with patch("app.api.v1.health.check_database_health", new_callable=AsyncMock, return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health/ready")
            assert response.status_code == 503
            data = response.json()["detail"]
            assert data["status"] == "unhealthy"
            assert data["services"]["database"] is False

@pytest.mark.asyncio
async def test_readiness_endpoint_when_redis_degraded():
    with patch("app.api.v1.health.check_database_health", new_callable=AsyncMock, return_value=True):
        with patch("app.api.v1.health.check_redis_health", new_callable=AsyncMock, return_value=False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/health/ready")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "degraded"
                assert data["services"]["database"] is True
                assert data["services"]["redis"] is False
