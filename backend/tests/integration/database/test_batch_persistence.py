"""
Integration tests for RailwayDataPersistenceService and PostGIS spatial queries.
"""

import pytest
import datetime
from sqlalchemy import select, func
from geoalchemy2.functions import ST_DWithin, ST_SetSRID, ST_MakePoint

from app.core.db import check_database_health, AsyncSessionLocal
from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.infrastructure.database.models.station import StationORM
from app.infrastructure.database.models.train import TrainORM, ScheduleORM
from app.infrastructure.persistence.batch_persistence import RailwayDataPersistenceService
from app.infrastructure.database.repositories.train_repository import SQLAlchemyTrainRepository


@pytest.mark.asyncio
class TestBatchPersistenceAndSpatialIntegration:
    """Verifies chunked bulk upserts, PostGIS spatial radius queries, and schedule atomicity."""

    async def test_bulk_upsert_stations_and_postgis_spatial_query(self):
        db_healthy = await check_database_health()
        if not db_healthy:
            pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

        service = RailwayDataPersistenceService()

        # 5 stations: 2 in Delhi area, 2 in Mumbai area, 1 in Bhopal
        stations = [
            Station(code="NDLS", name="New Delhi", latitude=28.6423, longitude=77.2200, state="Delhi", zone="NR"),
            Station(code="NZM", name="Hazrat Nizamuddin", latitude=28.5888, longitude=77.2534, state="Delhi", zone="NR"),
            Station(code="MMCT", name="Mumbai Central", latitude=18.9696, longitude=72.8193, state="Maharashtra", zone="WR"),
            Station(code="BVI", name="Borivali", latitude=19.2289, longitude=72.8570, state="Maharashtra", zone="WR"),
            Station(code="BPL", name="Bhopal Junction", latitude=23.2599, longitude=77.4126, state="Madhya Pradesh", zone="WCR"),
        ]

        async with AsyncSessionLocal() as session:
            try:
                # 1. Bulk Upsert Stations
                count = await service.bulk_upsert_stations(stations, chunk_size=2, session=session)
                assert count == 5

                # 2. Verify Stations Ingested
                for s in stations:
                    orm = await session.get(StationORM, s.code)
                    assert orm is not None
                    assert orm.name == s.name

                # 3. PostGIS ST_DWithin Spatial Query (Radius around New Delhi: 20 km)
                delhi_point = ST_SetSRID(ST_MakePoint(77.2200, 28.6423), 4326)
                stmt_delhi = select(StationORM.code).where(
                    ST_DWithin(StationORM.location, delhi_point, 20_000)  # 20 km in meters
                )
                res_delhi = await session.execute(stmt_delhi)
                delhi_codes = set(res_delhi.scalars().all())

                assert "NDLS" in delhi_codes
                assert "NZM" in delhi_codes
                assert "MMCT" not in delhi_codes
                assert "BVI" not in delhi_codes

                # 4. PostGIS ST_DWithin Spatial Query (Radius around Mumbai: 35 km)
                mumbai_point = ST_SetSRID(ST_MakePoint(72.8193, 18.9696), 4326)
                stmt_mumbai = select(StationORM.code).where(
                    ST_DWithin(StationORM.location, mumbai_point, 35_000)
                )
                res_mumbai = await session.execute(stmt_mumbai)
                mumbai_codes = set(res_mumbai.scalars().all())

                assert "MMCT" in mumbai_codes
                assert "BVI" in mumbai_codes
                assert "NDLS" not in mumbai_codes

                # 5. Idempotency Verification: Re-upserting with modified name updates cleanly
                updated_stations = [
                    Station(code="NDLS", name="New Delhi Premier Junction", latitude=28.6423, longitude=77.2200, state="Delhi", zone="NR"),
                ]
                await service.bulk_upsert_stations(updated_stations, session=session)
                orm_updated = await session.get(StationORM, "NDLS")
                assert orm_updated is not None
                assert orm_updated.name == "New Delhi Premier Junction"

            finally:
                await session.rollback()

    async def test_bulk_upsert_trains_schedule_replacement_and_route_search(self):
        db_healthy = await check_database_health()
        if not db_healthy:
            pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

        service = RailwayDataPersistenceService()

        # Seed stations first to satisfy foreign keys
        stations = [
            Station(code="MMCT", name="Mumbai Central", latitude=18.9696, longitude=72.8193),
            Station(code="BVI", name="Borivali", latitude=19.2289, longitude=72.8570),
            Station(code="KOTA", name="Kota Junction", latitude=25.2138, longitude=75.8648),
            Station(code="NDLS", name="New Delhi", latitude=28.6423, longitude=77.2200),
        ]

        async with AsyncSessionLocal() as session:
            try:
                await service.bulk_upsert_stations(stations, session=session)

                # 1. Create Train with 4 stops
                schedules_initial = [
                    TrainScheduleEntry(station_code="MMCT", departure_time=datetime.time(17, 0), day_offset=0, distance_km=0.0, stop_sequence=1),
                    TrainScheduleEntry(station_code="BVI", arrival_time=datetime.time(17, 30), departure_time=datetime.time(17, 33), day_offset=0, distance_km=30.0, stop_sequence=2),
                    TrainScheduleEntry(station_code="KOTA", arrival_time=datetime.time(3, 15), departure_time=datetime.time(3, 20), day_offset=1, distance_km=900.0, stop_sequence=3),
                    TrainScheduleEntry(station_code="NDLS", arrival_time=datetime.time(8, 30), day_offset=1, distance_km=1386.0, stop_sequence=4),
                ]
                train_initial = Train(
                    number="12951",
                    name="Mumbai Rajdhani",
                    origin_code="MMCT",
                    destination_code="NDLS",
                    runs_on_days=[0, 1, 2, 3, 4, 5, 6],
                    schedule=schedules_initial,
                )

                # Bulk upsert train
                await service.bulk_upsert_trains([train_initial], session=session)

                # Verify 4 stops exist
                sch_res = await session.execute(
                    select(ScheduleORM).where(ScheduleORM.train_number == "12951").order_by(ScheduleORM.stop_sequence)
                )
                sch_rows = sch_res.scalars().all()
                assert len(sch_rows) == 4
                assert [r.station_code for r in sch_rows] == ["MMCT", "BVI", "KOTA", "NDLS"]

                # 2. Schedule Replacement Test: Re-upsert train with only 2 stops (non-stop direct)
                schedules_updated = [
                    TrainScheduleEntry(station_code="MMCT", departure_time=datetime.time(17, 0), day_offset=0, distance_km=0.0, stop_sequence=1),
                    TrainScheduleEntry(station_code="NDLS", arrival_time=datetime.time(8, 30), day_offset=1, distance_km=1386.0, stop_sequence=2),
                ]
                train_updated = Train(
                    number="12951",
                    name="Mumbai Rajdhani Express",
                    origin_code="MMCT",
                    destination_code="NDLS",
                    runs_on_days=[0, 1, 2, 3, 4, 5, 6],
                    schedule=schedules_updated,
                )
                await service.bulk_upsert_trains([train_updated], session=session)

                # Verify exactly 2 stops remain and NO orphaned stops exist
                sch_res2 = await session.execute(
                    select(ScheduleORM).where(ScheduleORM.train_number == "12951").order_by(ScheduleORM.stop_sequence)
                )
                sch_rows2 = sch_res2.scalars().all()
                assert len(sch_rows2) == 2
                assert [r.station_code for r in sch_rows2] == ["MMCT", "NDLS"]

                # 3. Direct Train Route Search
                tr_repo = SQLAlchemyTrainRepository(session)
                direct = await tr_repo.find_direct_trains("MMCT", "NDLS")
                assert len(direct) >= 1
                assert any(t.number == "12951" for t in direct)

            finally:
                await session.rollback()

