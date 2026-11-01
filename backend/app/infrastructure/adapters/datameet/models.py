from dataclasses import dataclass, field
import datetime
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import Any
from pydantic import BaseModel

from app.domain.models.station import Station


def freeze_payload(obj: Any) -> Any:
    """Recursively freeze mappings into MappingProxyType and sequences/collections (except str/bytes) into tuples."""
    if isinstance(obj, (str, bytes)):
        return obj
    if isinstance(obj, Mapping):
        return MappingProxyType({k: freeze_payload(v) for k, v in obj.items()})
    if isinstance(obj, (Sequence, set, frozenset, deque)):
        return tuple(freeze_payload(v) for v in obj)
    return obj


def _normalize_to_tuple(val: Any, field_name: str) -> tuple:
    """
    Normalizes collection inputs (tuple, list, set, frozenset, deque, iterable) to tuple.
    Rejects strings, bytes, mappings, BaseModel instances, and non-iterable scalars with a clear TypeError.
    Preserves existing tuple instances directly.
    """
    if isinstance(val, tuple):
        return val
    if isinstance(val, (str, bytes)):
        raise TypeError(f"'{field_name}' must be an iterable collection of elements, not {type(val).__name__}")
    if isinstance(val, (Mapping, BaseModel)):
        raise TypeError(f"'{field_name}' must be an iterable collection of elements, not a mapping/model ({type(val).__name__})")
    if not isinstance(val, Iterable):
        raise TypeError(f"'{field_name}' must be an iterable collection, not scalar ({type(val).__name__})")
    return tuple(val)



@dataclass(frozen=True)
class AcceptedRecord:
    """Audit record preserving accepted Station domain entity and raw source provenance."""
    station: Station
    source_record_index: int
    original_station_code: str
    raw_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_payload", freeze_payload(self.raw_payload))


@dataclass(frozen=True)
class QuarantineRecord:
    """Represents a rejected source record and its validation failure reasons."""
    source_file: str
    source_record_index: int
    original_station_code: str | None
    original_station_name: str | None
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
class SourceProvenance:
    """Cryptographic, licence, and execution provenance for an adapted dataset."""
    source_repository_url: str = "https://github.com/datameet/railways"
    source_file_path: str = ""
    repository_snapshot_id: str | None = None
    source_license: str = "CC0 1.0 Universal"
    license_evidence: str = "Upstream DataMeet Railways README (https://github.com/datameet/railways)"
    license_qualification: str = "Underlying data provenance has not been independently audited."
    file_sha256: str = ""
    file_size_bytes: int = 0
    import_timestamp: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    adapter_version: str = "1.0.0"
    total_source_records: int = 0
    accepted_records_count: int = 0
    quarantined_records_count: int = 0
    rejection_reason_counts: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        counts = self.rejection_reason_counts
        if isinstance(counts, Mapping):
            object.__setattr__(self, "rejection_reason_counts", MappingProxyType(dict(counts)))
        else:
            object.__setattr__(self, "rejection_reason_counts", MappingProxyType({}))


@dataclass(frozen=True)
class AdapterResult:
    """The complete immutable result of an adapter run including accepted entities and quarantined items."""
    records: tuple[Station, ...]
    accepted: tuple[AcceptedRecord, ...]
    quarantined: tuple[QuarantineRecord, ...]
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
