import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_station_search_exact_match_priority():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Search 'BPL' - exact code should be item 0
        res = await client.get("/api/v1/stations/search?q=BPL&limit=10")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        assert data[0]["code"] == "BPL"
        assert "BHOPAL" in data[0]["name"].upper()

        # 2. Case insensitivity: 'bpl'
        res_lower = await client.get("/api/v1/stations/search?q=bpl&limit=10")
        assert res_lower.status_code == 200
        data_lower = res_lower.json()
        assert data_lower[0]["code"] == "BPL"

        # 3. Partial name matching: 'Gwalior'
        res_gwl = await client.get("/api/v1/stations/search?q=Gwalior&limit=5")
        assert res_gwl.status_code == 200
        data_gwl = res_gwl.json()
        codes = [s["code"] for s in data_gwl]
        assert "GWL" in codes

        # 4. Limit parameter respected
        res_limit = await client.get("/api/v1/stations/search?q=New&limit=3")
        assert res_limit.status_code == 200
        assert len(res_limit.json()) <= 3


@pytest.mark.asyncio
async def test_nearby_stations_by_code():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Nearby stations around NDLS (New Delhi) within 30 km
        res = await client.get("/api/v1/stations/nearby?station_code=NDLS&radius_km=30&limit=10")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0

        # Source station (NDLS) must be excluded from its own nearby list
        nearby_codes = [item["station"]["code"] for item in data]
        assert "NDLS" not in nearby_codes

        # Sorted nearest-first
        distances = [item["distance_km"] for item in data]
        assert distances == sorted(distances)

        # Distances must be within radius
        for d in distances:
            assert 0.0 < d <= 30.0

        # Known Delhi neighbor stations like CSB, TKJ, NZM, DLI or DEE should be present
        has_delhi_neighbor = any(c in nearby_codes for c in ["CSB", "TKJ", "NZM", "DLI", "DEE", "DSJ"])
        assert has_delhi_neighbor is True


@pytest.mark.asyncio
async def test_nearby_stations_errors_and_fallbacks():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unknown station code -> 404
        res_404 = await client.get("/api/v1/stations/nearby?station_code=ZZZ999&radius_km=30")
        assert res_404.status_code == 404
        assert "not found" in res_404.json()["detail"].lower()

        # 2. Missing both station_code and coordinates -> 400
        res_400 = await client.get("/api/v1/stations/nearby?radius_km=30")
        assert res_400.status_code == 400

        # 3. Radius exceeds max (le=200) -> 422
        res_422 = await client.get("/api/v1/stations/nearby?station_code=NDLS&radius_km=500")
        assert res_422.status_code == 422

        # 4. Fallback to GPS coordinates (NDLS coordinates approx 28.64, 77.22)
        res_gps = await client.get("/api/v1/stations/nearby?latitude=28.64&longitude=77.22&radius_km=15&limit=5")
        assert res_gps.status_code == 200
        assert len(res_gps.json()) > 0


@pytest.mark.asyncio
async def test_station_details_with_coverage():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Known major station with compiled schedules: NDLS
        res_ndls = await client.get("/api/v1/stations/NDLS")
        assert res_ndls.status_code == 200
        ndls = res_ndls.json()
        assert ndls["code"] == "NDLS"
        assert "NEW DELHI" in ndls["name"].upper()
        assert ndls["latitude"] != 0.0
        assert ndls["longitude"] != 0.0
        cov = ndls["timetable_coverage"]
        assert cov["has_timetable_coverage"] is True
        assert cov["total_compiled_trains"] > 0
        assert cov["coverage_status"] == "VERIFIED_TIMETABLE_COVERAGE"

        # 2. Unknown station -> 404
        res_unknown = await client.get("/api/v1/stations/UNKNOWNXYZ")
        assert res_unknown.status_code == 404

        # 3. Check station without compiled schedule records (distinguish from 404)
        # Find a station in DB with 0 schedule records
        res_search = await client.get("/api/v1/stations/search?q=A&limit=50")
        assert res_search.status_code == 200
        stations = res_search.json()
        
        # Test one of the minor stations
        for st in stations:
            res_det = await client.get(f"/api/v1/stations/{st['code']}")
            if res_det.status_code == 200:
                det = res_det.json()
                if det["timetable_coverage"]["total_compiled_trains"] == 0:
                    assert det["timetable_coverage"]["has_timetable_coverage"] is False
                    assert det["timetable_coverage"]["coverage_status"] == "AWAITING_COMPILED_SCHEDULES"
                    assert "no compiled schedule" in det["timetable_coverage"]["coverage_note"].lower()
                    break
