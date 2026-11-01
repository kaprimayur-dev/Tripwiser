"""
Integration tests for Bachelor Special Berth Segment Discovery API.
Verifies API contract, empty/unavailable states, and successful multi-segment assembly.
"""

import pytest
import datetime
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app
from app.core.db import check_database_health, AsyncSessionLocal
from app.infrastructure.database.models.vacancy import ChartVacancyORM


@pytest.mark.asyncio
async def test_bachelor_search_identical_stations_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/bachelor/search?origin=NDLS&destination=NDLS&date=2026-11-04")
        assert res.status_code == 400
        assert "identical" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_bachelor_search_no_direct_trains():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL database is not available.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/bachelor/search?origin=INVALID1&destination=INVALID2&date=2026-11-04")
        assert res.status_code == 200
        data = res.json()
        assert data["total_itineraries"] == 0
        assert data["itineraries"] == []
        assert data["status"] == "NO_DIRECT_TRAINS"
        assert data["is_live_source"] is False


@pytest.mark.asyncio
async def test_bachelor_search_empty_vacancies_returns_honest_response():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL database is not available.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # BCT -> NDLS operates train 12951, but has 0 records in chart_vacancies
        res = await client.get("/api/v1/bachelor/search?origin=BCT&destination=NDLS&date=2026-11-04")
        assert res.status_code == 200
        data = res.json()
        assert data["origin_code"] == "BCT"
        assert data["destination_code"] == "NDLS"
        assert data["total_itineraries"] == 0
        assert data["itineraries"] == []
        assert data["status"] == "NO_CHART_VACANCIES"
        assert data["is_live_source"] is False
        assert "chart" in data["chart_policy_notice"].lower()


@pytest.mark.asyncio
async def test_bachelor_search_discovers_assembled_segments():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL database is not available.")

    travel_date = datetime.date(2026, 11, 4)  # Wednesday (12002 runs daily)
    expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)
    inserted_ids = []

    async with AsyncSessionLocal() as session:
        try:
            # Insert test chart vacancies for train 12002 (NDLS -> BPL)
            # GWL is sequence 42, JHS is 52, BPL is 87
            v1_id = uuid.uuid4()
            v1 = ChartVacancyORM(
                id=v1_id,
                train_number="12002",
                chart_date=travel_date,
                coach="B2",
                berth_number=43,
                berth_type="UB",
                travel_class="3A",
                from_station_code="GWL",
                to_station_code="JHS",
                from_sequence=42,
                to_sequence=52,
                source="chart_feed",
                chart_phase="FIRST_CHART",
                status="VACANT",
                expires_at=expiry,
            )

            v2_id = uuid.uuid4()
            v2 = ChartVacancyORM(
                id=v2_id,
                train_number="12002",
                chart_date=travel_date,
                coach="B3",
                berth_number=21,
                berth_type="MB",
                travel_class="3A",
                from_station_code="JHS",
                to_station_code="BPL",
                from_sequence=52,
                to_sequence=87,
                source="chart_feed",
                chart_phase="FIRST_CHART",
                status="VACANT",
                expires_at=expiry,
            )

            session.add_all([v1, v2])
            await session.commit()
            inserted_ids = [v1_id, v2_id]

            # Query API
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.get(
                    f"/api/v1/bachelor/search?origin=GWL&destination=BPL&date={travel_date.isoformat()}&travel_class=3A"
                )
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "SUCCESS"
                assert data["total_itineraries"] >= 1
                first = data["itineraries"][0]
                assert first["train_number"] == "12002"
                assert first["total_segment_count"] == 2
                assert first["berth_changes_count"] == 1
                assert first["is_continuous"] is True
                assert len(first["segments"]) == 2
                assert first["segments"][0]["from_station_code"] == "GWL"
                assert first["segments"][0]["to_station_code"] == "JHS"
                assert first["segments"][0]["coach"] == "B2"
                assert first["segments"][0]["berth_number"] == 43
                assert first["segments"][1]["from_station_code"] == "JHS"
                assert first["segments"][1]["to_station_code"] == "BPL"
                assert first["segments"][1]["coach"] == "B3"
                assert first["segments"][1]["berth_number"] == 21

        finally:
            # Cleanup test vacancies
            if inserted_ids:
                async with AsyncSessionLocal() as cleanup_session:
                    await cleanup_session.execute(
                        delete(ChartVacancyORM).where(ChartVacancyORM.id.in_(inserted_ids))
                    )
                    await cleanup_session.commit()

