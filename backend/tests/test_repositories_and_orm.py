import pytest
import uuid
from datetime import time, date, datetime, timedelta

from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.infrastructure.database.models.station import StationORM
from app.infrastructure.database.models.train import TrainORM, ScheduleORM
from app.infrastructure.database.models.vacancy import ChartVacancyORM
from app.core.db import check_database_health, AsyncSessionLocal
from app.infrastructure.database.repositories.station_repository import SQLAlchemyStationRepository
from app.infrastructure.database.repositories.train_repository import SQLAlchemyTrainRepository


def test_orm_models_instantiation():
    station_orm = StationORM(
        code="GWL",
        name="Gwalior Junction",
        city="Gwalior",
        state="Madhya Pradesh",
        zone="NCR",
        location="SRID=4326;POINT(78.1828 26.2183)"
    )
    assert station_orm.code == "GWL"

    train_orm = TrainORM(
        number="12616",
        name="Grand Trunk Express",
        origin_code="GWL",
        destination_code="BPL",
        runs_on_days=[0, 1, 2, 3, 4, 5, 6]
    )
    assert train_orm.number == "12616"

    vacancy_orm = ChartVacancyORM(
        id=uuid.uuid4(),
        train_number="12616",
        chart_date=date(2026, 10, 15),
        coach="B2",
        berth_number=43,
        berth_type="UB",
        travel_class="3A",
        from_station_code="GWL",
        to_station_code="JHS",
        from_sequence=1,
        to_sequence=2,
        source="chart_feed",
        chart_phase="FIRST_CHART",
        status="VACANT",
        expires_at=datetime.now() + timedelta(hours=6)
    )
    assert vacancy_orm.coach == "B2"
    assert vacancy_orm.berth_number == 43


@pytest.mark.asyncio
async def test_database_and_repository_integration_if_db_available():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL/PostGIS database is not reachable in current environment.")

    async with AsyncSessionLocal() as session:
        station_repo = SQLAlchemyStationRepository(session)
        train_repo = SQLAlchemyTrainRepository(session)

        # 1. Save Test Station GWL
        st_gwl = Station(
            code="GWL",
            name="Gwalior Junction",
            latitude=26.2183,
            longitude=78.1828,
            city="Gwalior",
            state="MP",
            zone="NCR"
        )
        await station_repo.save(st_gwl)

        # 2. Save Test Station BPL
        st_bpl = Station(
            code="BPL",
            name="Bhopal Junction",
            latitude=23.2599,
            longitude=77.4126,
            city="Bhopal",
            state="MP",
            zone="WCR"
        )
        await station_repo.save(st_bpl)

        # 3. Retrieve Station by Code
        fetched_gwl = await station_repo.get_by_code("GWL")
        assert fetched_gwl is not None
        assert fetched_gwl.name == "Gwalior Junction"

        # 4. Search Station Autocomplete
        searched = await station_repo.search_by_name_or_code("Gwalior")
        assert len(searched) >= 1
        assert searched[0].code == "GWL"

        # 5. Nearby Station Spatial Query
        nearby = await station_repo.get_nearby_stations(26.20, 78.18, radius_km=50.0)
        assert len(nearby) >= 1
        assert nearby[0][0].code == "GWL"
