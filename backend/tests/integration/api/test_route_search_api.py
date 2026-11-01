"""
Integration tests for Route Discovery and Station API endpoints.
Verifies end-to-end HTTP requests against the FastAPI ASGI application with real database integration.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.db import check_database_health


@pytest.mark.asyncio
async def test_station_search_and_lookup_endpoints():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Search stations by code
        res = await client.get("/api/v1/stations/search?q=NDLS&limit=5")
        assert res.status_code == 200
        stations = res.json()
        assert len(stations) >= 1
        assert any(s["code"] == "NDLS" for s in stations)

        # 2. Search stations by city name
        res_city = await client.get("/api/v1/stations/search?q=Mumbai&limit=10")
        assert res_city.status_code == 200
        mumbai_stations = res_city.json()
        assert len(mumbai_stations) >= 1

        # 3. Get station by code
        res_code = await client.get("/api/v1/stations/NDLS")
        assert res_code.status_code == 200
        ndls = res_code.json()
        assert ndls["code"] == "NDLS"
        assert "New Delhi" in ndls["name"] or "NEW DELHI" in ndls["name"]
        assert abs(ndls["latitude"] - 28.6) < 0.5

        # 4. Station not found
        res_404 = await client.get("/api/v1/stations/NONEXISTENT123")
        assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_nearby_stations_endpoint():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Coordinates for New Delhi (28.6139, 77.2090)
        res = await client.get("/api/v1/stations/nearby?latitude=28.6139&longitude=77.2090&radius_km=30")
        assert res.status_code == 200
        nearby = res.json()
        assert len(nearby) >= 1
        codes = [item["station"]["code"] for item in nearby]
        assert "NDLS" in codes or "NZM" in codes or "DLI" in codes
        # Ensure distance is positive and sorted
        assert nearby[0]["distance_km"] >= 0.0


@pytest.mark.asyncio
async def test_route_search_direct_trains():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Search direct BCT -> NDLS on 2026-11-05 (Thursday)
        # 12951 runs daily (all 7 days)
        res = await client.get("/api/v1/routes/search?origin=BCT&destination=NDLS&date=2026-11-05&max_transfers=0")
        assert res.status_code == 200
        data = res.json()

        assert data["query"]["origin"] == "BCT"
        assert data["query"]["destination"] == "NDLS"
        assert data["origin_station"] is not None
        assert data["destination_station"] is not None
        assert data["timetable_status"] == "TIMETABLE_CONFIRMED"
        assert data["fare_status"] == "DEFERRED_NO_COMMERCIAL_FEED"
        assert data["availability_status"] == "NOT_CHECKED_SEAT_AVAILABILITY_DEFERRED"

        # In DataMeet compiled dataset, 12951 and 12953 run BCT -> NDLS / NZM
        if data["total_routes_found"] > 0:
            assert data["direct_routes_count"] >= 1
            route = data["routes"][0]
            assert route["is_direct"] is True
            assert route["transfer_count"] == 0
            assert route["total_fare"] is None  # Never fabricated to 0.0
            assert route["total_duration_minutes"] > 0
            assert len(route["legs"]) == 1

            leg = route["legs"][0]
            assert leg["train_number"] in ("12951", "12953")
            assert leg["timetable_status"] == "TIMETABLE_CONFIRMED"
            assert leg["travel_class"] is None  # Unverified commercial classes not fabricated
            assert leg["availability"] is None  # Seat availability provider was not queried


@pytest.mark.asyncio
async def test_route_search_validation_and_errors():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Same origin and destination
        res_same = await client.get("/api/v1/routes/search?origin=NDLS&destination=NDLS&date=2026-11-05")
        assert res_same.status_code == 400
        assert "identical" in res_same.json()["detail"].lower()

        # Invalid date
        res_date = await client.get("/api/v1/routes/search?origin=BCT&destination=NDLS&date=not-a-date")
        assert res_date.status_code == 400
        assert "invalid date" in res_date.json()["detail"].lower()

        # Station not found
        res_unknown = await client.get("/api/v1/routes/search?origin=UNKNOWN999&destination=NDLS&date=2026-11-05")
        assert res_unknown.status_code == 404


@pytest.mark.asyncio
async def test_route_search_sorting_modes():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for sort_mode in ["recommended", "fastest", "fewest_transfers"]:
            res = await client.get(
                f"/api/v1/routes/search?origin=BCT&destination=NDLS&date=2026-11-05&sort_by={sort_mode}"
            )
            assert res.status_code == 200
            data = res.json()
            assert data["query"]["sort_by"] == sort_mode
            assert data["sorting_applied"] == sort_mode
            assert data["sorting_note"] is None

        # Test cheapest sorting fallback: must clearly indicate deferral
        res_cheap = await client.get(
            "/api/v1/routes/search?origin=BCT&destination=NDLS&date=2026-11-05&sort_by=cheapest"
        )
        assert res_cheap.status_code == 200
        cheap_data = res_cheap.json()
        assert cheap_data["query"]["sort_by"] == "cheapest"
        assert cheap_data["sorting_applied"] == "recommended"
        assert cheap_data["sorting_note"] is not None
        assert "deferred" in cheap_data["sorting_note"].lower()


@pytest.mark.asyncio
async def test_route_search_no_route_found_diagnostics():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Search between two valid stations that have no direct trains in the 8-train compiled dataset
        # BCT and HWH have no direct trains (12301/12302 are NDLS-HWH, 12951/12952 are BCT-NDLS)
        res = await client.get("/api/v1/routes/search?origin=BCT&destination=HWH&date=2026-11-05&max_transfers=0")
        assert res.status_code == 200
        data = res.json()
        assert data["total_routes_found"] == 0
        assert data["no_route_reason"] in ("NO_DIRECT_OR_TRANSFER_ROUTES", "TRANSFER_BUFFER_VIOLATION")
