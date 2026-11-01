"""
Unit and integration tests for TW-116 Train Discovery & Passenger Intelligence:
- Multi-faceted train search (number, name, station code/name)
- Station trains discovery (/api/v1/stations/{code}/trains and /api/v1/trains/station/{code})
- Compare trains between stations (/api/v1/trains/compare)
- Validation boundaries (identical stations, non-existent stations, empty states)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_search_trains_by_number():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/trains/search?q=12002")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        assert any(t["number"] == "12002" for t in data)
        assert data[0]["number"] == "12002"
        assert "Shatabdi" in data[0]["name"]


@pytest.mark.asyncio
async def test_search_trains_by_name():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/trains/search?q=Rajdhani")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        assert all("rajdhani" in t["name"].lower() or "rajdhani" in t["number"].lower() for t in data)


@pytest.mark.asyncio
async def test_search_trains_by_station():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Search by station code BPL or name Bhopal
        res = await client.get("/api/v1/trains/search?q=BPL")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        # 12002 calls at or terminates at BPL
        assert any(t["number"] == "12002" for t in data)


@pytest.mark.asyncio
async def test_station_serving_trains_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Valid station with compiled train coverage: BPL
        res = await client.get("/api/v1/stations/BPL/trains")
        assert res.status_code == 200
        data = res.json()
        assert data["station_code"] == "BPL"
        assert data["total_trains"] > 0
        assert len(data["trains"]) == data["total_trains"]

        # Check train structure
        sample_train = data["trains"][0]
        assert "train_number" in sample_train
        assert "train_name" in sample_train
        assert "service_type" in sample_train
        assert sample_train["service_type"] in ("ORIGINATING", "TERMINATING", "EN_ROUTE")
        assert "runs_on_days" in sample_train
        assert "frequency_description" in sample_train
        assert "halt_minutes" in sample_train

        # 2. Non-existent station returns 404
        res_404 = await client.get("/api/v1/stations/NONEXISTENT999/trains")
        assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_compare_trains_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Compare direct trains NDLS -> BPL
        res = await client.get("/api/v1/trains/compare?origin=NDLS&destination=BPL")
        assert res.status_code == 200
        data = res.json()
        assert data["origin_code"] == "NDLS"
        assert data["destination_code"] == "BPL"
        assert data["total_trains"] >= 1
        assert len(data["trains"]) == data["total_trains"]

        # Verify train 12002 Bhopal Shatabdi is present in comparison
        shatabdi = next((t for t in data["trains"] if t["number"] == "12002"), None)
        assert shatabdi is not None
        assert shatabdi["departure_time"] is not None
        assert shatabdi["arrival_time"] is not None
        assert shatabdi["scheduled_duration_minutes"] is not None
        assert shatabdi["scheduled_duration_minutes"] > 0
        assert shatabdi["distance_km"] >= 0
        assert "TAG" in shatabdi["table_reference"] or "Table" in shatabdi["table_reference"]

        # Ensure no duplicates: each train number in data["trains"] must be unique
        train_numbers = [t["number"] for t in data["trains"]]
        assert len(train_numbers) == len(set(train_numbers)), "Comparison results must not contain duplicate trains"

        # 2. Identical origin and destination returns 400
        res_bad = await client.get("/api/v1/trains/compare?origin=BPL&destination=BPL")
        assert res_bad.status_code == 400

        # 3. Non-existent station returns 404
        res_404 = await client.get("/api/v1/trains/compare?origin=UNKNOWN999&destination=BPL")
        assert res_404.status_code == 404

        # 4. Corridor with no direct trains returns total_trains = 0 cleanly
        res_empty = await client.get("/api/v1/trains/compare?origin=BCT&destination=MAS")
        assert res_empty.status_code == 200
        data_empty = res_empty.json()
        assert data_empty["total_trains"] == 0
        assert data_empty["trains"] == []


@pytest.mark.asyncio
async def test_overnight_train_duration_math():
    """Verify overnight and day-offset duration math."""
    from app.api.v1.trains import calculate_halt_minutes
    import datetime

    # Same day halt: 10:00 to 10:15 = 15 mins
    h1 = calculate_halt_minutes(datetime.time(10, 0), datetime.time(10, 15), 0, 0)
    assert h1 == 15

    # Overnight crossing: 23:50 to 00:05 next day = 15 mins
    h2 = calculate_halt_minutes(datetime.time(23, 50), datetime.time(0, 5), 0, 1)
    assert h2 == 15

    # Missing timing returns 0 halt
    assert calculate_halt_minutes(None, datetime.time(10, 0)) == 0
    assert calculate_halt_minutes(datetime.time(10, 0), None) == 0


@pytest.mark.asyncio
async def test_station_trains_service_classification():
    """Verify ORIGINATING, TERMINATING, and EN_ROUTE classification for BPL."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/stations/BPL/trains")
        assert res.status_code == 200
        data = res.json()
        trains = data["trains"]

        service_types = {t["service_type"] for t in trains}
        # In BPL there are calling and terminating trains
        assert len(service_types) >= 1
        for t in trains:
            assert t["service_type"] in ("ORIGINATING", "TERMINATING", "EN_ROUTE")
            # If terminating, stop sequence must match total stops
            if t["service_type"] == "TERMINATING":
                assert t["stop_sequence"] == t["total_stops"]
            # If originating, stop sequence must be the start
            if t["service_type"] == "ORIGINATING":
                assert t["stop_sequence"] == 1
