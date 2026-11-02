"""
Unit tests for TW-117 Journey Planning & Personalization API:
- Journey sorting preferences (comfortable, fastest, fewest_transfers, recommended)
- Sorting note and response validation
- Overnight train journey day offset preservation
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_search_routes_with_comfortable_preference():
    """Verify route search accepts 'comfortable' personalization preference."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/routes/search?origin=BCT&destination=HWH&date=2026-11-04&max_transfers=2&sort_by=comfortable"
        )
        assert res.status_code == 200
        data = res.json()
        assert data["sorting_applied"] == "comfortable"
        assert "comfortable" in (data.get("sorting_note") or "").lower()
        assert data["total_routes_found"] >= 1
        assert len(data["routes"]) > 0
        assert len(data["routes"]) <= data["total_routes_found"]


@pytest.mark.asyncio
async def test_search_routes_sorting_modes():
    """Verify standard and personalized sorting modes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fastest
        res_fast = await client.get(
            "/api/v1/routes/search?origin=NDLS&destination=BPL&date=2026-11-04&max_transfers=1&sort_by=fastest"
        )
        assert res_fast.status_code == 200
        data_fast = res_fast.json()
        assert data_fast["sorting_applied"] == "fastest"

        # 2. Fewest transfers
        res_few = await client.get(
            "/api/v1/routes/search?origin=NDLS&destination=BPL&date=2026-11-04&max_transfers=1&sort_by=fewest_transfers"
        )
        assert res_few.status_code == 200
        data_few = res_few.json()
        assert data_few["sorting_applied"] == "fewest_transfers"

        # 3. Invalid sorting mode returns 422 validation error
        res_inv = await client.get(
            "/api/v1/routes/search?origin=NDLS&destination=BPL&date=2026-11-04&max_transfers=1&sort_by=INVALID_SORT"
        )
        assert res_inv.status_code == 422


@pytest.mark.asyncio
async def test_overnight_journey_breakdown_identity():
    """Verify total_duration = total_travel_time + total_wait_time across day offsets."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/routes/search?origin=BCT&destination=HWH&date=2026-11-04&max_transfers=2&sort_by=comfortable"
        )
        assert res.status_code == 200
        data = res.json()

        for route in data["routes"]:
            # Mathematical identity
            assert route["total_duration_minutes"] == route["total_travel_time_minutes"] + route["total_wait_time_minutes"]
            if route["is_direct"]:
                assert route["total_wait_time_minutes"] == 0
                assert route["transfer_count"] == 0
            else:
                assert route["transfer_count"] > 0
                assert len(route["layovers"]) == route["transfer_count"]
                for lay in route["layovers"]:
                    assert lay["duration_minutes"] >= 30
                    assert lay["duration_minutes"] <= 360
