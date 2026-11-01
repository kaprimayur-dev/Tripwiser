import json
import pytest
from pathlib import Path
from app.cli.import_chart_vacancies import parse_args, run_import


def test_import_chart_vacancies_cli_arg_parsing():
    # Dry run
    args_dry = parse_args(["--input", "some/path.json", "--dry-run"])
    assert args_dry.input == Path("some/path.json")
    assert args_dry.dry_run is True
    assert args_dry.persist is False

    # Persist
    args_persist = parse_args(["--input", "some/path.json", "--persist", "--source-label", "custom_audit"])
    assert args_persist.persist is True
    assert args_persist.dry_run is False
    assert args_persist.source_label == "custom_audit"


@pytest.mark.asyncio
async def test_import_chart_vacancies_cli_file_not_found():
    exit_code = await run_import(
        input_path=Path("non_existent_file_xyz.json"),
        persist=False,
        source_label="test",
    )
    assert exit_code == 1


@pytest.mark.asyncio
async def test_import_chart_vacancies_cli_dry_run_execution(tmp_path):
    test_file = tmp_path / "test_vacancies.json"
    records = [
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
            "source": "cli_dry_run_test",
        }
    ]
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(records, f)

    exit_code = await run_import(
        input_path=test_file,
        persist=False,
        source_label="cli_test",
    )
    assert exit_code == 0

