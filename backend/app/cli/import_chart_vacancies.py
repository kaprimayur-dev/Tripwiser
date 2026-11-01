"""
Administrative CLI tool for authentic chart vacancy ingestion into TripWiser PostgreSQL.
Usage:
    python -m app.cli.import_chart_vacancies --input <path_to_json> --dry-run
    python -m app.cli.import_chart_vacancies --input <path_to_json> --persist
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from app.core.db import AsyncSessionLocal, check_database_health
from app.infrastructure.adapters.chart.chart_ingestion_service import ChartIngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tripwiser-chart-importer")


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TripWiser Administrative Chart Vacancy Ingestion CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to JSON file containing verified chart vacancy records",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate records, generate quarantine and manifest, but do not write to database",
    )
    group.add_argument(
        "--persist",
        action="store_true",
        help="Persist validated records into PostgreSQL chart_vacancies table",
    )
    parser.add_argument(
        "--source-label",
        type=str,
        default="administrative_chart_dump",
        help="Audit provenance label for the imported batch",
    )
    return parser.parse_args(args)


async def run_import(input_path: Path, persist: bool, source_label: str) -> int:
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        return 1

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as ex:
        logger.error("Failed to parse JSON file: %s", ex)
        return 1

    if not isinstance(data, list):
        logger.error("Expected JSON array of vacancy objects, got %s", type(data).__name__)
        return 1

    logger.info("Connecting to database...")
    is_healthy = await check_database_health()
    if not is_healthy:
        logger.error("Database connection failed. Ensure PostgreSQL is running.")
        return 1

    async with AsyncSessionLocal() as session:
        service = ChartIngestionService(session=session)
        summary = await service.ingest_records(
            records=data,
            persist=persist,
            source_label=source_label,
        )

    # Print summary table
    print("\n" + "=" * 65)
    print("      TRIPWISER CHART VACANCY INGESTION SUMMARY")
    print("=" * 65)
    print(f" Execution Mode        : {'PERSIST (Database Updated)' if persist else 'DRY RUN (Validation Only)'}")
    print(f" Source Label          : {source_label}")
    print(f" Total Input Records   : {summary.total_records}")
    print(f" Valid Records         : {summary.valid_records}")
    print(f" Quarantined Records   : {summary.quarantined_records}")
    print(f" Persisted to DB       : {summary.persisted_records}")
    print(f" Manifest SHA-256 File : {summary.manifest_path or 'None'}")
    print(f" Quarantine Dump File  : {summary.quarantine_path or 'None (Clean batch)'}")
    print(f" Total Duration        : {summary.duration_seconds:.3f}s")
    print("=" * 65 + "\n")

    return 0


def main():
    args = parse_args()
    exit_code = asyncio.run(run_import(args.input, args.persist, args.source_label))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

