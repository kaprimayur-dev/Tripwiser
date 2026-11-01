"""
Administrative CLI tool for executing comprehensive railway data quality audits (TW-115).
Runs deterministic validation across Stations, Trains, Schedules, and Operating Calendars,
and produces machine-readable JSON and human-readable Markdown reports.

Usage:
    python -m app.cli.audit_data_quality
    python -m app.cli.audit_data_quality --format both --out-dir backend/data/reports
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

from app.domain.models.data_quality import (
    QualitySeverity,
    QualityStatus,
    CategoryQualitySummary,
    DataQualityAuditSummary,
)
from app.domain.services.data_quality_engine import DataQualityEngine
from app.infrastructure.adapters.datameet.station_adapter import DataMeetStationAdapter
from app.infrastructure.adapters.datameet.train_adapter import DataMeetTrainAdapter
from app.infrastructure.adapters.datameet.schedule_adapter import DataMeetScheduleAdapter
from app.infrastructure.integration.calendar_provider import JsonCalendarProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tripwiser-quality-auditor")


def resolve_path(p: Path | str) -> Path:
    path = Path(p)
    if path.exists():
        return path
    parts = path.parts
    if parts and parts[0] == "backend":
        alt = Path(*parts[1:])
        if alt.exists():
            return alt
        # For output paths where directory may not exist yet, check if cwd is already in backend
        if Path("app").exists() and Path("alembic.ini").exists():
            return alt
    return path


def run_audit(
    datameet_dir: Path,
    calendar_path: Path,
    out_dir: Path,
    format_type: str = "both",
) -> DataQualityAuditSummary:
    """
    Executes a complete data quality audit of all stations, trains, schedules,
    and running day calendars.
    """
    engine = DataQualityEngine()

    stations_file = resolve_path(datameet_dir / "stations.json")
    trains_file = resolve_path(datameet_dir / "trains.json")
    schedules_file = resolve_path(datameet_dir / "schedules.json")
    calendar_file = resolve_path(calendar_path)

    logger.info(f"Auditing Stations from: {stations_file}")
    logger.info(f"Auditing Trains from: {trains_file}")
    logger.info(f"Auditing Schedules from: {schedules_file}")
    logger.info(f"Auditing Calendars from: {calendar_file}")

    # ==========================================
    # 1. Ingest & Audit Stations
    # ==========================================
    station_adapter = DataMeetStationAdapter()
    station_result = station_adapter.adapt(stations_file)

    stn_summary = CategoryQualitySummary(total_inspected=len(station_result.records) + len(station_result.quarantined))
    seen_stn_codes: Set[str] = set()

    for stn in station_result.records:
        status = engine.validate_station(stn, seen_codes=seen_stn_codes, source_ref="stations.json")
        if status == QualityStatus.VALID:
            stn_summary.valid_count += 1
        elif status == QualityStatus.REVIEW_REQUIRED:
            stn_summary.review_required_count += 1
        elif status == QualityStatus.REJECTED:
            stn_summary.rejected_count += 1

    # Add quarantined records from adapter
    for q in station_result.quarantined:
        stn_summary.rejected_count += 1
        engine.validate_station(
            {
                "code": q.original_station_code,
                "name": q.original_station_name,
                "latitude": None,
                "longitude": None,
                "state": None,
            },
            seen_codes=seen_stn_codes,
            source_ref="stations.json:quarantine",
        )

    valid_stn_codes = set(seen_stn_codes)
    logger.info(f"Stations Audit: {stn_summary.total_inspected} inspected, {stn_summary.valid_count} valid, {stn_summary.rejected_count} rejected")

    # ==========================================
    # 2. Ingest & Audit Trains
    # ==========================================
    train_adapter = DataMeetTrainAdapter()
    train_result = train_adapter.adapt(trains_file, valid_station_codes=valid_stn_codes)

    trn_summary = CategoryQualitySummary(total_inspected=len(train_result.records) + len(train_result.quarantined))
    seen_trn_numbers: Set[str] = set()

    for trn in train_result.records:
        status = engine.validate_train_header(
            train_number=trn.number,
            train_name=trn.name,
            origin_code=trn.origin_code,
            destination_code=trn.destination_code,
            valid_station_codes=valid_stn_codes,
            seen_train_numbers=seen_trn_numbers,
            source_ref="trains.json",
        )
        if status == QualityStatus.VALID:
            trn_summary.valid_count += 1
        elif status == QualityStatus.REVIEW_REQUIRED:
            trn_summary.review_required_count += 1
        elif status == QualityStatus.REJECTED:
            trn_summary.rejected_count += 1

    for q in train_result.quarantined:
        trn_summary.rejected_count += 1
        engine.validate_train_header(
            train_number=q.original_train_number or "UNKNOWN",
            train_name=q.original_train_name or "",
            origin_code="UNKNOWN",
            destination_code="UNKNOWN",
            valid_station_codes=valid_stn_codes,
            seen_train_numbers=seen_trn_numbers,
            source_ref="trains.json:quarantine",
        )

    valid_trn_numbers = set(seen_trn_numbers)
    logger.info(f"Trains Audit: {trn_summary.total_inspected} inspected, {trn_summary.valid_count} valid, {trn_summary.rejected_count} rejected")

    # ==========================================
    # 3. Ingest & Audit Schedules
    # ==========================================
    train_map = {t.number: t for t in train_result.records}
    schedule_adapter = DataMeetScheduleAdapter()
    schedule_result = schedule_adapter.adapt(
        schedules_file,
        valid_station_codes=valid_stn_codes,
        valid_train_numbers=valid_trn_numbers,
        train_metadata=train_map,
    )

    sch_summary = CategoryQualitySummary(
        total_inspected=len(schedule_result.train_schedules) + len(schedule_result.quarantined)
    )

    for sched in schedule_result.train_schedules:
        trn_meta = train_map.get(sched.train_number)
        expected_orig = trn_meta.origin_code if trn_meta else None
        expected_dest = trn_meta.destination_code if trn_meta else None

        status = engine.validate_train_schedule(
            train_number=sched.train_number,
            stops=sched.entries,
            valid_station_codes=valid_stn_codes,
            expected_origin=expected_orig,
            expected_dest=expected_dest,
            source_ref="schedules.json",
        )
        if status == QualityStatus.VALID:
            sch_summary.valid_count += 1
        elif status == QualityStatus.RETAINED_INCOMPLETE:
            sch_summary.retained_incomplete_count += 1
        elif status == QualityStatus.REVIEW_REQUIRED:
            sch_summary.review_required_count += 1
        elif status == QualityStatus.REJECTED:
            sch_summary.rejected_count += 1

    sch_summary.rejected_count += len(schedule_result.quarantined)

    logger.info(
        f"Schedules Audit: {sch_summary.total_inspected} train schedules inspected, "
        f"{sch_summary.valid_count} valid, {sch_summary.retained_incomplete_count} incomplete, "
        f"{sch_summary.rejected_count} rejected"
    )

    # ==========================================
    # 4. Ingest & Audit Running Calendars
    # ==========================================
    cal_summary = CategoryQualitySummary(total_inspected=len(valid_trn_numbers))
    calendar_provider = JsonCalendarProvider(calendar_file) if calendar_file.exists() else None

    raw_calendar_entries: Dict[str, Any] = {}
    if calendar_file.exists():
        try:
            with open(calendar_file, "r", encoding="utf-8") as f:
                cal_data = json.load(f)
                if isinstance(cal_data, list):
                    for item in cal_data:
                        t_num = str(item.get("train_number", "")).strip()
                        if t_num:
                            raw_calendar_entries[t_num] = item
                elif isinstance(cal_data, dict):
                    raw_calendar_entries = cal_data
        except Exception as e:
            logger.warning(f"Error reading raw calendar file: {e}")

    for t_num in valid_trn_numbers:
        days = calendar_provider.get_running_days(t_num) if calendar_provider else None
        entry = raw_calendar_entries.get(t_num)

        status = engine.validate_running_calendar(
            train_number=t_num,
            runs_on_days=days,
            calendar_entry=entry,
            source_ref="railway_running_calendars.json",
        )
        if status == QualityStatus.VALID:
            cal_summary.valid_count += 1
        elif status == QualityStatus.REVIEW_REQUIRED:
            cal_summary.review_required_count += 1
        elif status == QualityStatus.REJECTED:
            cal_summary.rejected_count += 1

    logger.info(
        f"Calendars Audit: {cal_summary.total_inspected} train calendars inspected, "
        f"{cal_summary.valid_count} verified, {cal_summary.review_required_count} awaiting calendar"
    )

    # ==========================================
    # 5. Compile Summary & Artifacts
    # ==========================================
    source_artifacts = {
        "stations.json": str(stations_file),
        "trains.json": str(trains_file),
        "schedules.json": str(schedules_file),
        "railway_running_calendars.json": str(calendar_file),
    }

    summary = engine.compile_audit_report(
        stations_summary=stn_summary,
        trains_summary=trn_summary,
        schedules_summary=sch_summary,
        calendars_summary=cal_summary,
        source_artifacts=source_artifacts,
    )

    out_dir_path = resolve_path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    # Export machine-readable JSON
    if format_type in ("json", "both"):
        json_path = out_dir_path / "data_quality_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(), f, indent=2)
        logger.info(f"Saved machine-readable quality report to: {json_path}")

    # Export human-readable Markdown
    if format_type in ("markdown", "both"):
        md_path = out_dir_path / "DATA_QUALITY_REPORT.md"
        md_content = generate_markdown_report(summary)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"Saved human-readable quality report to: {md_path}")

        # Also copy to root for immediate review
        root_md_path = Path("DATA_QUALITY_REPORT.md")
        try:
            with open(root_md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            logger.info(f"Copied quality report to repository root: {root_md_path}")
        except Exception as err:
            logger.warning(f"Could not write root DATA_QUALITY_REPORT.md: {err}")

    return summary


def generate_markdown_report(summary: DataQualityAuditSummary) -> str:
    """Generates an administrative markdown audit report from the summary model."""
    top_failures_md = "\n".join(
        f"| `{r['rule_code']}` | **{r['count']:,}** |"
        for r in summary.top_failure_rules
    )

    return f"""# TripWiser Railway Data Quality & Trust Audit (TW-115)

