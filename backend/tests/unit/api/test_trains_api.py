"""
Unit and integration tests for Trains API:
- Train search by number and name
- Train detail retrieval with TAG provenance
- Complete timetable schedule with station names and halt calculation
- Intermediate stop slicing (consecutive stops, reversed order, invalid stations, non-stop legs)
- Differentiating compiled trains vs quarantined trains vs unknown train numbers
- Overnight halt calculations
"""

import pytest
import datetime
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.v1.trains import calculate_halt_minutes, format_running_days


def test_calculate_halt_minutes():
    # Normal daytime halt
    assert calculate_halt_minutes(datetime.time(7, 32), datetime.time(7, 34)) == 2
    assert calculate_halt_minutes(datetime.time(8, 12), datetime.time(8, 17)) == 5
    # Passing waypoint (halt = 0)
    assert calculate_halt_minutes(datetime.time(6, 16), datetime.time(6, 16)) == 0
    # Origin or destination with missing timing
    assert calculate_halt_minutes(None, datetime.time(6, 0)) == 0
    assert calculate_halt_minutes(datetime.time(14, 5), None) == 0
    assert calculate_halt_minutes(None, None) == 0
    # Overnight halt transition: arrives 23:55, departs 00:05
    assert calculate_halt_minutes(datetime.time(23, 55), datetime.time(0, 5)) == 10
    # Overnight halt with day offsets: arr day 0 at 23:50, dep day 1 at 00:10
    assert calculate_halt_minutes(datetime.time(23, 50), datetime.time(0, 10), arr_day_offset=0, dep_day_offset=1) == 20


def test_format_running_days():
    # All 7 days
    assert format_running_days([0, 1, 2, 3, 4, 5, 6]) == "Daily (Mon-Sun)"
    # Mon-Sat (Except Sunday)
    assert format_running_days([0, 1, 2, 3, 4, 5]) == "Except Sunday (Mon-Sat)"
    # Sat-Thu (Except Friday)
    assert format_running_days([0, 1, 2, 3, 5, 6]) == "Except Friday (Sat-Thu)"
    # Mon-Fri
    assert format_running_days([0, 1, 2, 3, 4]) == "Weekdays (Mon-Fri)"
    # Bi-weekly Mon & Fri
    assert format_running_days([0, 4]) == "Mon, Fri"
    # Empty
    assert format_running_days([]) == "Not Scheduled"


@pytest.mark.asyncio
async def test_train_search_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Search by train number prefix
        res = await client.get("/api/v1/trains/search?q=12002")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        train = data[0]
        assert train["number"] == "12002"
        assert "Shatabdi" in train["name"]
        assert train["origin_code"] == "NDLS"
        assert train["destination_code"] == "BPL"
        assert train["runs_on_days"] == [0, 1, 2, 3, 4, 5, 6]
        assert "Daily" in train["frequency_description"]
        assert train["total_stops"] > 0
        assert train["provenance_tier"] == "OFFICIALLY_VERIFIED_INDIVIDUAL_TABLE_RECORD"

        # Search by train name substring
        res_name = await client.get("/api/v1/trains/search?q=Rajdhani&limit=5")
        assert res_name.status_code == 200
        data_name = res_name.json()
        assert len(data_name) >= 1
        assert any("Rajdhani" in t["name"] for t in data_name)

        # Search with no match
        res_empty = await client.get("/api/v1/trains/search?q=XYZ999NONEXISTENT")
        assert res_empty.status_code == 200
        assert res_empty.json() == []


@pytest.mark.asyncio
async def test_train_detail_and_provenance_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Existing verified train: 12002
        res = await client.get("/api/v1/trains/12002")
        assert res.status_code == 200
        t = res.json()
        assert t["number"] == "12002"
        assert t["origin_name"] != ""
        assert t["destination_name"] != ""
        assert t["source_document"] == "Trains at a Glance (TAG) 2024-2026, Ministry of Railways"
        assert t["publication_version"] == "TAG 2024-2026 (Published July 2024, in force 2024-2026)"
        assert t["table_reference"] == "Table 3A: New Delhi - Rani Kamlapati (Bhopal) Shatabdi Express"
        assert t["provenance_tier"] == "OFFICIALLY_VERIFIED_INDIVIDUAL_TABLE_RECORD"

        # 2. Non-daily verified train: 12302 (Except Friday)
        res_12302 = await client.get("/api/v1/trains/12302")
        assert res_12302.status_code == 200
        t_12302 = res_12302.json()
        assert 4 not in t_12302["runs_on_days"]
        assert "Except Friday" in t_12302["frequency_description"]

        # 3. Quarantined train: 04601
        res_quarantine = await client.get("/api/v1/trains/04601")
        assert res_quarantine.status_code == 404
        q_data = res_quarantine.json()
        assert q_data["detail"]["error_code"] == "AWAITING_VERIFIED_SCHEDULE"
        assert "quarantined" in q_data["detail"]["message"].lower()

        # 4. Unknown train number: 99999
        res_unknown = await client.get("/api/v1/trains/99999")
        assert res_unknown.status_code == 404
        u_data = res_unknown.json()
        assert u_data["detail"]["error_code"] == "TRAIN_NOT_FOUND"


