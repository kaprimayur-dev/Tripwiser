import datetime
import json
import os
import pytest
import uuid
from sqlalchemy import select, func, delete

from app.core.db import AsyncSessionLocal, check_database_health
from app.infrastructure.database.models.vacancy import ChartVacancyORM
from app.infrastructure.adapters.chart.chart_ingestion_service import ChartIngestionService


@pytest.mark.asyncio
async def test_chart_ingestion_validation_and_quarantine(tmp_path):
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL database is not available.")

    quarantine_dir = str(tmp_path / "quarantine")
    manifest_dir = str(tmp_path / "manifests")

    records = [
        # 1. Invalid: non-existent train
        {
            "train_number": "99999",
            "chart_date": "2026-11-04",
            "coach": "B1",
            "berth_number": 10,
            "from_station_code": "GWL",
            "to_station_code": "JHS",
            "from_sequence": 42,
            "to_sequence": 52,
        },
        # 2. Invalid: identical stations
        {
            "train_number": "12002",
            "chart_date": "2026-11-04",
            "coach": "B1",
            "berth_number": 12,
            "from_station_code": "GWL",
            "to_station_code": "GWL",
            "from_sequence": 42,
            "to_sequence": 52,
        },
        # 3. Invalid: sequence order reversed (to <= from)
        {
            "train_number": "12002",
            "chart_date": "2026-11-04",
            "coach": "B1",
            "berth_number": 15,
            "from_station_code": "GWL",
            "to_station_code": "JHS",
            "from_sequence": 52,
            "to_sequence": 42,
        },
        # 4. Invalid: berth out of bounds
        {
            "train_number": "12002",
            "chart_date": "2026-11-04",
            "coach": "B1",
            "berth_number": 150,
            "from_station_code": "GWL",
            "to_station_code": "JHS",
            "from_sequence": 42,
            "to_sequence": 52,
        },
        # 5. Valid record
        {
            "train_number": "12002",
            "chart_date": "2026-11-04",
            "coach": "B2",
            "berth_number": 43,
            "berth_type": "UB",
            "travel_class": "3A",
            "from_station_code": "GWL",
            "to_station_code": "JHS",
            "from_sequence": 42,
            "to_sequence": 52,
            "source": "verified_chart_audit",
        },
    ]

    async with AsyncSessionLocal() as session:
        service = ChartIngestionService(
            session=session,
            quarantine_dir=quarantine_dir,
            manifest_dir=manifest_dir,
        )

        # Execute Dry Run
        summary = await service.ingest_records(records, persist=False)

        assert summary.total_records == 5
        assert summary.valid_records == 1
        assert summary.quarantined_records == 4
        assert summary.persisted_records == 0  # Dry run!
        assert summary.quarantine_path is not None
        assert os.path.exists(summary.quarantine_path)
        assert summary.manifest_path is not None
        assert os.path.exists(summary.manifest_path)

        # Verify quarantine content
        with open(summary.quarantine_path, "r", encoding="utf-8") as f:
            quarantine_data = json.load(f)
            assert len(quarantine_data) == 4
            reasons = [q["exclusion_reason"] for q in quarantine_data]
            assert any("99999" in r for r in reasons)
            assert any("identical" in r for r in reasons)
            assert any("greater than from_sequence" in r for r in reasons)
            assert any("150" in r for r in reasons)


@pytest.mark.asyncio
async def test_chart_ingestion_idempotent_persistence(tmp_path):
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL database is not available.")

    quarantine_dir = str(tmp_path / "quarantine")
    manifest_dir = str(tmp_path / "manifests")

    test_date_str = "2026-11-04"
    valid_batch = [
        {
            "train_number": "12002",
            "chart_date": test_date_str,
            "coach": "B2",
            "berth_number": 43,
            "berth_type": "UB",
            "travel_class": "3A",
            "from_station_code": "GWL",
            "to_station_code": "JHS",
            "from_sequence": 42,
            "to_sequence": 52,
            "source": "verified_chart_test",
        },
        {
            "train_number": "12002",
            "chart_date": test_date_str,
            "coach": "B3",
            "berth_number": 21,
            "berth_type": "MB",
            "travel_class": "3A",
            "from_station_code": "JHS",
            "to_station_code": "BPL",
            "from_sequence": 52,
            "to_sequence": 87,
            "source": "verified_chart_test",
        },
    ]

    async with AsyncSessionLocal() as session:
        service = ChartIngestionService(
            session=session,
            quarantine_dir=quarantine_dir,
            manifest_dir=manifest_dir,
        )

        try:
            # First Run with Persist
            summary1 = await service.ingest_records(valid_batch, persist=True)
            assert summary1.valid_records == 2
            assert summary1.persisted_records == 2

            # Check DB Count
            count_res1 = await session.execute(
                select(func.count(ChartVacancyORM.id)).where(
                    ChartVacancyORM.train_number == "12002",
                    ChartVacancyORM.chart_date == datetime.date(2026, 11, 4),
                )
            )
            count1 = count_res1.scalar_one()
            assert count1 == 2

            # Second Run with exact same batch: must be idempotent!
            summary2 = await service.ingest_records(valid_batch, persist=True)
            assert summary2.valid_records == 2
            assert summary2.persisted_records == 2

            # Check DB Count after second run: must still be 2, no duplicates!
            count_res2 = await session.execute(
                select(func.count(ChartVacancyORM.id)).where(
                    ChartVacancyORM.train_number == "12002",
                    ChartVacancyORM.chart_date == datetime.date(2026, 11, 4),
                )
            )
            count2 = count_res2.scalar_one()
            assert count2 == 2

        finally:
            # Cleanup test records
            await session.execute(
                delete(ChartVacancyORM).where(
                    ChartVacancyORM.train_number == "12002",
                    ChartVacancyORM.chart_date == datetime.date(2026, 11, 4),
                )
            )
            await session.commit()

