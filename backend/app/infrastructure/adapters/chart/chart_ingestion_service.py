import datetime
import hashlib
import json
import os
import time
from typing import Any, Mapping, Sequence
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.station import StationORM
from app.infrastructure.database.models.train import TrainORM
from app.infrastructure.database.models.vacancy import ChartVacancyORM
from app.infrastructure.adapters.chart.chart_models import (
    ChartQuarantineRecord,
    ChartIngestionSummary,
)


class ChartIngestionService:
    """
    Validates, quarantines, audits, and idempotently persists chart vacancy records
    from verified offline dumps or administrative feeds.
    """

    def __init__(
        self,
        session: AsyncSession,
        quarantine_dir: str = "data/quarantine/chart_vacancies",
        manifest_dir: str = "data/manifests/chart_vacancies",
    ):
        self.session = session
        self.quarantine_dir = quarantine_dir
        self.manifest_dir = manifest_dir

    async def ingest_records(
        self,
        records: Sequence[Mapping[str, Any]],
        persist: bool = True,
        source_label: str = "administrative_chart_dump",
    ) -> ChartIngestionSummary:
        start_time = time.perf_counter()
        total_records = len(records)

        # 1. Cache existing stations and trains for foreign-key validation
        station_codes_res = await self.session.execute(select(StationORM.code))
        valid_station_codes = set(station_codes_res.scalars().all())

        train_numbers_res = await self.session.execute(select(TrainORM.number))
        valid_train_numbers = set(train_numbers_res.scalars().all())

        valid_records: list[dict[str, Any]] = []
        quarantine_records: list[ChartQuarantineRecord] = []
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        # 2. Validation loop
        for idx, rec in enumerate(records):
            reason = self._validate_record(rec, valid_station_codes, valid_train_numbers)
            if reason:
                quarantine_records.append(
                    ChartQuarantineRecord(
                        record_index=idx,
                        train_number=rec.get("train_number"),
                        chart_date=str(rec.get("chart_date")),
                        coach=rec.get("coach"),
                        berth_number=rec.get("berth_number"),
                        from_station=rec.get("from_station_code"),
                        to_station=rec.get("to_station_code"),
                        exclusion_reason=reason,
                        raw_payload=dict(rec),
                        quarantined_at=now_utc,
                    )
                )
            else:
                # Parse validated record
                parsed = self._normalize_record(rec, source_label, now_utc)
                valid_records.append(parsed)

        # 3. Write Quarantine if errors exist
        quarantine_path = None
        if quarantine_records:
            os.makedirs(self.quarantine_dir, exist_ok=True)
            ts_str = now_utc.strftime("%Y%m%d_%H%M%S")
            quarantine_path = os.path.join(
                self.quarantine_dir, f"quarantine_chart_vacancies_{ts_str}.json"
            )
            with open(quarantine_path, "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "record_index": q.record_index,
                            "train_number": q.train_number,
                            "chart_date": q.chart_date,
                            "coach": q.coach,
                            "berth_number": q.berth_number,
                            "from_station": q.from_station,
                            "to_station": q.to_station,
                            "exclusion_reason": q.exclusion_reason,
                            "raw_payload": dict(q.raw_payload),
                            "quarantined_at": q.quarantined_at.isoformat(),
                        }
                        for q in quarantine_records
                    ],
                    f,
                    indent=2,
                )

        # 4. Write Manifest
        manifest_path = None
        if valid_records or quarantine_records:
            os.makedirs(self.manifest_dir, exist_ok=True)
            ts_str = now_utc.strftime("%Y%m%d_%H%M%S")
            manifest_path = os.path.join(
                self.manifest_dir, f"manifest_chart_vacancies_{ts_str}.json"
            )
            raw_serialized = json.dumps(
                [
                    {k: str(v) for k, v in r.items()}
                    for r in valid_records
                ],
                sort_keys=True,
            ).encode("utf-8")
            payload_sha256 = hashlib.sha256(raw_serialized).hexdigest()

            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "source_label": source_label,
                        "created_at": now_utc.isoformat(),
                        "total_input_records": total_records,
                        "valid_records_count": len(valid_records),
                        "quarantined_records_count": len(quarantine_records),
                        "sha256_checksum": payload_sha256,
                        "quarantine_file": quarantine_path,
                    },
                    f,
                    indent=2,
                )

        # 5. Idempotent Database Upsert (if persist is True)
        persisted_count = 0
        if persist and valid_records:
            chunk_size = 500
            for i in range(0, len(valid_records), chunk_size):
                chunk = valid_records[i : i + chunk_size]
                insert_stmt = postgresql.insert(ChartVacancyORM).values(chunk)
                upsert_stmt = insert_stmt.on_conflict_do_update(
                    constraint="uq_chart_vacancies_segment",
                    set_={
                        "status": insert_stmt.excluded.status,
                        "observed_at": insert_stmt.excluded.observed_at,
                        "expires_at": insert_stmt.excluded.expires_at,
                        "chart_phase": insert_stmt.excluded.chart_phase,
                        "source": insert_stmt.excluded.source,
                        "berth_type": insert_stmt.excluded.berth_type,
                        "travel_class": insert_stmt.excluded.travel_class,
                    },
                )
                await self.session.execute(upsert_stmt)
            await self.session.commit()
            persisted_count = len(valid_records)

        duration = time.perf_counter() - start_time
        return ChartIngestionSummary(
            total_records=total_records,
            valid_records=len(valid_records),
            quarantined_records=len(quarantine_records),
            persisted_records=persisted_count,
            manifest_path=manifest_path,
            quarantine_path=quarantine_path,
            duration_seconds=duration,
        )

    def _validate_record(
        self,
        rec: Mapping[str, Any],
        valid_stations: set[str],
        valid_trains: set[str],
    ) -> str | None:
        train_num = str(rec.get("train_number", "")).strip()
        if not train_num:
            return "Missing train_number"
        if train_num not in valid_trains:
            return f"Train number '{train_num}' does not exist in trains table"

        from_st = str(rec.get("from_station_code", "")).strip().upper()
        if not from_st or from_st not in valid_stations:
            return f"Origin station '{from_st}' does not exist in stations table"

        to_st = str(rec.get("to_station_code", "")).strip().upper()
        if not to_st or to_st not in valid_stations:
            return f"Destination station '{to_st}' does not exist in stations table"

        if from_st == to_st:
            return f"from_station_code and to_station_code cannot be identical ('{from_st}')"

        try:
            from_seq = int(rec.get("from_sequence", 0))
            to_seq = int(rec.get("to_sequence", 0))
            if from_seq <= 0 or to_seq <= 0:
                return "Sequence values must be positive integers"
            if to_seq <= from_seq:
                return f"to_sequence ({to_seq}) must be greater than from_sequence ({from_seq})"
        except (ValueError, TypeError):
            return "Non-integer sequence values"

        try:
            berth_no = int(rec.get("berth_number", 0))
            if berth_no <= 0 or berth_no > 120:
                return f"Berth number {berth_no} is outside valid coach range (1-120)"
        except (ValueError, TypeError):
            return "Non-integer berth_number"

        coach = str(rec.get("coach", "")).strip()
        if not coach:
            return "Missing coach designation"

        chart_dt = rec.get("chart_date")
        if not chart_dt:
            return "Missing chart_date"
        try:
            if isinstance(chart_dt, str):
                datetime.date.fromisoformat(chart_dt)
        except ValueError:
            return f"Invalid chart_date format '{chart_dt}', expected YYYY-MM-DD"

        return None

    def _normalize_record(
        self,
        rec: Mapping[str, Any],
        source_label: str,
        now_utc: datetime.datetime,
    ) -> dict[str, Any]:
        chart_dt = rec["chart_date"]
        if isinstance(chart_dt, str):
            chart_date_obj = datetime.date.fromisoformat(chart_dt)
        else:
            chart_date_obj = chart_dt

        expires_val = rec.get("expires_at")
        if expires_val:
            if isinstance(expires_val, str):
                expires_dt = datetime.datetime.fromisoformat(expires_val.replace("Z", "+00:00"))
            else:
                expires_dt = expires_val
        else:
            expires_dt = now_utc + datetime.timedelta(hours=6)

        return {
            "train_number": str(rec["train_number"]).strip(),
            "chart_date": chart_date_obj,
            "coach": str(rec["coach"]).strip().upper(),
            "berth_number": int(rec["berth_number"]),
            "berth_type": str(rec.get("berth_type", "UB")).strip().upper(),
            "travel_class": str(rec.get("travel_class", "3A")).strip().upper(),
            "from_station_code": str(rec["from_station_code"]).strip().upper(),
            "to_station_code": str(rec["to_station_code"]).strip().upper(),
            "from_sequence": int(rec["from_sequence"]),
            "to_sequence": int(rec["to_sequence"]),
            "source": str(rec.get("source", source_label)).strip(),
            "chart_phase": str(rec.get("chart_phase", "FIRST_CHART")).strip(),
            "status": str(rec.get("status", "VACANT")).strip().upper(),
            "observed_at": now_utc,
            "expires_at": expires_dt,
        }