@pytest.mark.asyncio
async def test_train_schedule_timetable_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Full schedule for 12002
        res = await client.get("/api/v1/trains/12002/schedule")
        assert res.status_code == 200
        data = res.json()
        assert data["train"]["number"] == "12002"
        assert len(data["stops"]) == data["total_stops"]
        assert data["commercial_stops_count"] > 0

        # Verify sequence order and timings
        stops = data["stops"]
        first_stop = stops[0]
        assert first_stop["station_code"] == "NDLS"
        assert first_stop["stop_sequence"] == 1
        assert first_stop["arrival_time"] is None
        assert first_stop["departure_time"] is not None

        last_stop = stops[-1]
        assert last_stop["station_code"] == "BPL"
        assert last_stop["arrival_time"] is not None
        assert last_stop["departure_time"] is None

        # Monotonic sequence assertion
        for i in range(len(stops) - 1):
            assert stops[i]["stop_sequence"] < stops[i + 1]["stop_sequence"]

        # Filter only commercial passenger halts
        res_comm = await client.get("/api/v1/trains/12002/schedule?only_commercial=true")
        assert res_comm.status_code == 200
        data_comm = res_comm.json()
        assert len(data_comm["stops"]) == data["commercial_stops_count"]
        for st in data_comm["stops"]:
            assert st["is_commercial_halt"] is True


@pytest.mark.asyncio
async def test_intermediate_stops_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Valid intermediate slice on Train 12002 (NDLS -> BPL)
        # Slicing from MTJ (Mathura) to GWL (Gwalior)
        res = await client.get("/api/v1/trains/12002/intermediate-stops?from_code=MTJ&to_code=GWL&only_commercial=true")
        assert res.status_code == 200
        data = res.json()
        assert data["train_number"] == "12002"
        assert data["from_station_code"] == "MTJ"
        assert data["to_station_code"] == "GWL"
        assert data["intermediate_stop_count"] >= 1
        # Check AGC (Agra Cantt) is inside
        intermediate_codes = [s["station_code"] for s in data["stops"]]
        assert "AGC" in intermediate_codes
        # Assert neither MTJ nor GWL are in intermediate stops list
        assert "MTJ" not in intermediate_codes
        assert "GWL" not in intermediate_codes

        # 2. Consecutive stops (MTJ to BAD)
        res_consec = await client.get("/api/v1/trains/12002/intermediate-stops?from_code=MTJ&to_code=BAD")
        assert res_consec.status_code == 200
        assert res_consec.json()["intermediate_stop_count"] == 0

        # 3. Reversed station order (GWL to MTJ) -> HTTP 400
        res_rev = await client.get("/api/v1/trains/12002/intermediate-stops?from_code=GWL&to_code=MTJ")
        assert res_rev.status_code == 400
        assert "reversed" in res_rev.json()["detail"].lower()

        # 4. Same origin and destination -> HTTP 400
        res_same = await client.get("/api/v1/trains/12002/intermediate-stops?from_code=NDLS&to_code=NDLS")
        assert res_same.status_code == 400

        # 5. Station not on route -> HTTP 400
        res_invalid = await client.get("/api/v1/trains/12002/intermediate-stops?from_code=HWH&to_code=BPL")
        assert res_invalid.status_code == 400
        assert "not a scheduled stop" in res_invalid.json()["detail"].lower()

        # 6. Unknown train -> HTTP 404
        res_no_train = await client.get("/api/v1/trains/99999/intermediate-stops?from_code=NDLS&to_code=BPL")
        assert res_no_train.status_code == 404