**Report ID**: `{summary.report_id}`  
**Generated At**: `{summary.generated_at}`  
**Total Records Inspected**: **{summary.total_records_inspected:,}**  
**Reproducibility SHA-256**: `{summary.reproducibility_hash}`  

---

## 1. Executive Summary & Quality Classification

| Category | Inspected | Valid | Retained Incomplete | Review Required | Rejected / Quarantined |
|---|---|---|---|---|---|
| **Stations** | {summary.stations.total_inspected:,} | {summary.stations.valid_count:,} | {summary.stations.retained_incomplete_count:,} | {summary.stations.review_required_count:,} | {summary.stations.rejected_count:,} |
| **Trains (Headers)** | {summary.trains.total_inspected:,} | {summary.trains.valid_count:,} | {summary.trains.retained_incomplete_count:,} | {summary.trains.review_required_count:,} | {summary.trains.rejected_count:,} |
| **Train Schedules** | {summary.schedules.total_inspected:,} | {summary.schedules.valid_count:,} | {summary.schedules.retained_incomplete_count:,} | {summary.schedules.review_required_count:,} | {summary.schedules.rejected_count:,} |
| **Running Calendars** | {summary.calendars.total_inspected:,} | {summary.calendars.valid_count:,} | {summary.calendars.retained_incomplete_count:,} | {summary.calendars.review_required_count:,} | {summary.calendars.rejected_count:,} |

