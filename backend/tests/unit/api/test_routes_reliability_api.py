"""
Unit tests for TW-113: Routes API reliability and journey breakdown serialization.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_search_api_returns_journey_breakdown_and_layovers():
    """Verify route search API serializes journey time breakdown and layover classifications."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test BCT -> HWH on 2026-11-02 with max_transfers=2
        res = await client.get(
            "/api/v1/routes/search",
            params={
                "origin": "BCT",
                "destination": "HWH",
                "date": "2026-11-02",
                "max_transfers": 2,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_routes_found"] > 0
        routes = data["routes"]
        assert len(routes) > 0

        first_route = routes[0]
        # Assert breakdown fields exist
        assert "total_travel_time_minutes" in first_route
        assert "total_wait_time_minutes" in first_route
        assert "layovers" in first_route
        assert "insights" in first_route
        assert "overall_transfer_risk" in first_route

        # Assert identity
        assert first_route["total_duration_minutes"] == (
            first_route["total_travel_time_minutes"] + first_route["total_wait_time_minutes"]
        )

        # Check multi-transfer route has structured layovers
        multi_routes = [r for r in routes if r["transfer_count"] >= 1]
        assert len(multi_routes) > 0
        multi_route = multi_routes[0]
        assert len(multi_route["layovers"]) == multi_route["transfer_count"]

        first_layover = multi_route["layovers"][0]
        assert "interchange_station_code" in first_layover
        assert "arriving_train_number" in first_layover
        assert "departing_train_number" in first_layover
        assert "duration_minutes" in first_layover
        assert "risk_level" in first_layover
        assert "risk_label" in first_layover
        assert "risk_description" in first_layover
        assert first_layover["risk_level"] in [
            "TIGHT_CONNECTION",
            "MODERATE_CONNECTION",
            "COMFORTABLE_CONNECTION",
            "LONG_WAIT",
        ]
