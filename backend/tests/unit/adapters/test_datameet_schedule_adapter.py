import json
import datetime
from collections import deque
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType
import pytest

from app.infrastructure.adapters.datameet.station_adapter import DataMeetStationAdapter
from app.infrastructure.adapters.datameet.train_adapter import DataMeetTrainAdapter
from app.infrastructure.adapters.datameet.schedule_adapter import DataMeetScheduleAdapter
from app.infrastructure.adapters.datameet.schedule_models import (
    DataMeetScheduleEntry,
    DataMeetTrainSchedule,
    AcceptedScheduleRecord,
    ScheduleQuarantineRecord,
    ScheduleAdapterResult,
)
from app.infrastructure.adapters.datameet.models import SourceProvenance
from app.infrastructure.adapters.exceptions import (
    SourceFileNotFoundError,
    SourceIOError,
    SourceEncodingError,
    MalformedSourceError,
)

STATIONS_DATA_PATH = Path("app/infrastructure/data/sources/datameet/stations.json")
TRAINS_DATA_PATH = Path("app/infrastructure/data/sources/datameet/trains.json")
SCHEDULES_DATA_PATH = Path("app/infrastructure/data/sources/datameet/schedules.json")


def _make_schedule_record(
    record_id: int = 1001,
    train_number: str = "12951",
    station_code: str = "MMCT",
    station_name: str = "MUMBAI CENTRAL",
    arrival: str = "None",
    departure: str = "16:35:00",
    day: int | None = 1,
    train_name: str = "Mumbai Rajdhani",
) -> dict:
    return {
        "id": record_id,
        "train_number": train_number,
        "station_code": station_code,
        "station_name": station_name,
        "arrival": arrival,
        "departure": departure,
        "day": day,
        "train_name": train_name,
    }