---

## 2. Findings by Severity Level

- **CRITICAL**: **{summary.findings_by_severity.get("CRITICAL", 0):,}** (Unusable / null geometry / missing identifier)
- **ERROR**: **{summary.findings_by_severity.get("ERROR", 0):,}** (Logical integrity / unresolved foreign references / out-of-bounds coords)
- **WARNING**: **{summary.findings_by_severity.get("WARNING", 0):,}** (Suspicious anomaly / awaiting running calendar / missing state)
- **INFO**: **{summary.findings_by_severity.get("INFO", 0):,}** (Incomplete timing / technical waypoint / zero dwell)

---

## 3. Top Validation Failure Rules

| Validation Rule Code | Occurrences |
|---|---|
{top_failures_md}

---

## 4. Source Data Provenance & Freshness Statement

> [!IMPORTANT]
> **Data Freshness Policy**:  
> {summary.data_freshness_statement}

### Audited Source Artifacts:
{chr(10).join(f"- **`{k}`**: `{v}`" for k, v in summary.source_artifacts.items())}

---

## 5. Route Engine Protection Guarantee

- **Compiled Domain Models Only**: The Route Discovery Engine queries exclusively compiled domain trains with verified operating calendars (`runs_on_days`) and monotonic stop sequences.
- **Fail-Safe Integrity**: Any schedule stop with unverified station references, invalid times, or missing day offsets is automatically quarantined and excluded from passenger itinerary construction.
- **Honest Disclaimers**: Disclaimers and timetable badges are rendered on the passenger frontend, making it explicit that results represent scheduled timetables rather than real-time tracking or seat availability feeds.
"""


def main():
    parser = argparse.ArgumentParser(description="TripWiser Data Quality Audit CLI")
    parser.add_argument(
        "--datameet-dir",
        type=Path,
        default=Path("backend/app/infrastructure/data/sources/datameet"),
        help="Path to directory containing datameet JSON files",
    )
    parser.add_argument(
        "--calendar-path",
        type=Path,
        default=Path("backend/app/infrastructure/data/sources/official/railway_running_calendars.json"),
        help="Path to verified running calendars JSON file",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("backend/data/reports"),
        help="Output directory for quality audit reports",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "both"],
        default="both",
        help="Report export format",
    )

    args = parser.parse_args()

    try:
        run_audit(
            datameet_dir=args.datameet_dir,
            calendar_path=args.calendar_path,
            out_dir=args.out_dir,
            format_type=args.format,
        )
        logger.info("Data Quality Audit completed successfully.")
    except Exception as exc:
        logger.error(f"Data Quality Audit failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
