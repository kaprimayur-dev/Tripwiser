import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

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
async def test_readiness_endpoint_when_db_down():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Since DB/Redis are not connected in mock test environment, expect 503 Service Unavailable
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["status"] == "unhealthy"
        assert "database" in data["services"]
        assert "redis" in data["services"]
