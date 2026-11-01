"""
Unit tests for TW-115: Railway Data Quality Validation Engine.
Tests all validation rules, severity levels, quality classifications, and checksum reproducibility.
"""

import pytest
from app.domain.models.data_quality import (
    QualitySeverity,
    QualityStatus,
    RecordType,
    ValidationFinding,
    CategoryQualitySummary,
)
from app.domain.services.data_quality_engine import DataQualityEngine


def test_station_validation_rules():
    engine = DataQualityEngine()
    seen_codes = set()

    # 1. Missing station code -> CRITICAL / REJECTED
    status = engine.validate_station(
        {"code": "", "name": "Test Station", "latitude": 23.2, "longitude": 77.4, "state": "Madhya Pradesh"},
        seen_codes=seen_codes,
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "STN_MISSING_CODE" and f.severity == QualitySeverity.CRITICAL for f in engine.findings)

    # 2. Duplicate station code -> CRITICAL / REJECTED
    seen_codes.add("BPL")
    status = engine.validate_station(
        {"code": "BPL", "name": "Bhopal Junction", "latitude": 23.2, "longitude": 77.4, "state": "Madhya Pradesh"},
        seen_codes=seen_codes,
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "STN_DUPLICATE_CODE" and f.severity == QualitySeverity.CRITICAL for f in engine.findings)

    # 3. Null geometry / missing coords -> CRITICAL / REJECTED
    status = engine.validate_station(
        {"code": "TEST1", "name": "Test Station 1", "latitude": None, "longitude": None, "state": "Madhya Pradesh"},
        seen_codes=seen_codes,
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "STN_NULL_GEOMETRY" and f.severity == QualitySeverity.CRITICAL for f in engine.findings)

    # 4. Out of bounds coordinates -> ERROR / REJECTED
    status = engine.validate_station(
        {"code": "TEST3", "name": "Out of Bounds Station", "latitude": 55.0, "longitude": 10.0, "state": "Madhya Pradesh"},
        seen_codes=seen_codes,
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "STN_OUT_OF_BOUNDS_COORDINATES" and f.severity == QualitySeverity.ERROR for f in engine.findings)

    # 5. Missing state -> WARNING / REVIEW_REQUIRED
    engine.clear()
    status = engine.validate_station(
        {"code": "TEST4", "name": "Station Without State", "latitude": 23.2, "longitude": 77.4, "state": None},
        seen_codes=seen_codes,
    )
    assert status == QualityStatus.REVIEW_REQUIRED
    assert any(f.rule_code == "STN_MISSING_STATE" and f.severity == QualitySeverity.WARNING for f in engine.findings)

    # 6. Completely valid station -> VALID
    engine.clear()
    status = engine.validate_station(
        {"code": "NDLS", "name": "New Delhi", "latitude": 28.6139, "longitude": 77.2090, "state": "Delhi"},
        seen_codes=seen_codes,
    )
    assert status == QualityStatus.VALID
    assert len(engine.findings) == 0


def test_train_header_validation_rules():
    engine = DataQualityEngine()
    valid_stations = {"NDLS", "BPL", "CSMT"}
    seen_trains = set()

    # 1. Missing train number -> CRITICAL / REJECTED
    status = engine.validate_train_header(
        train_number="",
        train_name="Express",
        origin_code="NDLS",
        destination_code="BPL",
        valid_station_codes=valid_stations,
        seen_train_numbers=seen_trains,
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "TRN_MISSING_NUMBER" for f in engine.findings)

    # 2. Duplicate train number -> CRITICAL / REJECTED
    seen_trains.add("12002")
    status = engine.validate_train_header(
        train_number="12002",
        train_name="Bhopal Shatabdi",
        origin_code="NDLS",
        destination_code="BPL",
        valid_station_codes=valid_stations,
        seen_train_numbers=seen_trains,
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "TRN_DUPLICATE_NUMBER" for f in engine.findings)

    # 3. Missing name -> ERROR / REJECTED
    status = engine.validate_train_header(
        train_number="12001",
        train_name="",
        origin_code="NDLS",
        destination_code="BPL",
        valid_station_codes=valid_stations,
        seen_train_numbers=seen_trains,
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "TRN_MISSING_NAME" for f in engine.findings)

    # 4. Unresolved origin station -> ERROR / REJECTED
    status = engine.validate_train_header(
        train_number="12003",
        train_name="Shatabdi Express",
        origin_code="UNKNOWN",
        destination_code="BPL",
        valid_station_codes=valid_stations,
        seen_train_numbers=seen_trains,
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "TRN_UNRESOLVED_ORIGIN" for f in engine.findings)

    # 5. Same origin and destination -> ERROR / REJECTED
    status = engine.validate_train_header(
        train_number="12004",
        train_name="Circular Express",
        origin_code="BPL",
        destination_code="BPL",
        valid_station_codes=valid_stations,
        seen_train_numbers=seen_trains,
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "TRN_IDENTICAL_ENDPOINTS" for f in engine.findings)

    # 6. Valid train header -> VALID
    engine.clear()
    status = engine.validate_train_header(
        train_number="12005",
        train_name="Bhopal Shatabdi",
        origin_code="NDLS",
        destination_code="BPL",
        valid_station_codes=valid_stations,
        seen_train_numbers=seen_trains,
    )
    assert status == QualityStatus.VALID
    assert len(engine.findings) == 0


