"""
Unit and API integration tests for TW-112:
Routes connectivity, interchange discovery, and multi-transfer search API endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_api_routes_connectivity():
    """Verify GET /api/v1/routes/connectivity returns valid direct trains between two stations."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Valid search
        resp = await client.get("/api/v1/routes/connectivity?origin_code=NDLS&destination_code=BPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["origin_code"] == "NDLS"
        assert data["destination_code"] == "BPL"
        assert data["total_trains_count"] > 0
        assert len(data["trains"]) > 0

        train_0 = data["trains"][0]
        assert "train_number" in train_0
        assert "train_name" in train_0
        assert "departure_time" in train_0
        assert "arrival_time" in train_0
        assert "intermediate_stop_count" in train_0
        assert "runs_on_days" in train_0

        # Same station error
        err_same = await client.get("/api/v1/routes/connectivity?origin_code=NDLS&destination_code=NDLS")
        assert err_same.status_code == 400

        # Nonexistent station
        err_404 = await client.get("/api/v1/routes/connectivity?origin_code=NDLS&destination_code=XYZ999")
        assert err_404.status_code == 404


@pytest.mark.asyncio
async def test_api_routes_interchanges():
    """Verify GET /api/v1/routes/interchanges for corridor and global queries."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Global top hubs
        resp_global = await client.get("/api/v1/routes/interchanges?limit=10")
        assert resp_global.status_code == 200
        data_global = resp_global.json()
        assert data_global["total_interchanges_found"] > 0
        assert len(data_global["interchanges"]) > 0

        hub_codes = [h["station_code"] for h in data_global["interchanges"]]
        assert "NDLS" in hub_codes

        # Corridor hubs
        resp_corridor = await client.get(
            "/api/v1/routes/interchanges?origin_code=BCT&destination_code=HWH&limit=10"
        )
        assert resp_corridor.status_code == 200
        data_corridor = resp_corridor.json()
        assert data_corridor["origin_code"] == "BCT"
        assert data_corridor["destination_code"] == "HWH"
        assert len(data_corridor["interchanges"]) > 0

        # Asymmetric query (only origin)
        err_asym = await client.get("/api/v1/routes/interchanges?origin_code=BCT")
        assert err_asym.status_code == 400


@pytest.mark.asyncio
async def test_api_multi_transfer_search():
    """Verify GET /api/v1/routes/search with max_transfers=2."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/routes/search?origin=PUNE&destination=ASR&date=2026-11-03&max_transfers=2"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"]["max_transfers"] == 2
        assert "routes" in data
        for r in data["routes"]:
            assert r["transfer_count"] <= 2
            assert len(r["legs"]) == r["transfer_count"] + 1
            assert len(r["transfer_durations_minutes"]) == r["transfer_count"]