class TestDataMeetScheduleAdapterFileHandling:
    """Verifies file I/O, encoding, and schema parsing error handling."""

    def test_missing_file_raises_source_file_not_found(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        missing = tmp_path / "non_existent_schedules.json"
        with pytest.raises(SourceFileNotFoundError) as exc_info:
            adapter.adapt(missing)
        assert "not found" in str(exc_info.value).lower()

    def test_directory_path_raises_source_io_error(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        with pytest.raises(SourceIOError) as exc_info:
            adapter.adapt(tmp_path)
        assert "not a regular file" in str(exc_info.value).lower()

    def test_invalid_utf8_encoding_raises_source_encoding_error(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        bad_file = tmp_path / "invalid_encoding.json"
        bad_file.write_bytes(b'[\xff\xfe invalid]')
        with pytest.raises(SourceEncodingError) as exc_info:
            adapter.adapt(bad_file)
        assert "utf-8" in str(exc_info.value).lower()

    def test_corrupted_json_syntax_raises_malformed_source_error(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        corrupt = tmp_path / "syntax_error.json"
        corrupt.write_text('[{"id": 1, "train_number": "12951",}', encoding="utf-8")
        with pytest.raises(MalformedSourceError) as exc_info:
            adapter.adapt(corrupt)
        assert "malformed json" in str(exc_info.value).lower()

    def test_non_list_root_raises_malformed_source_error(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        bad_root = tmp_path / "dict_root.json"
        bad_root.write_text('{"records": []}', encoding="utf-8")
        with pytest.raises(MalformedSourceError) as exc_info:
            adapter.adapt(bad_root)
        assert "json array" in str(exc_info.value).lower()


class TestDataMeetScheduleAdapterQuarantineRules:
    """Verifies quarantine of structurally deficient records and unresolved references."""

    def test_quarantines_non_dict_record(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        p = tmp_path / "malformed_records.json"
        p.write_text(json.dumps(["not a dict", 12345]), encoding="utf-8")

        result = adapter.adapt(p)
        assert len(result.accepted) == 0
        assert len(result.quarantined) == 2
        assert "MALFORMED_RECORD_OBJECT" in result.quarantined[0].rejection_codes
        assert result.provenance.rejection_reason_counts["MALFORMED_RECORD_OBJECT"] == 2

    def test_quarantines_missing_or_non_integer_id(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [
            {"train_number": "12951", "station_code": "MMCT"},  # missing id
            {"id": "not_an_int", "train_number": "12951", "station_code": "MMCT"},
            {"id": True, "train_number": "12951", "station_code": "MMCT"},  # bool is not int
        ]
        p = tmp_path / "invalid_id.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        assert len(result.accepted) == 0
        assert len(result.quarantined) == 3
        for q in result.quarantined:
            assert "MISSING_RECORD_ID" in q.rejection_codes

    def test_quarantines_missing_or_empty_train_number(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [
            {"id": 1, "station_code": "MMCT"},
            {"id": 2, "train_number": "", "station_code": "MMCT"},
            {"id": 3, "train_number": "   ", "station_code": "MMCT"},
            {"id": 4, "train_number": None, "station_code": "MMCT"},
        ]
        p = tmp_path / "missing_train.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        assert len(result.accepted) == 0
        assert len(result.quarantined) == 4
        for q in result.quarantined:
            assert "MISSING_TRAIN_NUMBER" in q.rejection_codes

    def test_quarantines_missing_or_empty_station_code(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [
            {"id": 1, "train_number": "12951"},
            {"id": 2, "train_number": "12951", "station_code": ""},
            {"id": 3, "train_number": "12951", "station_code": "   "},
            {"id": 4, "train_number": "12951", "station_code": None},
        ]
        p = tmp_path / "missing_station.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        assert len(result.accepted) == 0
        assert len(result.quarantined) == 4
        for q in result.quarantined:
            assert "MISSING_STATION_CODE" in q.rejection_codes

    def test_quarantines_unresolved_train_and_station_references(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [
            _make_schedule_record(1, "12951", "MMCT"),  # both valid
            _make_schedule_record(2, "99999", "MMCT"),  # train invalid
            _make_schedule_record(3, "12951", "XXXX"),  # station invalid
            _make_schedule_record(4, "99999", "XXXX"),  # both invalid
        ]
        p = tmp_path / "references.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(
            p,
            valid_station_codes=["MMCT"],
            valid_train_numbers=["12951"],
        )
        assert len(result.accepted) == 1
        assert len(result.quarantined) == 3

        q_train_only = result.quarantined[0]
        assert q_train_only.original_train_number == "99999"
        assert q_train_only.rejection_codes == ("UNRESOLVED_TRAIN_REFERENCE",)

        q_station_only = result.quarantined[1]
        assert q_station_only.original_station_code == "XXXX"
        assert q_station_only.rejection_codes == ("UNRESOLVED_STATION_REFERENCE",)

        q_both = result.quarantined[2]
        assert "UNRESOLVED_TRAIN_REFERENCE" in q_both.rejection_codes
        assert "UNRESOLVED_STATION_REFERENCE" in q_both.rejection_codes


class TestDataMeetScheduleAdapterStopSequencing:
    """Verifies deterministic stop sequence reconstruction from ascending source IDs."""

    def test_reconstructs_stop_sequence_from_ascending_source_id(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        # Given out of order in the file
        records = [
            _make_schedule_record(300, "12951", "NDLS", arrival="08:35:00", departure="None", day=2),
            _make_schedule_record(100, "12951", "MMCT", arrival="None", departure="16:35:00", day=1),
            _make_schedule_record(200, "12951", "BVI", arrival="17:08:00", departure="17:10:00", day=1),
        ]
        p = tmp_path / "unordered_stops.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        assert len(result.train_schedules) == 1
        sched = result.train_schedules[0]
        assert sched.total_stops == 3

        # Sorted by ascending ID: 100 (MMCT), 200 (BVI), 300 (NDLS)
        seq_stations = [e.station_code for e in sched.entries]
        assert seq_stations == ["MMCT", "BVI", "NDLS"]

        sequences = [e.stop_sequence for e in sched.entries]
        assert sequences == [1, 2, 3]

        assert sched.origin_code == "MMCT"
        assert sched.destination_code == "NDLS"


class TestDataMeetScheduleAdapterTimingAndIncompleteRecords:
    """Verifies preservation of station topology without timing as Accepted Incomplete records."""

    def test_preserves_incomplete_timing_records_with_warning(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [
            _make_schedule_record(1, "12951", "MMCT", arrival="None", departure="None", day=None),
            _make_schedule_record(2, "12951", "NDLS", arrival="08:35:00", departure="None", day=2),
        ]
        p = tmp_path / "incomplete_timing.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        assert len(result.accepted) == 2
        assert len(result.quarantined) == 0

        incomplete_entry = result.records[0]
        assert incomplete_entry.is_timing_complete is False
        assert incomplete_entry.is_commercial_halt is False
        assert incomplete_entry.is_waypoint is False
        assert "INCOMPLETE_TIMING_INFO" in incomplete_entry.validation_warnings

        complete_entry = result.records[1]
        assert complete_entry.is_timing_complete is True
        assert complete_entry.is_commercial_halt is True

        assert len(result.accepted_incomplete) == 1
        assert len(result.accepted_complete) == 1

    def test_equal_arrival_departure_is_waypoint_with_warning(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [
            _make_schedule_record(1, "12951", "MMCT", arrival="12:00:00", departure="12:00:00", day=1),
        ]
        p = tmp_path / "equal_time.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        entry = result.records[0]
        assert entry.has_equal_arrival_departure is True
        assert entry.is_waypoint is True
        assert entry.is_commercial_halt is False
        assert "EQUAL_ARRIVAL_DEPARTURE_TIME" in entry.validation_warnings


class TestDataMeetScheduleAdapterDayAndDistanceRules:
    """Verifies zero-fabrication of missing day values and distance preservation."""

    def test_missing_day_is_none_and_not_defaulted_to_zero(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [
            _make_schedule_record(1, "12951", "MMCT", day=None),
            _make_schedule_record(2, "12951", "NDLS", day=""),
        ]
        p = tmp_path / "missing_day.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        for entry in result.records:
            assert entry.day is None
            assert entry.day_offset is None
            assert "MISSING_DAY_FIELD" in entry.validation_warnings

    def test_day_offset_calculation_for_valid_days(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [
            _make_schedule_record(1, "12951", "MMCT", day=1),
            _make_schedule_record(2, "12951", "KOTA", day=2),
            _make_schedule_record(3, "12951", "NDLS", day=3),
        ]
        p = tmp_path / "days.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        assert result.records[0].day == 1
        assert result.records[0].day_offset == 0
        assert result.records[1].day == 2
        assert result.records[1].day_offset == 1
        assert result.records[2].day == 3
        assert result.records[2].day_offset == 2

    def test_day_above_6_preserved_verbatim_with_suspicious_day_warning(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [
            _make_schedule_record(1, "12951", "MMCT", day=10),
        ]
        p = tmp_path / "high_day.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        entry = result.records[0]
        assert entry.day == 10
        assert entry.day_offset == 9
        assert "SUSPICIOUS_DAY_VALUE" in entry.validation_warnings

    def test_missing_distance_preserved_as_none_with_warning(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        records = [_make_schedule_record(1, "12951", "MMCT")]
        p = tmp_path / "distance.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        entry = result.records[0]
        assert entry.distance_km is None
        assert "MISSING_DISTANCE" in entry.validation_warnings


class TestDataMeetScheduleAdapterRouteLevelWarnings:
    """Verifies route-level anomaly detection: repeated stations, chronological inversions, endpoint mismatches."""

    def test_repeated_station_calls_detected_with_warning(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        # Train calls at BVI twice
        records = [
            _make_schedule_record(10, "12951", "MMCT", departure="16:00:00", day=1),
            _make_schedule_record(20, "12951", "BVI", arrival="16:30:00", departure="16:35:00", day=1),
            _make_schedule_record(30, "12951", "BVI", arrival="17:00:00", departure="17:05:00", day=1),
            _make_schedule_record(40, "12951", "NDLS", arrival="08:00:00", day=2),
        ]
        p = tmp_path / "repeated_station.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        sched = result.train_schedules[0]
        assert "REPEATED_STATION_IN_ROUTE" in sched.schedule_warnings

        # First visit has no repeated station warning
        assert "REPEATED_STATION_IN_ROUTE" not in sched.entries[1].validation_warnings
        # Second visit is flagged
        assert "REPEATED_STATION_IN_ROUTE" in sched.entries[2].validation_warnings

    def test_chronological_inversion_detected_with_warning(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        # Inversion: departure at 23:30 on day 1, then arrival at 00:30 with day still 1 (unrecorded rollover)
        records = [
            _make_schedule_record(10, "12951", "MMCT", departure="23:30:00", day=1),
            _make_schedule_record(20, "12951", "BVI", arrival="00:30:00", departure="00:35:00", day=1),
        ]
        p = tmp_path / "inversion.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        result = adapter.adapt(p)
        sched = result.train_schedules[0]
        assert "CHRONOLOGICAL_INVERSION" in sched.schedule_warnings
        assert "CHRONOLOGICAL_INVERSION" in sched.entries[1].validation_warnings

    def test_endpoint_mismatch_detected_against_metadata(self, tmp_path):
        adapter = DataMeetScheduleAdapter()
        # Schedule has origin BVI and destination KOTA, but metadata header says MMCT -> NDLS
        records = [
            _make_schedule_record(10, "12951", "BVI", departure="16:35:00", day=1),
            _make_schedule_record(20, "12951", "KOTA", arrival="08:35:00", day=2),
        ]
        p = tmp_path / "mismatch.json"
        p.write_text(json.dumps(records), encoding="utf-8")

        train_meta = {
            "12951": {
                "name": "Mumbai Rajdhani",
                "origin_code": "MMCT",
                "destination_code": "NDLS",
            }
        }

        result = adapter.adapt(p, train_metadata=train_meta)
        sched = result.train_schedules[0]
        assert "ORIGIN_STATION_MISMATCH" in sched.schedule_warnings
        assert "DESTINATION_STATION_MISMATCH" in sched.schedule_warnings
        assert "ORIGIN_STATION_MISMATCH" in sched.entries[0].validation_warnings
        assert "DESTINATION_STATION_MISMATCH" in sched.entries[-1].validation_warnings


class TestDataMeetScheduleAdapterImmutability:
    """Verifies strict construction-time immutability and collection normalization."""

    def test_schedule_entry_is_immutable(self):
        entry = DataMeetScheduleEntry(
            source_record_id=1,
            train_number="12951",
            station_code="MMCT",
            stop_sequence=1,
            validation_warnings=["WARN1"],
        )
        assert isinstance(entry.validation_warnings, tuple)
        with pytest.raises(FrozenInstanceError):
            entry.stop_sequence = 2  # type: ignore

    def test_train_schedule_is_immutable(self):
        entry = DataMeetScheduleEntry(
            source_record_id=1,
            train_number="12951",
            station_code="MMCT",
            stop_sequence=1,
        )
        sched = DataMeetTrainSchedule(
            train_number="12951",
            train_name="Rajdhani",
            origin_code="MMCT",
            destination_code="NDLS",
            total_stops=1,
            entries=[entry],
            schedule_warnings=deque(["WARN_A"]),
        )
        assert isinstance(sched.entries, tuple)
        assert isinstance(sched.schedule_warnings, tuple)
        with pytest.raises(FrozenInstanceError):
            sched.total_stops = 2  # type: ignore

    def test_accepted_and_quarantine_records_freeze_payload(self):
        entry = DataMeetScheduleEntry(
            source_record_id=1,
            train_number="12951",
            station_code="MMCT",
            stop_sequence=1,
        )
        accepted = AcceptedScheduleRecord(
            entry=entry,
            source_record_index=0,
            original_train_number="12951",
            original_station_code="MMCT",
            raw_payload={"details": {"train": "12951"}},
        )
        assert isinstance(accepted.raw_payload, MappingProxyType)
        with pytest.raises(TypeError):
            accepted.raw_payload["details"] = {}  # type: ignore

        quarantine = ScheduleQuarantineRecord(
            source_file="test.json",
            source_record_index=0,
            source_record_id=1,
            original_train_number="99999",
            original_station_code="XXXX",
            rejection_codes=["CODE"],
            validation_messages=["MSG"],
            raw_payload={"error": "details"},
        )
        assert isinstance(quarantine.rejection_codes, tuple)
        assert isinstance(quarantine.validation_messages, tuple)
        assert isinstance(quarantine.raw_payload, MappingProxyType)

    def test_collection_normalization_rejects_scalars_and_mappings(self):
        entry = DataMeetScheduleEntry(
            source_record_id=1,
            train_number="12951",
            station_code="MMCT",
            stop_sequence=1,
        )
        with pytest.raises(TypeError):
            # entries cannot be a scalar
            DataMeetTrainSchedule(
                train_number="12951",
                train_name="Rajdhani",
                origin_code="MMCT",
                destination_code="NDLS",
                total_stops=1,
                entries=entry,  # type: ignore
            )

        with pytest.raises(TypeError):
            # rejection_codes cannot be a string
            ScheduleQuarantineRecord(
                source_file="test.json",
                source_record_index=0,
                source_record_id=1,
                original_train_number="99999",
                original_station_code="XXXX",
                rejection_codes="SINGLE_CODE",  # type: ignore
                validation_messages=("MSG",),
                raw_payload={},
            )


@pytest.mark.skipif(not SCHEDULES_DATA_PATH.exists(), reason="Requires DataMeet schedules.json snapshot")
class TestDataMeetScheduleAdapterReconciliation:
    """Verifies exact reconciliation on the full DataMeet schedules.json source dataset."""

    def test_exact_standalone_reconciliation(self):
        adapter = DataMeetScheduleAdapter()
        result = adapter.adapt(SCHEDULES_DATA_PATH)

        assert result.provenance.total_source_records == 417080
        assert result.provenance.accepted_records_count == 417080
        assert result.provenance.quarantined_records_count == 0

        assert len(result.accepted_complete) == 394391
        assert len(result.accepted_incomplete) == 22689
        assert len(result.records) == 417080
        assert len(result.train_schedules) == 5208

        # Exact identity
        assert len(result.accepted_complete) + len(result.accepted_incomplete) == 417080

    def test_exact_integrated_foundation_reconciliation(self):
        station_adapter = DataMeetStationAdapter()
        train_adapter = DataMeetTrainAdapter()
        schedule_adapter = DataMeetScheduleAdapter()

        station_res = station_adapter.adapt(STATIONS_DATA_PATH)
        valid_stations = {s.code for s in station_res.records}

        train_res = train_adapter.adapt(TRAINS_DATA_PATH, valid_station_codes=valid_stations)
        valid_trains = {t.number for t in train_res.records}
        train_meta = {t.number: t for t in train_res.records}

        assert len(valid_stations) == 8697
        assert len(valid_trains) == 5175

        result = schedule_adapter.adapt(
            SCHEDULES_DATA_PATH,
            valid_station_codes=valid_stations,
            valid_train_numbers=valid_trains,
            train_metadata=train_meta,
        )

        assert result.provenance.total_source_records == 417080
        assert result.provenance.accepted_records_count == 414176
        assert len(result.accepted_complete) == 392420
        assert len(result.accepted_incomplete) == 21756
        assert result.provenance.quarantined_records_count == 2904

        # Exact reconciliation identity: Accepted (414,176) + Quarantined (2,904) = 417,080
        assert result.provenance.accepted_records_count + result.provenance.quarantined_records_count == 417080

        # Exact unique train schedules
        assert len(result.train_schedules) == 5175

        # Rejection reason breakdown
        counts = result.provenance.rejection_reason_counts
        assert counts["UNRESOLVED_TRAIN_REFERENCE"] == 411
        assert counts["UNRESOLVED_STATION_REFERENCE"] == 2660

