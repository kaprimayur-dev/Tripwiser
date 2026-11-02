"""
Unit tests for the TripWiser Administrative Ingestion CLI.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.cli.import_railway_data import parse_args, load_fixture_dataset, run_pipeline
from app.infrastructure.integration.models import (
    IntegratedRailwayDataset,
)

FIXTURE_PATH = Path("backend/app/infrastructure/data/fixtures/bootstrap_railway_data.json")
if not FIXTURE_PATH.exists():
    FIXTURE_PATH = Path("app/infrastructure/data/fixtures/bootstrap_railway_data.json")


class TestImportCLIUnit:
    """Verifies argument parsing, flag behavior, and pipeline flow in isolation."""

    def test_default_cli_arguments(self):
        args = parse_args([])
        assert args.source == "fixture"
        assert args.dry_run is False
        assert args.persist_stations is False
        assert args.persist_trains is False
        assert args.persist_all is False
        assert args.chunk_size == 1000
        assert args.manifest_dir == "data/manifests"
        assert args.quarantine_dir == "data/quarantine"
        assert "railway_running_calendars.json" in str(args.calendar_path)

    def test_custom_cli_arguments(self):
        custom = [
            "--source", "datameet",
            "--dry-run",
            "--persist-stations",
            "--chunk-size", "500",
            "--manifest-dir", "custom/manifests",
            "--quarantine-dir", "custom/quarantine",
            "--calendar-path", "custom/calendars.json",
        ]
        args = parse_args(custom)
        assert args.source == "datameet"
        assert args.dry_run is True
        assert args.persist_stations is True
        assert args.chunk_size == 500
        assert args.manifest_dir == "custom/manifests"
        assert args.quarantine_dir == "custom/quarantine"
        assert args.calendar_path == "custom/calendars.json"

    def test_invalid_source_argument(self):
        with pytest.raises(SystemExit):
            parse_args(["--source", "invalid_source"])

    @pytest.mark.skipif(not FIXTURE_PATH.exists(), reason="Bootstrap fixture required")
    def test_load_fixture_dataset(self):
        dataset, source_files = load_fixture_dataset(FIXTURE_PATH)
        assert isinstance(dataset, IntegratedRailwayDataset)
        assert len(dataset.stations) == 50
        assert len(dataset.compiled_trains) == 12
        assert len(dataset.train_records) == 12
        assert len(source_files) == 1
        assert source_files[0] == FIXTURE_PATH

    @pytest.mark.asyncio
    @pytest.mark.skipif(not FIXTURE_PATH.exists(), reason="Bootstrap fixture required")
    async def test_run_pipeline_dry_run_fixture(self, tmp_path):
        manifest_dir = tmp_path / "manifests"
        quarantine_dir = tmp_path / "quarantine"

        args = parse_args([
            "--source", "fixture",
            "--dry-run",
            "--fixture-path", str(FIXTURE_PATH),
            "--manifest-dir", str(manifest_dir),
            "--quarantine-dir", str(quarantine_dir),
        ])

        exit_code = await run_pipeline(args)
        assert exit_code == 0
        assert manifest_dir.exists()
        manifest_files = list(manifest_dir.glob("*.json"))
        assert len(manifest_files) == 1
        assert quarantine_dir.exists()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not FIXTURE_PATH.exists(), reason="Bootstrap fixture required")
    async def test_dry_run_flag_strictly_prevents_persistence(self, tmp_path):
        manifest_dir = tmp_path / "manifests"
        quarantine_dir = tmp_path / "quarantine"

        args = parse_args([
            "--source", "fixture",
            "--dry-run",
            "--persist-all",  # Even if persist-all is passed, dry-run must override
            "--fixture-path", str(FIXTURE_PATH),
            "--manifest-dir", str(manifest_dir),
            "--quarantine-dir", str(quarantine_dir),
        ])

        with patch("app.cli.import_railway_data.RailwayDataPersistenceService") as mock_service_cls:
            exit_code = await run_pipeline(args)
            assert exit_code == 0
            # RailwayDataPersistenceService must NOT be instantiated
            mock_service_cls.assert_not_called()

