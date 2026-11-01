from dataclasses import dataclass, field
import datetime
from typing import Any, Mapping

from app.infrastructure.adapters.datameet.models import (
    SourceProvenance,
    freeze_payload,
    _normalize_to_tuple,
)


@dataclass(frozen=True)
class DataMeetTrainRecord:
    """
    Immutable representation of an adapted DataMeet railway train route header.
    Preserves exact train numbers as strings (including leading zeroes),
    exact train names with suffixes, endpoints, coach indicators, optional
    timing/distance metrics, synthetic route geometry, and validation warnings.
    """
    number: str
    name: str
    origin_code: str
    destination_code: str
    origin_name: str | None = None
    destination_name: str | None = None
    train_type: str | None = None
    zone: str | None = None
    departure_time: datetime.time | None = None
    arrival_time: datetime.time | None = None
    duration_hours: int | None = None
    duration_minutes: int | None = None
    distance_km: float | None = None
    return_train_number: str | None = None
    has_sleeper: bool = False
    has_third_ac: bool = False
    has_second_ac: bool = False
    has_first_ac: bool = False
    has_first_class: bool = False
    has_chair_car: bool = False
    classes_raw: str | None = None
    route_geometry_coordinates: tuple[tuple[float, float], ...] = ()
    validation_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "route_geometry_coordinates",
            _normalize_to_tuple(self.route_geometry_coordinates, "route_geometry_coordinates"),
        )
        object.__setattr__(
            self,
            "validation_warnings",
            _normalize_to_tuple(self.validation_warnings, "validation_warnings"),
        )


@dataclass(frozen=True)
class AcceptedTrainRecord:
    """Audit record pairing adapted DataMeetTrainRecord with source index, train number, and frozen raw payload."""
    train: DataMeetTrainRecord
    source_record_index: int
    original_train_number: str
    raw_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_payload", freeze_payload(self.raw_payload))


@dataclass(frozen=True)
class TrainQuarantineRecord:
    """Represents a rejected train source record, its validation rejection codes, messages, and frozen raw payload."""
    source_file: str
    source_record_index: int
    original_train_number: str | None
    original_train_name: str | None
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
class TrainAdapterResult:
    """Complete immutable result of a DataMeet train adapter execution."""
    records: tuple[DataMeetTrainRecord, ...]
    accepted: tuple[AcceptedTrainRecord, ...]
    quarantined: tuple[TrainQuarantineRecord, ...]
    provenance: SourceProvenance

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "records",
            _normalize_to_tuple(self.records, "records"),
        )
        object.__setattr__(
            self,
            "accepted",
            _normalize_to_tuple(self.accepted, "accepted"),
        )
        object.__setattr__(
            self,
            "quarantined",
            _normalize_to_tuple(self.quarantined, "quarantined"),
        )