def test_train_schedule_validation_rules():
    engine = DataQualityEngine()
    valid_stations = {"NDLS", "GWL", "BPL"}

    # 1. Empty schedule -> REJECTED
    status = engine.validate_train_schedule(
        train_number="12002",
        stops=[],
        valid_station_codes=valid_stations,
        expected_origin="NDLS",
        expected_dest="BPL",
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "SCH_EMPTY_SCHEDULE" for f in engine.findings)

    # 2. Non-monotonic sequence numbers -> REJECTED
    engine.clear()
    status = engine.validate_train_schedule(
        train_number="12002",
        stops=[
            {"station_code": "NDLS", "stop_sequence": 2, "departure_time": "06:00:00", "arrival_time": "06:00:00", "day_offset": 0},
            {"station_code": "GWL", "stop_sequence": 1, "departure_time": "09:30:00", "arrival_time": "09:25:00", "day_offset": 0},
        ],
        valid_station_codes=valid_stations,
        expected_origin="NDLS",
        expected_dest="GWL",
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "SCH_NON_MONOTONIC_SEQUENCE" for f in engine.findings)

    # 3. Duplicate sequence numbers -> REJECTED
    engine.clear()
    status = engine.validate_train_schedule(
        train_number="12002",
        stops=[
            {"station_code": "NDLS", "stop_sequence": 1, "departure_time": "06:00:00", "arrival_time": "06:00:00", "day_offset": 0},
            {"station_code": "GWL", "stop_sequence": 1, "departure_time": "09:30:00", "arrival_time": "09:25:00", "day_offset": 0},
        ],
        valid_station_codes=valid_stations,
        expected_origin="NDLS",
        expected_dest="GWL",
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "SCH_DUPLICATE_SEQUENCE" for f in engine.findings)

    # 4. Zero dwell waypoint (arrival == departure) and negative dwell detection
    engine.clear()
    status = engine.validate_train_schedule(
        train_number="12002",
        stops=[
            {"station_code": "NDLS", "stop_sequence": 1, "departure_time": "06:00:00", "arrival_time": "06:00:00", "day_offset": 0},
            # Negative dwell: departure 09:20 before arrival 09:30 on same day
            {"station_code": "GWL", "stop_sequence": 2, "departure_time": "09:20:00", "arrival_time": "09:30:00", "day_offset": 0},
            # Zero-dwell technical pass
            {"station_code": "BPL", "stop_sequence": 3, "departure_time": "14:00:00", "arrival_time": "14:00:00", "day_offset": 0},
        ],
        valid_station_codes=valid_stations,
        expected_origin="NDLS",
        expected_dest="BPL",
    )
    assert any(f.rule_code == "SCH_NEGATIVE_STATION_DWELL" and f.severity == QualitySeverity.WARNING for f in engine.findings)
    assert any(f.rule_code == "SCH_ZERO_DWELL_WAYPOINT" and f.severity == QualitySeverity.INFO for f in engine.findings)

    # 5. Missing day offset -> WARNING finding (REVIEW_REQUIRED)
    engine.clear()
    status = engine.validate_train_schedule(
        train_number="12002",
        stops=[
            {"station_code": "NDLS", "stop_sequence": 1, "departure_time": "06:00:00", "arrival_time": "06:00:00", "day_offset": None},
            {"station_code": "BPL", "stop_sequence": 2, "departure_time": "14:00:00", "arrival_time": "14:00:00", "day_offset": None},
        ],
        valid_station_codes=valid_stations,
        expected_origin="NDLS",
        expected_dest="BPL",
    )
    assert any(f.rule_code == "SCH_MISSING_DAY_OFFSET" and f.severity == QualitySeverity.WARNING for f in engine.findings)

    # 6. Decreasing day offset -> ERROR / REJECTED
    engine.clear()
    status = engine.validate_train_schedule(
        train_number="12002",
        stops=[
            {"station_code": "NDLS", "stop_sequence": 1, "departure_time": "06:00:00", "arrival_time": "06:00:00", "day_offset": 2},
            {"station_code": "BPL", "stop_sequence": 2, "departure_time": "14:00:00", "arrival_time": "14:00:00", "day_offset": 1},
        ],
        valid_station_codes=valid_stations,
        expected_origin="NDLS",
        expected_dest="BPL",
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "SCH_DECREASING_DAY_OFFSET" and f.severity == QualitySeverity.ERROR for f in engine.findings)


