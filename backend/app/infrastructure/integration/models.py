from dataclasses import dataclass, field
import datetime
from types import MappingProxyType
from typing import Any, Mapping

from app.domain.models.station import Station
from app.domain.models.train import Train
from app.infrastructure.adapters.datameet.models import (
    SourceProvenance,
    QuarantineRecord,
    freeze_payload,
    _normalize_to_tuple,
)
from app.infrastructure.adapters.datameet.train_models import (
    DataMeetTrainRecord,
    TrainQuarantineRecord,
)
from app.infrastructure.adapters.datameet.schedule_models import (
    ScheduleQuarantineRecord,
)


@dataclass(frozen=True)
class IntegratedScheduleStop:
    """
    High-fidelity representation of an integrated schedule stop.
    Links the schedule entry to the resolved Station domain entity.
    Preserves missing timing, day offsets, and distances without synthetic fabrication.
    """
    source_record_id: int
    train_number: str
    station_code: str
    stop_sequence: int
    station: Station
    arrival_time: datetime.time | None = None
    departure_time: datetime.time | None = None
    day: int | None = None
    day_offset: int | None = None
    distance_km: float | None = None
    is_commercial_halt: bool = False
    is_waypoint: bool = False
    is_timing_complete: bool = True
    has_equal_arrival_departure: bool = False
    validation_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "validation_warnings",
            _normalize_to_tuple(self.validation_warnings, "validation_warnings"),
        )


@dataclass(frozen=True)
class IntegratedTrainSchedule:
    """Sequenced schedule of integrated stops for a train."""
    train_number: str
    train_name: str | None
    origin_station: Station
    destination_station: Station
    total_stops: int
    stops: tuple[IntegratedScheduleStop, ...] = ()
    schedule_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stops", _normalize_to_tuple(self.stops, "stops"))
        object.__setattr__(
            self,
            "schedule_warnings",
            _normalize_to_tuple(self.schedule_warnings, "schedule_warnings"),
        )


@dataclass(frozen=True)
class IntegratedTrainRecord:
    """
    Unites route header metadata, sequenced stops, coach capabilities,
    and compilation status.
    """
    header: DataMeetTrainRecord
    schedule: IntegratedTrainSchedule | None = None
    runs_on_days: tuple[int, ...] | None = None
    is_compilable_to_domain: bool = False
    uncompilable_reasons: tuple[str, ...] = ()
    integration_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.runs_on_days is not None:
            object.__setattr__(
                self,
                "runs_on_days",
                _normalize_to_tuple(self.runs_on_days, "runs_on_days"),
            )
        object.__setattr__(
            self,
            "uncompilable_reasons",
            _normalize_to_tuple(self.uncompilable_reasons, "uncompilable_reasons"),
        )
        object.__setattr__(
            self,
            "integration_warnings",
            _normalize_to_tuple(self.integration_warnings, "integration_warnings"),
        )


@dataclass(frozen=True)
class IntegratedRailwayDataset:
    """
    Complete immutable result of the multi-source railway data integration.
    """
    # Resolved Domain Entities (TW-102)
    stations: tuple[Station, ...] = ()
    compiled_trains: tuple[Train, ...] = ()

    # High-Fidelity Integrated Entities (Tier 1)
    train_records: tuple[IntegratedTrainRecord, ...] = ()
    train_schedules: tuple[IntegratedTrainSchedule, ...] = ()
    schedule_stops: tuple[IntegratedScheduleStop, ...] = ()

    # Reference / Uncompiled & Quarantined Entities
    uncompiled_trains: tuple[IntegratedTrainRecord, ...] = ()
    quarantined_stations: tuple[QuarantineRecord, ...] = ()
    quarantined_trains: tuple[TrainQuarantineRecord, ...] = ()
    quarantined_schedule_stops: tuple[ScheduleQuarantineRecord, ...] = ()

    # Provenance
    station_provenance: SourceProvenance | None = None
    train_provenance: SourceProvenance | None = None
    schedule_provenance: SourceProvenance | None = None
    integration_timestamp: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    reconciliation_summary: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "stations", _normalize_to_tuple(self.stations, "stations"))
        object.__setattr__(self, "compiled_trains", _normalize_to_tuple(self.compiled_trains, "compiled_trains"))
        object.__setattr__(self, "train_records", _normalize_to_tuple(self.train_records, "train_records"))
        object.__setattr__(self, "train_schedules", _normalize_to_tuple(self.train_schedules, "train_schedules"))
        object.__setattr__(self, "schedule_stops", _normalize_to_tuple(self.schedule_stops, "schedule_stops"))
        object.__setattr__(self, "uncompiled_trains", _normalize_to_tuple(self.uncompiled_trains, "uncompiled_trains"))
        object.__setattr__(self, "quarantined_stations", _normalize_to_tuple(self.quarantined_stations, "quarantined_stations"))
        object.__setattr__(self, "quarantined_trains", _normalize_to_tuple(self.quarantined_trains, "quarantined_trains"))
        object.__setattr__(self, "quarantined_schedule_stops", _normalize_to_tuple(self.quarantined_schedule_stops, "quarantined_schedule_stops"))
        reconcile = self.reconciliation_summary
        if isinstance(reconcile, Mapping):
            object.__setattr__(self, "reconciliation_summary", MappingProxyType(dict(reconcile)))
        else:
            object.__setattr__(self, "reconciliation_summary", MappingProxyType({}))

