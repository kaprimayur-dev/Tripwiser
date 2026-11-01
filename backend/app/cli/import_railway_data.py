"""
Administrative CLI tool for railway data ingestion into TripWiser PostgreSQL/PostGIS.

Usage:
    python -m app.cli.import_railway_data --source fixture --dry-run
    python -m app.cli.import_railway_data --source datameet --persist-all
"""

import argparse
import asyncio
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Union

from app.core.db import check_database_health
from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.infrastructure.adapters.datameet.station_adapter import DataMeetStationAdapter
from app.infrastructure.adapters.datameet.train_adapter import DataMeetTrainAdapter
from app.infrastructure.adapters.datameet.train_models import DataMeetTrainRecord
from app.infrastructure.adapters.datameet.schedule_adapter import DataMeetScheduleAdapter
from app.infrastructure.integration.calendar_provider import (
    FixtureCalendarProvider,
    JsonCalendarProvider,
    CompositeCalendarProvider,
)
from app.infrastructure.integration.models import (
    IntegratedRailwayDataset,
    IntegratedTrainRecord,
    IntegratedTrainSchedule,
    IntegratedScheduleStop,
)
from app.infrastructure.integration.service import RailwayDataIntegrationService
from app.infrastructure.manifest.manifest_service import ImportManifestService
from app.infrastructure.persistence.batch_persistence import RailwayDataPersistenceService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tripwiser-importer")

DEFAULT_FIXTURE_PATH = Path("backend/app/infrastructure/data/fixtures/bootstrap_railway_data.json")
DEFAULT_DATAMEET_DIR = Path("backend/app/infrastructure/data/sources/datameet")
DEFAULT_OFFICIAL_CALENDAR_PATH = Path("backend/app/infrastructure/data/sources/official/railway_running_calendars.json")


def resolve_source_path(p: Union[str, Path]) -> Path:
    """Resolves path supporting both host-relative and docker-relative working directories."""
    path = Path(p)
    if path.exists():
        return path
    parts = path.parts
    if parts and parts[0] == "backend":
        alt = Path(*parts[1:])
        if alt.exists():
            return alt
    return path




def parse_args(args: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TripWiser Administrative Railway Ingestion CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=["fixture", "datameet"],
        default="fixture",
        help="Source dataset to ingest: 'fixture' (curated 50 stations / 12 verified trains) or 'datameet' (full network)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute parsing, integration, and manifest generation without writing to the database",
    )
    parser.add_argument(
        "--persist-stations",
        action="store_true",
        help="Persist accepted stations into the database",
    )
    parser.add_argument(
        "--persist-trains",
        action="store_true",
        help="Persist Tier 2 compiled domain trains and schedules into the database",
    )
    parser.add_argument(
        "--persist-all",
        action="store_true",
        help="Persist both stations and compiled trains",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Batch chunk size for database bulk upsert operations",
    )
    parser.add_argument(
        "--manifest-dir",
        type=str,
        default="data/manifests",
        help="Directory to save cryptographic import manifests",
    )
    parser.add_argument(
        "--quarantine-dir",
        type=str,
        default="data/quarantine",
        help="Directory to export structured quarantine and uncompiled artifacts",
    )
    parser.add_argument(
        "--fixture-path",
        type=str,
        default=str(DEFAULT_FIXTURE_PATH),
        help="Path to curated bootstrap fixture JSON",
    )
    parser.add_argument(
        "--calendar-path",
        type=str,
        default=str(DEFAULT_OFFICIAL_CALENDAR_PATH),
        help="Path to verified official running calendar JSON dataset",
    )
    parser.add_argument(
        "--datameet-dir",
        type=str,
        default=str(DEFAULT_DATAMEET_DIR),
        help="Directory containing DataMeet sources (stations.json, trains.json, schedules.json)",
    )
    return parser.parse_args(args)


