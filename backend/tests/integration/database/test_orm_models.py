import uuid
import datetime
from app.infrastructure.database.models.station import StationORM
from app.infrastructure.database.models.train import TrainORM, ScheduleORM
from app.infrastructure.database.models.vacancy import ChartVacancyORM


def test_station_orm_instantiation():
    station = StationORM(
        code="GWL",
        name="Gwalior Junction",
        city="Gwalior",
        state="Madhya Pradesh",
        zone="NCR",
        location="SRID=4326;POINT(78.1828 26.2183)"
    )
    assert station.code == "GWL"
    assert station.name == "Gwalior Junction"


def test_train_and_schedule_orm_instantiation():
    train = TrainORM(
        number="12616",
        name="Grand Trunk Express",
        origin_code="GWL",
        destination_code="BPL",
        runs_on_days=[0, 1, 2, 3, 4, 5, 6]
    )
    schedule = ScheduleORM(
        train_number="12616",
        station_code="GWL",
        stop_sequence=1,
        departure_time=datetime.time(6, 15),
        day_offset=0,
        distance_km=0.0
    )
    assert train.number == "12616"
    assert schedule.stop_sequence == 1


def test_chart_vacancy_orm_instantiation():
    vacancy = ChartVacancyORM(
        id=uuid.uuid4(),
        train_number="12616",
        chart_date=datetime.date(2026, 10, 15),
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
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)
    )
    assert vacancy.coach == "B2"
    assert vacancy.berth_number == 43
    assert vacancy.status == "VACANT"


import pytest
from sqlalchemy import select
from app.core.db import check_database_health, AsyncSessionLocal

@pytest.mark.asyncio
async def test_chart_vacancy_persistence_flow():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL is not available.")

    async with AsyncSessionLocal() as session:
        try:
            # 1. Setup required foreign key entities
            st1 = StationORM(code="GWL", name="Gwalior", location="SRID=4326;POINT(78.1828 26.2183)")
            st2 = StationORM(code="JHS", name="Jhansi", location="SRID=4326;POINT(78.5685 25.4484)")
            session.add_all([st1, st2])
            
            tr = TrainORM(
                number="12616",
                name="Grand Trunk Express",
                origin_code="GWL",
                destination_code="JHS",
                runs_on_days=[0, 1, 2, 3, 4, 5, 6]
            )
            session.add(tr)
            await session.flush()

            # 2. Insert ChartVacancyORM
            vacancy_id = uuid.uuid4()
            expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=4)
            vac = ChartVacancyORM(
                id=vacancy_id,
                train_number="12616",
                chart_date=datetime.date(2026, 10, 15),
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
                expires_at=expiry
            )
            session.add(vac)
            await session.flush()

            # 3. Retrieve from live database
            stmt = select(ChartVacancyORM).where(ChartVacancyORM.id == vacancy_id)
            result = await session.execute(stmt)
            retrieved = result.scalar_one_or_none()

            assert retrieved is not None
            assert retrieved.id == vacancy_id
            assert retrieved.train_number == "12616"
            assert retrieved.coach == "B2"
            assert retrieved.berth_number == 43
            assert retrieved.status == "VACANT"
            assert retrieved.travel_class == "3A"

        finally:
            await session.rollback()
