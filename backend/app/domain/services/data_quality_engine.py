"""
Data Quality Validation and Trust Engine (TW-115).
Provides rigorous, deterministic integrity checks across Stations, Trains,
Timetables, and Operating Calendars without fabricating missing data.
"""

from typing import Dict, Any, List, Set, Sequence, Optional, Tuple, Iterable
from datetime import datetime, time, date, timedelta
import hashlib
import json
from collections import Counter

from app.domain.models.data_quality import (
    QualitySeverity,
    QualityStatus,
    RecordType,
    ValidationFinding,
    CategoryQualitySummary,
    DataQualityAuditSummary,
)
from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry


# India Geodetic Bounding Box boundaries (approx with marine/islands buffer)
INDIA_MIN_LAT = 6.0
INDIA_MAX_LAT = 38.5
INDIA_MIN_LON = 68.0
INDIA_MAX_LON = 98.5


class DataQualityEngine:
    """
    Reusable data quality validation engine that inspects railway records,
    detects anomalies, and categorizes findings with deterministic rules.
    """

    DATA_FRESHNESS_STATEMENT = (
        "Dataset compiled from public DataMeet Railways repository snapshots and official "
        "Indian Railways Trains at a Glance (TAG 2024-2026) publication tables. "
        "Source files do not provide per-record HTTP last-modified timestamps; freshness cannot "
        "be dynamically verified beyond the documented publication release dates."
    )

    def __init__(self):
        self.findings: List[ValidationFinding] = []

    def clear(self):
        self.findings.clear()

    # ==========================================
    # 1. Station Integrity Rules
    # ==========================================
    def validate_station(
        self,
        station: Station | Dict[str, Any],
        seen_codes: Set[str],
        source_ref: Optional[str] = None,
    ) -> QualityStatus:
        """
        Validates individual station record against code, coordinate, and metadata constraints.
        """
        findings: List[ValidationFinding] = []

        code = (station.code if isinstance(station, Station) else station.get("code") or "").strip().upper()
        name = (station.name if isinstance(station, Station) else station.get("name") or "").strip()
        lat = station.latitude if isinstance(station, Station) else station.get("latitude")
        lon = station.longitude if isinstance(station, Station) else station.get("longitude")
        state = station.state if isinstance(station, Station) else station.get("state")

        record_id = code or f"UNKNOWN_STN_{len(seen_codes)}"

        # 1. Code presence
        if not code:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.STATION,
                    record_id=record_id,
                    rule_code="STN_MISSING_CODE",
                    severity=QualitySeverity.CRITICAL,
                    message="Station record missing unique station code",
                    source_ref=source_ref,
                )
            )
        elif code in seen_codes:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.STATION,
                    record_id=code,
                    rule_code="STN_DUPLICATE_CODE",
                    severity=QualitySeverity.CRITICAL,
                    message=f"Duplicate station code '{code}' encountered",
                    details={"code": code},
                    source_ref=source_ref,
                )
            )
        else:
            seen_codes.add(code)

        # 2. Name presence
        if not name:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.STATION,
                    record_id=record_id,
                    rule_code="STN_MISSING_NAME",
                    severity=QualitySeverity.ERROR,
                    message=f"Station '{code}' missing official station name",
                    source_ref=source_ref,
                )
            )

        # 3. Coordinate validity
        if lat is None or lon is None:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.STATION,
                    record_id=record_id,
                    rule_code="STN_NULL_GEOMETRY",
                    severity=QualitySeverity.CRITICAL,
                    message=f"Station '{code}' has null or missing geographic coordinates",
                    source_ref=source_ref,
                )
            )
        else:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                if not (INDIA_MIN_LAT <= lat_f <= INDIA_MAX_LAT and INDIA_MIN_LON <= lon_f <= INDIA_MAX_LON):
                    findings.append(
                        ValidationFinding(
                            record_type=RecordType.STATION,
                            record_id=record_id,
                            rule_code="STN_OUT_OF_BOUNDS_COORDINATES",
                            severity=QualitySeverity.ERROR,
                            message=f"Station '{code}' coordinates ({lat_f}, {lon_f}) fall outside India bounding box",
                            details={"latitude": lat_f, "longitude": lon_f},
                            source_ref=source_ref,
                        )
                    )
            except (ValueError, TypeError):
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.STATION,
                        record_id=record_id,
                        rule_code="STN_MALFORMED_COORDINATES",
                        severity=QualitySeverity.CRITICAL,
                        message=f"Station '{code}' coordinates cannot be parsed as floats",
                        source_ref=source_ref,
                    )
                )

        # 4. State / zone metadata (Warning only)
        if not state:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.STATION,
                    record_id=record_id,
                    rule_code="STN_MISSING_STATE",
                    severity=QualitySeverity.WARNING,
                    message=f"Station '{code}' has unassigned state administration metadata",
                    source_ref=source_ref,
                )
            )

        self.findings.extend(findings)

        if any(f.severity in (QualitySeverity.CRITICAL, QualitySeverity.ERROR) for f in findings):
            return QualityStatus.REJECTED
        if any(f.severity == QualitySeverity.WARNING for f in findings):
            return QualityStatus.REVIEW_REQUIRED
        return QualityStatus.VALID

    # ==========================================
    # 2. Train Header Integrity Rules
    # ==========================================
    def validate_train_header(
        self,
        train_number: str,
        train_name: str,
        origin_code: str,
        destination_code: str,
        valid_station_codes: Set[str],
        seen_train_numbers: Set[str],
        source_ref: Optional[str] = None,
    ) -> QualityStatus:
        """
        Validates train header definition: number format, uniqueness, and station references.
        """
        findings: List[ValidationFinding] = []
        num_clean = train_number.strip().upper()
        record_id = num_clean or f"UNKNOWN_TRN_{len(seen_train_numbers)}"

        # 1. Number presence & uniqueness
        if not num_clean:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.TRAIN,
                    record_id=record_id,
                    rule_code="TRN_MISSING_NUMBER",
                    severity=QualitySeverity.CRITICAL,
                    message="Train record missing train number",
                    source_ref=source_ref,
                )
            )
        elif num_clean in seen_train_numbers:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.TRAIN,
                    record_id=num_clean,
                    rule_code="TRN_DUPLICATE_NUMBER",
                    severity=QualitySeverity.CRITICAL,
                    message=f"Duplicate train number '{num_clean}' encountered",
                    source_ref=source_ref,
                )
            )
        else:
            seen_train_numbers.add(num_clean)

        # 2. Name presence
        if not train_name or not train_name.strip():
            findings.append(
                ValidationFinding(
                    record_type=RecordType.TRAIN,
                    record_id=record_id,
                    rule_code="TRN_MISSING_NAME",
                    severity=QualitySeverity.ERROR,
                    message=f"Train '{num_clean}' missing train service name",
                    source_ref=source_ref,
                )
            )

        # 3. Origin & Destination station reference integrity
        orig_clean = origin_code.strip().upper()
        dest_clean = destination_code.strip().upper()

        if not orig_clean or orig_clean not in valid_station_codes:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.TRAIN,
                    record_id=record_id,
                    rule_code="TRN_UNRESOLVED_ORIGIN",
                    severity=QualitySeverity.ERROR,
                    message=f"Train '{num_clean}' origin station '{orig_clean}' not found in station master",
                    details={"origin_code": orig_clean},
                    source_ref=source_ref,
                )
            )

        if not dest_clean or dest_clean not in valid_station_codes:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.TRAIN,
                    record_id=record_id,
                    rule_code="TRN_UNRESOLVED_DESTINATION",
                    severity=QualitySeverity.ERROR,
                    message=f"Train '{num_clean}' destination station '{dest_clean}' not found in station master",
                    details={"destination_code": dest_clean},
                    source_ref=source_ref,
                )
            )

        # 4. Distinct endpoints
        if orig_clean and dest_clean and orig_clean == dest_clean:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.TRAIN,
                    record_id=record_id,
                    rule_code="TRN_IDENTICAL_ENDPOINTS",
                    severity=QualitySeverity.ERROR,
                    message=f"Train '{num_clean}' has identical origin and destination ({orig_clean})",
                    source_ref=source_ref,
                )
            )

        self.findings.extend(findings)

        if any(f.severity in (QualitySeverity.CRITICAL, QualitySeverity.ERROR) for f in findings):
            return QualityStatus.REJECTED
        if any(f.severity == QualitySeverity.WARNING for f in findings):
            return QualityStatus.REVIEW_REQUIRED
        return QualityStatus.VALID

    # ==========================================
    # 3. Timetable Schedule Sequence Rules
    # ==========================================
    def validate_train_schedule(
        self,
        train_number: str,
        stops: Sequence[Any],
        valid_station_codes: Set[str],
        expected_origin: Optional[str] = None,
        expected_dest: Optional[str] = None,
        source_ref: Optional[str] = None,
    ) -> QualityStatus:
        """
        Validates the complete timetable schedule sequence for a train:
        - Non-empty schedule
        - Strictly increasing sequence numbers
        - No duplicate stop sequences
        - Valid station references
        - Time chronology and positive dwell duration
        - Day offset monotonicity
        - Endpoint alignment with train header
        """
        findings: List[ValidationFinding] = []
        train_num = train_number.strip().upper()

        if not stops or len(stops) == 0:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.SCHEDULE,
                    record_id=f"{train_num}_SCHEDULE",
                    rule_code="SCH_EMPTY_SCHEDULE",
                    severity=QualitySeverity.ERROR,
                    message=f"Train '{train_num}' has an empty timetable stop list",
                    source_ref=source_ref,
                )
            )
            self.findings.extend(findings)
            return QualityStatus.REJECTED

        prev_seq: Optional[int] = None
        seen_seqs: Set[int] = set()
        prev_arr_time: Optional[time] = None
        prev_dep_time: Optional[time] = None
        prev_day_offset: Optional[int] = None
        has_incomplete_timing = False
        has_waypoint_or_zero_dwell = False

        for idx, stop in enumerate(stops):
            stn_code = (getattr(stop, "station_code", None) or stop.get("station_code") or "").strip().upper()
            seq = getattr(stop, "stop_sequence", None)
            if seq is None and isinstance(stop, dict):
                seq = stop.get("stop_sequence")

            arr = getattr(stop, "arrival_time", None)
            if arr is None and isinstance(stop, dict):
                arr = stop.get("arrival_time")

            dep = getattr(stop, "departure_time", None)
            if dep is None and isinstance(stop, dict):
                dep = stop.get("departure_time")

            day_off = getattr(stop, "day_offset", None)
            if day_off is None and isinstance(stop, dict):
                day_off = stop.get("day_offset")

            stop_id = f"{train_num}_STOP_{seq if seq is not None else idx}"

            # 1. Station code reference validation
            if not stn_code or stn_code not in valid_station_codes:
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.SCHEDULE,
                        record_id=stop_id,
                        rule_code="SCH_UNRESOLVED_STATION",
                        severity=QualitySeverity.ERROR,
                        message=f"Schedule stop #{seq} references unknown station code '{stn_code}'",
                        details={"train_number": train_num, "station_code": stn_code},
                        source_ref=source_ref,
                    )
                )

            # 2. Sequence monotonicity & uniqueness
            if seq is None or not isinstance(seq, int) or seq <= 0:
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.SCHEDULE,
                        record_id=stop_id,
                        rule_code="SCH_INVALID_SEQUENCE",
                        severity=QualitySeverity.CRITICAL,
                        message=f"Invalid stop sequence value '{seq}' on train '{train_num}'",
                        source_ref=source_ref,
                    )
                )
            else:
                if seq in seen_seqs:
                    findings.append(
                        ValidationFinding(
                            record_type=RecordType.SCHEDULE,
                            record_id=stop_id,
                            rule_code="SCH_DUPLICATE_SEQUENCE",
                            severity=QualitySeverity.CRITICAL,
                            message=f"Duplicate stop sequence '{seq}' found in train '{train_num}' timetable",
                            source_ref=source_ref,
                        )
                    )
                seen_seqs.add(seq)

                if prev_seq is not None and seq <= prev_seq:
                    findings.append(
                        ValidationFinding(
                            record_type=RecordType.SCHEDULE,
                            record_id=stop_id,
                            rule_code="SCH_NON_MONOTONIC_SEQUENCE",
                            severity=QualitySeverity.ERROR,
                            message=f"Non-increasing sequence ({prev_seq} -> {seq}) in train '{train_num}'",
                            source_ref=source_ref,
                        )
                    )
                prev_seq = seq

            # 3. Timing checks
            is_origin_stop = (idx == 0)
            is_final_stop = (idx == len(stops) - 1)

            # Incomplete timing tracking
            if (not is_origin_stop and arr is None) or (not is_final_stop and dep is None):
                has_incomplete_timing = True
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.SCHEDULE,
                        record_id=stop_id,
                        rule_code="SCH_INCOMPLETE_TIMING",
                        severity=QualitySeverity.INFO,
                        message=f"Stop #{seq} at {stn_code} has incomplete commercial timing",
                        source_ref=source_ref,
                    )
                )

            # Equal arrival and departure time (0 dwell time)
            if arr is not None and dep is not None and arr == dep:
                has_waypoint_or_zero_dwell = True
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.SCHEDULE,
                        record_id=stop_id,
                        rule_code="SCH_ZERO_DWELL_WAYPOINT",
                        severity=QualitySeverity.INFO,
                        message=f"Stop #{seq} at {stn_code} has equal arrival and departure times ({arr})",
                        source_ref=source_ref,
                    )
                )

            # Inversion on same stop (departure before arrival without next day)
            if arr is not None and dep is not None and dep < arr:
                # If departure is earlier than arrival at the same station, it is only possible if midnight passed during dwell
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.SCHEDULE,
                        record_id=stop_id,
                        rule_code="SCH_NEGATIVE_STATION_DWELL",
                        severity=QualitySeverity.WARNING,
                        message=f"Stop #{seq} at {stn_code} departs ({dep}) before arrival ({arr})",
                        details={"arrival": str(arr), "departure": str(dep)},
                        source_ref=source_ref,
                    )
                )

            # 4. Day offset sanity
            if day_off is None:
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.SCHEDULE,
                        record_id=stop_id,
                        rule_code="SCH_MISSING_DAY_OFFSET",
                        severity=QualitySeverity.WARNING,
                        message=f"Stop #{seq} at {stn_code} has unknown or unassigned day_offset",
                        source_ref=source_ref,
                    )
                )
            else:
                if day_off < 0 or day_off > 10:
                    findings.append(
                        ValidationFinding(
                            record_type=RecordType.SCHEDULE,
                            record_id=stop_id,
                            rule_code="SCH_ANOMALOUS_DAY_OFFSET",
                            severity=QualitySeverity.ERROR,
                            message=f"Stop #{seq} at {stn_code} has anomalous day_offset ({day_off})",
                            source_ref=source_ref,
                        )
                    )
                if prev_day_offset is not None and day_off < prev_day_offset:
                    findings.append(
                        ValidationFinding(
                            record_type=RecordType.SCHEDULE,
                            record_id=stop_id,
                            rule_code="SCH_DECREASING_DAY_OFFSET",
                            severity=QualitySeverity.ERROR,
                            message=f"Day offset decreased from {prev_day_offset} to {day_off} at stop #{seq}",
                            source_ref=source_ref,
                        )
                    )
                prev_day_offset = day_off

        # 5. Endpoint Alignment
        if expected_origin and stops:
            first_stn = (getattr(stops[0], "station_code", None) or stops[0].get("station_code") or "").strip().upper()
            if first_stn != expected_origin.strip().upper():
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.SCHEDULE,
                        record_id=f"{train_num}_ORIGIN_ALIGNMENT",
                        rule_code="SCH_ORIGIN_ENDPOINT_MISMATCH",
                        severity=QualitySeverity.WARNING,
                        message=f"First timetable stop '{first_stn}' does not match train header origin '{expected_origin}'",
                        details={"first_stop": first_stn, "header_origin": expected_origin},
                        source_ref=source_ref,
                    )
                )

        if expected_dest and stops:
            last_stn = (getattr(stops[-1], "station_code", None) or stops[-1].get("station_code") or "").strip().upper()
            if last_stn != expected_dest.strip().upper():
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.SCHEDULE,
                        record_id=f"{train_num}_DEST_ALIGNMENT",
                        rule_code="SCH_DEST_ENDPOINT_MISMATCH",
                        severity=QualitySeverity.WARNING,
                        message=f"Last timetable stop '{last_stn}' does not match train header destination '{expected_dest}'",
                        details={"last_stop": last_stn, "header_destination": expected_dest},
                        source_ref=source_ref,
                    )
                )

        self.findings.extend(findings)

        if any(f.severity in (QualitySeverity.CRITICAL, QualitySeverity.ERROR) for f in findings):
            return QualityStatus.REJECTED
        if any(f.severity == QualitySeverity.WARNING for f in findings):
            return QualityStatus.REVIEW_REQUIRED
        if has_incomplete_timing:
            return QualityStatus.RETAINED_INCOMPLETE
        return QualityStatus.VALID

    # ==========================================
    # 4. Operating Calendar Integrity Rules
    # ==========================================
    def validate_running_calendar(
        self,
        train_number: str,
        runs_on_days: Optional[Sequence[int]],
        calendar_entry: Optional[Dict[str, Any]] = None,
        source_ref: Optional[str] = None,
    ) -> QualityStatus:
        """
        Validates train operating days and calendar provenance:
        - Calendar must exist and not be empty.
        - Days must be valid integers in range 0..6 (0=Mon, 6=Sun).
        - No duplicate days.
        - Verification evidence / table citation check.
        """
        findings: List[ValidationFinding] = []
        train_num = train_number.strip().upper()
        record_id = f"CALENDAR_{train_num}"

        if runs_on_days is None or len(runs_on_days) == 0:
            findings.append(
                ValidationFinding(
                    record_type=RecordType.CALENDAR,
                    record_id=record_id,
                    rule_code="CAL_AWAITING_CALENDAR",
                    severity=QualitySeverity.WARNING,
                    message=f"Train '{train_num}' lacks verified operating days calendar (awaiting official publication)",
                    source_ref=source_ref,
                )
            )
            self.findings.extend(findings)
            return QualityStatus.REVIEW_REQUIRED

        seen_days = set()
        for d in runs_on_days:
            if not isinstance(d, int) or d < 0 or d > 6:
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.CALENDAR,
                        record_id=record_id,
                        rule_code="CAL_INVALID_DAY_INTEGER",
                        severity=QualitySeverity.ERROR,
                        message=f"Invalid weekday integer '{d}' in calendar for train '{train_num}' (must be 0..6)",
                        source_ref=source_ref,
                    )
                )
            if d in seen_days:
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.CALENDAR,
                        record_id=record_id,
                        rule_code="CAL_DUPLICATE_DAY_INTEGER",
                        severity=QualitySeverity.ERROR,
                        message=f"Duplicate weekday integer '{d}' in calendar for train '{train_num}'",
                        source_ref=source_ref,
                    )
                )
            seen_days.add(d)

        # Check provenance details if entry dictionary provided
        if calendar_entry:
            source_doc = calendar_entry.get("source_document") or calendar_entry.get("source")
            is_verified = calendar_entry.get("is_verified") or calendar_entry.get("official_verified")
            if not source_doc:
                findings.append(
                    ValidationFinding(
                        record_type=RecordType.CALENDAR,
                        record_id=record_id,
                        rule_code="CAL_UNVERIFIED_PROVENANCE",
                        severity=QualitySeverity.WARNING,
                        message=f"Calendar for train '{train_num}' lacks documented official source citation",
                        source_ref=source_ref,
                    )
                )

        self.findings.extend(findings)

        if any(f.severity in (QualitySeverity.CRITICAL, QualitySeverity.ERROR) for f in findings):
            return QualityStatus.REJECTED
        if any(f.severity == QualitySeverity.WARNING for f in findings):
            return QualityStatus.REVIEW_REQUIRED
        return QualityStatus.VALID

    # ==========================================
    # 5. Audit Report Compilation
    # ==========================================
    def compile_audit_report(
        self,
        stations_summary: CategoryQualitySummary,
        trains_summary: CategoryQualitySummary,
        schedules_summary: CategoryQualitySummary,
        calendars_summary: CategoryQualitySummary,
        source_artifacts: Optional[Dict[str, str]] = None,
    ) -> DataQualityAuditSummary:
        """
        Aggregates all collected validation findings into a reproducible, deterministic summary.
        """
        now = datetime.now()
        report_id = f"quality_audit_{now.strftime('%Y%m%d_%H%M%S')}"

        sev_counter = Counter(f.severity.value for f in self.findings)
        cat_counter = Counter(f.record_type.value for f in self.findings)
        rule_counter = Counter(f.rule_code for f in self.findings)

        top_rules = [
            {"rule_code": code, "count": count}
            for code, count in rule_counter.most_common(15)
        ]

        total_inspected = (
            stations_summary.total_inspected
            + trains_summary.total_inspected
            + schedules_summary.total_inspected
            + calendars_summary.total_inspected
        )

        # Compute deterministic hash of all findings for reproducibility verification
        findings_signatures = sorted(
            f"{f.record_type.value}:{f.record_id}:{f.rule_code}:{f.severity.value}"
            for f in self.findings
        )
        content_for_hash = "\n".join(findings_signatures).encode("utf-8")
        reproducibility_hash = hashlib.sha256(content_for_hash).hexdigest()

        return DataQualityAuditSummary(
            report_id=report_id,
            generated_at=now.isoformat(),
            total_records_inspected=total_inspected,
            stations=stations_summary,
            trains=trains_summary,
            schedules=schedules_summary,
            calendars=calendars_summary,
            findings_by_severity=dict(sev_counter),
            findings_by_category=dict(cat_counter),
            top_failure_rules=top_rules,
            data_freshness_statement=self.DATA_FRESHNESS_STATEMENT,
            source_artifacts=source_artifacts or {},
            reproducibility_hash=reproducibility_hash,
        )