def load_fixture_dataset(fixture_path: Path) -> tuple[IntegratedRailwayDataset, list[Path]]:
    """Loads and compiles curated bootstrap fixture into an IntegratedRailwayDataset."""
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture file not found: {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Parse Stations
    stations: List[Station] = []
    for s in data.get("stations", []):
        stations.append(
            Station(
                code=s["code"],
                name=s["name"],
                latitude=float(s["latitude"]),
                longitude=float(s["longitude"]),
                state=s.get("state"),
                zone=s.get("zone"),
            )
        )

    # 2. Parse Active Verified Trains
    compiled_trains: List[Train] = []
    integrated_train_records: List[IntegratedTrainRecord] = []
    integrated_schedules: List[IntegratedTrainSchedule] = []
    all_stops: List[IntegratedScheduleStop] = []

    st_map = {s.code: s for s in stations}

    for t in data.get("trains", []):
        if t.get("verification_status") != "ROUTE_TABLE_VERIFIED":
            continue

        schedule_entries: List[TrainScheduleEntry] = []
        integrated_stops: List[IntegratedScheduleStop] = []

        for seq, entry in enumerate(t.get("schedule", []), start=1):
            arr_str = entry.get("arrival_time")
            dep_str = entry.get("departure_time")
            arr_t = datetime.time.fromisoformat(arr_str) if arr_str else None
            dep_t = datetime.time.fromisoformat(dep_str) if dep_str else None
            day_offset = int(entry["day_offset"])
            dist_km = float(entry["distance_km"])
            st_code = entry["station_code"]

            sch_entry = TrainScheduleEntry(
                station_code=st_code,
                arrival_time=arr_t,
                departure_time=dep_t,
                day_offset=day_offset,
                distance_km=dist_km,
                stop_sequence=entry.get("stop_sequence", seq),
            )
            schedule_entries.append(sch_entry)

            resolved_st = st_map.get(st_code)
            if not resolved_st:
                continue
            int_stop = IntegratedScheduleStop(
                source_record_id=entry.get("source_record_id", seq),
                train_number=t["number"],
                station_code=st_code,
                stop_sequence=entry.get("stop_sequence", seq),
                station=resolved_st,
                arrival_time=arr_t,
                departure_time=dep_t,
                day=day_offset + 1,
                day_offset=day_offset,
                distance_km=dist_km,
                is_commercial_halt=True,
                is_waypoint=False,
                is_timing_complete=True,
            )
            integrated_stops.append(int_stop)
            all_stops.append(int_stop)

        domain_train = Train(
            number=t["number"],
            name=t["name"],
            origin_code=t["origin_code"],
            destination_code=t["destination_code"],
            runs_on_days=list(t["runs_on_days"]),
            schedule=schedule_entries,
        )
        compiled_trains.append(domain_train)

        int_schedule = IntegratedTrainSchedule(
            train_number=t["number"],
            train_name=t["name"],
            origin_station=st_map[t["origin_code"]],
            destination_station=st_map[t["destination_code"]],
            total_stops=len(integrated_stops),
            stops=tuple(integrated_stops),
        )
        integrated_schedules.append(int_schedule)

        header = DataMeetTrainRecord(
            number=t["number"],
            name=t["name"],
            origin_code=t["origin_code"],
            destination_code=t["destination_code"],
        )
        train_rec = IntegratedTrainRecord(
            header=header,
            schedule=int_schedule,
            runs_on_days=tuple(t["runs_on_days"]),
            is_compilable_to_domain=True,
        )
        integrated_train_records.append(train_rec)

    dataset = IntegratedRailwayDataset(
        stations=tuple(stations),
        compiled_trains=tuple(compiled_trains),
        train_records=tuple(integrated_train_records),
        train_schedules=tuple(integrated_schedules),
        schedule_stops=tuple(all_stops),
    )
    return dataset, [fixture_path]


def load_datameet_dataset(
    datameet_dir: Path,
    fixture_path: Path,
    calendar_path: Path | None = None,
):
    """Loads and integrates DataMeet datasets with CompositeCalendarProvider."""
    st_path = datameet_dir / "stations.json"
    tr_path = datameet_dir / "trains.json"
    sch_path = datameet_dir / "schedules.json"

    for p in [st_path, tr_path, sch_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required DataMeet file missing: {p}")

    providers = [FixtureCalendarProvider(fixture_path)]
    source_files = [st_path, tr_path, sch_path, fixture_path]

    if calendar_path is not None and calendar_path.exists():
        logger.info("Configuring verified running calendar from %s", calendar_path)
        providers.append(JsonCalendarProvider(calendar_path))
        source_files.append(calendar_path)

    composite_calendar = CompositeCalendarProvider(providers)

    logger.info("Integrating multi-source dataset via RailwayDataIntegrationService.integrate()")
    integration_service = RailwayDataIntegrationService()
    dataset = integration_service.integrate(
        stations_source=st_path,
        trains_source=tr_path,
        schedules_source=sch_path,
        calendar_provider=composite_calendar,
    )
    return dataset, source_files


def print_summary_table(
    source_name: str,
    mode_str: str,
    dataset: IntegratedRailwayDataset,
    persisted_stations: int,
    persisted_trains: int,
    manifest_path: Path,
    quarantine_artifacts: Dict[str, Path],
    duration: float,
) -> None:
    width = 82
    print("\n" + "=" * width)
    print(f" TripWiser Railway Ingestion Summary".center(width))
    print(f" Source: {source_name.upper()} | Mode: {mode_str}".center(width))
    print("=" * width)
    print(f"{'Entity Category':<28} | {'Total':<14} | {'Accepted':<14} | {'Quarantined/Excluded':<18}")
    print("-" * width)

    tot_st = len(dataset.stations) + len(dataset.quarantined_stations)
    tot_tr = len(dataset.train_records) + len(dataset.quarantined_trains)
    tot_sch = len(dataset.schedule_stops) + len(dataset.quarantined_schedule_stops)

    print(f"{'Stations':<28} | {tot_st:<14,d} | {len(dataset.stations):<14,d} | {len(dataset.quarantined_stations):<18,d}")
    print(f"{'Train Headers':<28} | {tot_tr:<14,d} | {len(dataset.train_records):<14,d} | {len(dataset.quarantined_trains):<18,d}")
    print(f"{'Compiled Domain Trains':<28} | {len(dataset.train_records):<14,d} | {len(dataset.compiled_trains):<14,d} | {len(dataset.uncompiled_trains):<18,d}")
    print(f"{'Schedule Stops':<28} | {tot_sch:<14,d} | {len(dataset.schedule_stops):<14,d} | {len(dataset.quarantined_schedule_stops):<18,d}")
    print("-" * width)
    print(f" Database Persistence:  Stations: {persisted_stations:,d} | Trains: {persisted_trains:,d}")
    print(f" Audit Manifest:        {manifest_path}")
    print(f" Quarantine Directory:  {manifest_path.parent / '..' / 'quarantine'}")
    print(f" Status:                SUCCESS (Execution took {duration:.2f}s)")
    print("=" * width + "\n")


async def run_pipeline(args: argparse.Namespace) -> int:
    start_time = time.time()
    source = args.source
    dry_run = args.dry_run

    # Determine persistence flags
    if dry_run:
        persist_stations = False
        persist_trains = False
        mode_str = "DRY-RUN (No Database Changes)"
    else:
        if args.persist_all or (not args.persist_stations and not args.persist_trains):
            persist_stations = True
            persist_trains = True
        else:
            persist_stations = args.persist_stations
            persist_trains = args.persist_trains
        mode_str = f"PERSISTENCE (Stations={persist_stations}, Trains={persist_trains})"

    logger.info("Beginning TripWiser ingestion pipeline: source=%s, mode=%s", source, mode_str)

    # 1. Load & Integrate Dataset
    fixture_path = resolve_source_path(args.fixture_path)
    if source == "fixture":
        dataset, source_files = load_fixture_dataset(fixture_path)
    else:
        datameet_dir = resolve_source_path(args.datameet_dir)
        calendar_path = resolve_source_path(args.calendar_path) if args.calendar_path else None
        dataset, source_files = load_datameet_dataset(datameet_dir, fixture_path, calendar_path)

    # 2. Database Persistence
    persisted_st = 0
    persisted_tr = 0
    if not dry_run and (persist_stations or persist_trains):
        logger.info("Checking database connectivity and PostGIS health...")
        db_healthy = await check_database_health()
        if not db_healthy:
            logger.error("PostgreSQL database is unhealthy or unreachable. Aborting persistence.")
            return 1

        persistence_service = RailwayDataPersistenceService()
        logger.info("Persisting dataset into PostgreSQL/PostGIS...")
        persisted_st, persisted_tr = await persistence_service.persist_dataset(
            dataset=dataset,
            persist_stations=persist_stations,
            persist_trains=persist_trains,
            chunk_size=args.chunk_size,
        )
        logger.info("Persistence complete: %d stations, %d trains", persisted_st, persisted_tr)

    # 3. Manifest & Quarantine Export
    duration = time.time() - start_time
    manifest_service = ImportManifestService()
    manifest_dict = manifest_service.generate_manifest(
        dataset=dataset,
        source_paths=source_files,
        dry_run=dry_run,
        persisted_stations=persisted_st,
        persisted_trains=persisted_tr,
        duration_sec=duration,
    )

    manifest_dir = Path(args.manifest_dir)
    quarantine_dir = Path(args.quarantine_dir)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    manifest_path = manifest_service.save_manifest(
        manifest_dict, manifest_dir / f"import_manifest_{ts}.json"
    )
    quarantine_artifacts = manifest_service.export_quarantine_artifacts(dataset, quarantine_dir)

    # 4. Print Summary Table
    print_summary_table(
        source_name=source,
        mode_str=mode_str,
        dataset=dataset,
        persisted_stations=persisted_st,
        persisted_trains=persisted_tr,
        manifest_path=manifest_path,
        quarantine_artifacts=quarantine_artifacts,
        duration=duration,
    )

    return 0


def main() -> None:
    parsed_args = parse_args()
    code = asyncio.run(run_pipeline(parsed_args))
    sys.exit(code)


if __name__ == "__main__":
    main()
