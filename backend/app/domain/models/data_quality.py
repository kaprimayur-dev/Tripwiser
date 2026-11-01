"""
Domain models for Railway Data Quality and Trust Engine (TW-115).
Provides structured definitions for severity levels, validation findings,
record statuses, and dataset quality audit summaries.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class QualitySeverity(str, Enum):
    CRITICAL = "CRITICAL"  # Critical flaw: record completely unusable/corrupt
    ERROR = "ERROR"        # Logical/integrity violation: record must be rejected from domain
    WARNING = "WARNING"    # Suspicious anomaly: record retained but flagged for manual review
    INFO = "INFO"          # Informational/telemetry notice (e.g. waypoint, missing optional field)


class QualityStatus(str, Enum):
    VALID = "VALID"                      # Meets all domain and operational criteria
    REJECTED = "REJECTED"                # Quarantined / rejected from compiled dataset
    REVIEW_REQUIRED = "REVIEW_REQUIRED"  # Flagged for human or source verification
    RETAINED_INCOMPLETE = "RETAINED_INCOMPLETE"  # Safe for display/topology, but timing incomplete


class RecordType(str, Enum):
    STATION = "STATION"
    TRAIN = "TRAIN"
    SCHEDULE = "SCHEDULE"
    CALENDAR = "CALENDAR"


class ValidationFinding(BaseModel):
    """
    Immutable structured finding emitted when a validation rule is triggered.
    """
    record_type: RecordType
    record_id: str
    rule_code: str
    severity: QualitySeverity
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    source_ref: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class CategoryQualitySummary(BaseModel):
    total_inspected: int = 0
    valid_count: int = 0
    rejected_count: int = 0
    review_required_count: int = 0
    retained_incomplete_count: int = 0
    warnings_count: int = 0


class DataQualityAuditSummary(BaseModel):
    """
    Aggregated dataset audit metrics detailing station, train, schedule,
    and calendar data quality.
    """
    report_id: str
    generated_at: str
    total_records_inspected: int
    stations: CategoryQualitySummary
    trains: CategoryQualitySummary
    schedules: CategoryQualitySummary
    calendars: CategoryQualitySummary
    findings_by_severity: Dict[str, int]
    findings_by_category: Dict[str, int]
    top_failure_rules: List[Dict[str, Any]]
    data_freshness_statement: str
    source_artifacts: Dict[str, str]
    reproducibility_hash: str

