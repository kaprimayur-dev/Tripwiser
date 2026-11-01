from dataclasses import dataclass, field
import datetime
from typing import Any, Mapping

from app.infrastructure.adapters.datameet.models import (
    SourceProvenance,
    freeze_payload,
    _normalize_to_tuple,
)


@dataclass(frozen=True)
class DataMeetScheduleEntry:
    """
    Immutable representation of an adapted DataMeet railway schedule stop/waypoint.
    Preserves exact timing, reconstructed 1-based stop sequence (from ascending source ID),
    and waypoint/halt indicators without synthesizing missing data.
    """
    source_record_id: int
    train_number: str
    station_code: str
    stop_sequence: int
    station_name: str | None = None
    arrival_time: datetime.time | None = None
    departure_time: datetime.time | None = None
    day: int | None = None
    day_offset: int | None = None
    is_commercial_halt: bool = False
    is_waypoint: bool = False
    is_timing_complete: bool = True
    has_equal_arrival_departure: bool = False
    distance_km: float | None = None
    validation_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "validation_warnings",
            _normalize_to_tuple(self.validation_warnings, "validation_warnings"),
        )


@dataclass(frozen=True)
class DataMeetTrainSchedule:
    """
    Immutable representation of a train's sequenced schedule, grouping and sequencing its stops.
    stop_sequence is the deterministic reconstruction from ascending source IDs, not an official
    railway timetable sequence.
    """
    train_number: str
    train_name: str | None
    origin_code: str
    destination_code: str
    total_stops: int
    entries: tuple[DataMeetScheduleEntry, ...]
    schedule_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", _normalize_to_tuple(self.entries, "entries"))
        object.__setattr__(
            self,
            "schedule_warnings",
            _normalize_to_tuple(self.schedule_warnings, "schedule_warnings"),
        )


@dataclass(frozen=True)
class AcceptedScheduleRecord:
    """Audit record pairing adapted DataMeetScheduleEntry with source index, identifiers, and frozen raw payload."""
    entry: DataMeetScheduleEntry
    source_record_index: int
    original_train_number: str
    original_station_code: str
    raw_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_payload", freeze_payload(self.raw_payload))


@dataclass(frozen=True)
class ScheduleQuarantineRecord:
    """Represents a rejected schedule stop record and its diagnostic failure metadata."""
    source_file: str
    source_record_index: int
    source_record_id: int | None
    original_train_number: str | None
    original_station_code: str | None
    rejection_codes: tuple[str, ...]
    validation_messages: tuple[str, ...]
    raw_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rejection_codes",
            _normalize_to_tuple(self.rejection_codes, "rejection_codes"),
        )
        object.__setattr__(
            self,
            "validation_messages",
            _normalize_to_tuple(self.validation_messages, "validation_messages"),
        )
        object.__setattr__(self, "raw_payload", freeze_payload(self.raw_payload))


@dataclass(frozen=True)
class ScheduleAdapterResult:
    """Complete immutable result of a DataMeet schedule adapter execution."""
    train_schedules: tuple[DataMeetTrainSchedule, ...]
    records: tuple[DataMeetScheduleEntry, ...]
    accepted: tuple[AcceptedScheduleRecord, ...]
    quarantined: tuple[ScheduleQuarantineRecord, ...]
    provenance: SourceProvenance

    def __post_init__(self) -> None:
        object.__setattr__(self, "train_schedules", _normalize_to_tuple(self.train_schedules, "train_schedules"))
        object.__setattr__(self, "records", _normalize_to_tuple(self.records, "records"))
        object.__setattr__(self, "accepted", _normalize_to_tuple(self.accepted, "accepted"))
        object.__setattr__(self, "quarantined", _normalize_to_tuple(self.quarantined, "quarantined"))

    @property
    def accepted_complete(self) -> tuple[AcceptedScheduleRecord, ...]:
        """Convenience property filtering for accepted records with valid timing."""
        return tuple(a for a in self.accepted if a.entry.is_timing_complete)

    @property
    def accepted_incomplete(self) -> tuple[AcceptedScheduleRecord, ...]:
        """Convenience property filtering for accepted incomplete records (both times None)."""
        return tuple(a for a in self.accepted if not a.entry.is_timing_complete)

