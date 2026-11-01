import pytest
import datetime
from app.core.db import check_database_health, AsyncSessionLocal
from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.infrastructure.database.repositories.station_repository import SQLAlchemyStationRepository
from app.infrastructure.database.repositories.train_repository import SQLAlchemyTrainRepository


@pytest.mark.asyncio
async def test_train_repository_flow():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

    async with AsyncSessionLocal() as session:
        try:
            st_repo = SQLAlchemyStationRepository(session)
            tr_repo = SQLAlchemyTrainRepository(session)

            # 1. Create Origin and Destination Stations
            st_gwl = Station(code="GWL", name="Gwalior", latitude=26.2183, longitude=78.1828)
            st_bpl = Station(code="BPL", name="Bhopal", latitude=23.2599, longitude=77.4126)
            await st_repo.save(st_gwl)
            await st_repo.save(st_bpl)

            # 2. Create Train with Schedules
            e1 = TrainScheduleEntry(station_code="GWL", departure_time=datetime.time(6, 15), day_offset=0, distance_km=0.0, stop_sequence=1)
            e2 = TrainScheduleEntry(station_code="BPL", arrival_time=datetime.time(10, 45), day_offset=0, distance_km=390.0, stop_sequence=2)
            train = Train(
                number="TEST12616",
                name="Test Grand Trunk Express",
                origin_code="GWL",
                destination_code="BPL",
                runs_on_days=[0, 1, 2, 3, 4, 5, 6],
                schedule=[e1, e2]
            )

            await tr_repo.save(train)

            # 3. Retrieve Train by Number
            retrieved = await tr_repo.get_by_number("TEST12616")
            assert retrieved is not None
            assert retrieved.name == "Test Grand Trunk Express"
            assert len(retrieved.schedule) == 2
            assert retrieved.schedule[0].station_code == "GWL"
            assert retrieved.schedule[1].station_code == "BPL"

            # 4. Find Direct Trains
            direct_trains = await tr_repo.find_direct_trains("GWL", "BPL")
            assert len(direct_trains) >= 1
            assert any(t.number == "TEST12616" for t in direct_trains)

        finally:
            await session.rollback()