def test_calendar_validation_rules():
    engine = DataQualityEngine()

    # 1. Missing days -> REVIEW_REQUIRED / WARNING
    status = engine.validate_running_calendar(
        train_number="12001",
        runs_on_days=[],
        calendar_entry={"runs_on_days": []},
    )
    assert status == QualityStatus.REVIEW_REQUIRED
    assert any(f.rule_code == "CAL_AWAITING_CALENDAR" for f in engine.findings)

    # 2. Invalid day range (outside 0-6) -> REJECTED / ERROR
    engine.clear()
    status = engine.validate_running_calendar(
        train_number="12001",
        runs_on_days=[0, 1, 7],
        calendar_entry={"runs_on_days": [0, 1, 7]},
    )
    assert status == QualityStatus.REJECTED
    assert any(f.rule_code == "CAL_INVALID_DAY_INTEGER" for f in engine.findings)

    # 3. Valid calendar with provenance -> VALID
    engine.clear()
    status = engine.validate_running_calendar(
        train_number="12002",
        runs_on_days=[0, 1, 2, 3, 4, 5, 6],
        calendar_entry={
            "runs_on_days": [0, 1, 2, 3, 4, 5, 6],
            "source_document": "Indian Railways Trains at a Glance (TAG 2024-2026)",
            "official_verified": True,
        },
    )
    assert status == QualityStatus.VALID
    assert len(engine.findings) == 0


def test_audit_reproducibility_checksum():
    """Verify that compiling audit reports produces deterministic reproducible SHA-256 hashes."""
    engine1 = DataQualityEngine()
    engine2 = DataQualityEngine()

    finding1 = ValidationFinding(
        record_type=RecordType.STATION,
        record_id="TEST1",
        rule_code="STN_NULL_GEOMETRY",
        severity=QualitySeverity.CRITICAL,
        message="Station geometry is missing or null",
    )
    finding2 = ValidationFinding(
        record_type=RecordType.SCHEDULE,
        record_id="12002_STOP_1",
        rule_code="SCH_ZERO_DWELL_WAYPOINT",
        severity=QualitySeverity.INFO,
        message="Timetable record has equal arrival and departure times",
    )

    engine1.findings = [finding1, finding2]
    engine2.findings = [finding1, finding2]

    cat_sum = CategoryQualitySummary(
        total_inspected=2,
        valid_count=1,
        rejected_count=1,
        review_required_count=0,
        retained_incomplete_count=0,
    )

    report1 = engine1.compile_audit_report(cat_sum, cat_sum, cat_sum, cat_sum)
    report2 = engine2.compile_audit_report(cat_sum, cat_sum, cat_sum, cat_sum)

    assert report1.reproducibility_hash == report2.reproducibility_hash
    assert len(report1.reproducibility_hash) == 64
