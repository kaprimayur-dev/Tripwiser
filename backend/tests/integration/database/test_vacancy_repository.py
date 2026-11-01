"""
Integration tests for PostgresVacancyRepository.
Verifies sequence bounding, travel class filtering, and expiry timestamps.
"""

import pytest
import datetime
import uuid
from sqlalchemy import delete

from app.core.db import check_database_health, AsyncSessionLocal
from app.infrastructure.database.models.vacancy import ChartVacancyORM
from app.infrastructure.database.repositories.vacancy_repository import PostgresVacancyRepository


@pytest.mark.asyncio
async def test_postgres_vacancy_repository_queries_and_filters():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL database is not available.")

    travel_date = datetime.date(2026, 11, 4)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    future_expiry = now_utc + datetime.timedelta(hours=4)
    past_expiry = now_utc - datetime.timedelta(hours=1)
    inserted_ids = []

    async with AsyncSessionLocal() as session:
        try:
            repo = PostgresVacancyRepository(session)

            # 1. Active unexpired vacancy in 3A (seq 42 to 52)
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
                expires_at=future_expiry,
            )

            # 2. Expired vacancy (should be omitted)
            v2_id = uuid.uuid4()
            v2 = ChartVacancyORM(
                id=v2_id,
                train_number="12002",
                chart_date=travel_date,
                coach="B2",
                berth_number=44,
                berth_type="MB",
                travel_class="3A",
                from_station_code="GWL",
                to_station_code="JHS",
                from_sequence=42,
                to_sequence=52,
                source="chart_feed",
                chart_phase="FIRST_CHART",
                status="VACANT",
                expires_at=past_expiry,
            )

            # 3. Active vacancy in 2A (different class)
            v3_id = uuid.uuid4()
            v3 = ChartVacancyORM(
                id=v3_id,
                train_number="12002",
                chart_date=travel_date,
                coach="A1",
                berth_number=12,
                berth_type="LB",
                travel_class="2A",
                from_station_code="GWL",
                to_station_code="JHS",
                from_sequence=42,
                to_sequence=52,
                source="chart_feed",
                chart_phase="FIRST_CHART",
                status="VACANT",
                expires_at=future_expiry,
            )

            session.add_all([v1, v2, v3])
            await session.commit()
            inserted_ids = [v1_id, v2_id, v3_id]

            # Query without class filter: should find v1 and v3 (v2 expired is excluded)
            results_all = await repo.get_vacancies_for_train(
                train_number="12002",
                travel_date=travel_date,
                min_seq=40,
                max_seq=60,
            )
            assert len(results_all) == 2
            found_ids = {s.segment_id for s in results_all}
            assert str(v1_id) in found_ids
            assert str(v3_id) in found_ids
            assert str(v2_id) not in found_ids

            # Query with travel_class="3A": only v1 returned
            results_3a = await repo.get_vacancies_for_train(
                train_number="12002",
                travel_date=travel_date,
                min_seq=40,
                max_seq=60,
                travel_class="3A",
            )
            assert len(results_3a) == 1
            assert results_3a[0].segment_id == str(v1_id)

            # Query with sequence outside range: returns empty
            results_out_of_bounds = await repo.get_vacancies_for_train(
                train_number="12002",
                travel_date=travel_date,
                min_seq=60,
                max_seq=80,
            )
            assert len(results_out_of_bounds) == 0

        finally:
            if inserted_ids:
                async with AsyncSessionLocal() as cleanup_session:
                    await cleanup_session.execute(
                        delete(ChartVacancyORM).where(ChartVacancyORM.id.in_(inserted_ids))
                    )
                    await cleanup_session.commit()

