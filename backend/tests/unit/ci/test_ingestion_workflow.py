"""
Unit tests validating the GitHub Actions Production Railway Data Ingestion workflow.
Verifies workflow structure, safety gates, triggers, exclusivity, and CLI command parity.
"""

from pathlib import Path
import yaml
import pytest


CANDIDATE_PATHS = [
    Path(".github/workflows/production-railway-import.yml"),
    Path("../.github/workflows/production-railway-import.yml"),
    Path(__file__).parent / "production-railway-import.yml",
    Path("tests/unit/ci/production-railway-import.yml"),
]

WORKFLOW_PATH = next((p for p in CANDIDATE_PATHS if p.exists()), None)


@pytest.fixture
def workflow_data():
    assert WORKFLOW_PATH is not None and WORKFLOW_PATH.exists(), "Workflow file not found in candidate paths"
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_workflow_triggers(workflow_data):
    return workflow_data.get("on") or workflow_data.get(True) or {}


def test_workflow_triggers_strictly_manual(workflow_data):
    """Workflow must only be triggered manually via workflow_dispatch."""
    triggers = get_workflow_triggers(workflow_data)
    assert "workflow_dispatch" in triggers, "Must have workflow_dispatch trigger"
    assert "push" not in triggers, "Must NEVER trigger automatically on push"
    assert "pull_request" not in triggers, "Must NEVER trigger on pull_request"
    assert "schedule" not in triggers, "Must NEVER trigger on schedule"


def test_workflow_dry_run_input_defaults_to_true(workflow_data):
    """dry_run input must default to true for safety."""
    triggers = get_workflow_triggers(workflow_data)
    inputs = triggers["workflow_dispatch"].get("inputs", {})
    assert "dry_run" in inputs, "Must declare dry_run input"
    assert inputs["dry_run"]["default"] is True, "dry_run default must be True"
    assert inputs["dry_run"]["type"] == "boolean"


def test_workflow_permissions_and_concurrency(workflow_data):
    """Workflow must have read-only contents permission and concurrency locking."""
    permissions = workflow_data.get("permissions", {})
    assert permissions.get("contents") == "read", "Permissions must be read-only"

    concurrency = workflow_data.get("concurrency", {})
    assert concurrency.get("group") == "production-railway-import"
    assert concurrency.get("cancel-in-progress") is False


def test_workflow_job_configuration(workflow_data):
    """Verify job runner, timeout, Python version, and execution steps."""
    job = workflow_data["jobs"]["ingest"]
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] == 15

    steps = job["steps"]
    step_names = [s.get("name", "") for s in steps]

    # Verify key steps exist
    assert any("Checkout Code" in name for name in step_names)
    assert any("Set up Python 3.11" in name for name in step_names)
    assert any("Install Python Dependencies" in name for name in step_names)
    assert any("Preflight Safety Checks" in name for name in step_names)
    assert any("Execute Railway Dataset Ingestion (DRY-RUN)" in name for name in step_names)
    assert any("Execute Railway Dataset Ingestion (PERSISTENCE)" in name for name in step_names)
    assert any("Post-Persistence Database Verification" in name for name in step_names)

    # Verify Python version setup
    python_step = next(s for s in steps if "Set up Python" in s.get("name", ""))
    assert python_step["with"]["python-version"] == "3.11"


def test_dry_run_and_persistence_mutually_exclusive(workflow_data):
    """Verify dry-run and persistence steps are mutually exclusive and invoke verified CLI commands."""
    steps = workflow_data["jobs"]["ingest"]["steps"]

    dry_run_step = next(s for s in steps if "DRY-RUN" in s.get("name", ""))
    persist_step = next(s for s in steps if "PERSISTENCE" in s.get("name", ""))

    # Condition checks
    assert "inputs.dry_run == true" in dry_run_step["if"]
    assert "inputs.dry_run == false" in persist_step["if"]

    # Command verification
    assert "python -m app.cli.import_railway_data --source datameet --dry-run" in dry_run_step["run"]
    assert "python -m app.cli.import_railway_data --source datameet --persist-all" in persist_step["run"]

    # Secret mapping check
    assert "${{ secrets.PROD_DATABASE_URL }}" in dry_run_step["env"]["DATABASE_URL"]
    assert "${{ secrets.PROD_DATABASE_URL }}" in persist_step["env"]["DATABASE_URL"]
