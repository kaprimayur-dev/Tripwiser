from dataclasses import dataclass, field
import datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class ChartQuarantineRecord:
    """Represents a chart vacancy record rejected during ingestion."""
    record_index: int
    train_number: str | None
    chart_date: str | None
    coach: str | None
    berth_number: Any
    from_station: str | None
    to_station: str | None
    exclusion_reason: str
    raw_payload: Mapping[str, Any] = field(default_factory=dict)
    quarantined_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


@dataclass(frozen=True)
class ChartIngestionSummary:
    """High-level summary of an administrative chart vacancy import batch."""
    total_records: int
    valid_records: int
    quarantined_records: int
    persisted_records: int
    manifest_path: str | None
    quarantine_path: str | None
    duration_seconds: float

