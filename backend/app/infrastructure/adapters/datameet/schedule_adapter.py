from pathlib import Path
import json
import hashlib
import datetime
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Union

from app.infrastructure.adapters.exceptions import (
    SourceFileNotFoundError,
    SourceIOError,
    SourceEncodingError,
    MalformedSourceError,
)
from app.infrastructure.adapters.datameet.models import (
    SourceProvenance,
    freeze_payload,
)
from app.infrastructure.adapters.datameet.schedule_models import (
    DataMeetScheduleEntry,
    DataMeetTrainSchedule,
    AcceptedScheduleRecord,
    ScheduleQuarantineRecord,
    ScheduleAdapterResult,
)


def _parse_time(raw_val: Any) -> datetime.time | None:
    """Parses a time string into a datetime.time object, or returns None if missing or invalid."""
    if raw_val is None:
        return None
    val_str = str(raw_val).strip()
    if val_str in ("", "None", "null"):
        return None
    parts = val_str.split(":")
    if len(parts) >= 2:
        try:
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            if 0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60:
                return datetime.time(hour=h, minute=m, second=s)
        except (ValueError, TypeError):
            return None
    return None


class DataMeetScheduleAdapter:
    """
    Dedicated source adapter for DataMeet Railways JSON train schedules dataset.

    Reconstructs deterministic stop sequences from ascending source IDs.
    Validates train and station references against external foundation filters.
    Preserves useful station topology without commercial timing as Accepted Incomplete records.
    Strictly avoids zero-defaulting missing day values.
    Preserves repeated station visits, chronological inversions, and high day values with explicit warnings.
    """

    ADAPTER_VERSION = "1.0.0"
    SOURCE_REPO_URL = "https://github.com/datameet/railways"
    SOURCE_LICENSE = "CC0 1.0 Universal"
    LICENSE_EVIDENCE = "Upstream DataMeet Railways README (https://github.com/datameet/railways)"
    LICENSE_QUALIFICATION = "Underlying data provenance has not been independently audited."

    def adapt(
        self,
        file_path: Union[str, Path],
        valid_station_codes: Iterable[str] | None = None,
        valid_train_numbers: Iterable[str] | None = None,
        train_metadata: Mapping[str, Any] | None = None,
    ) -> ScheduleAdapterResult:
        """
        Process a local DataMeet schedules.json file into immutable schedule domain models.

        Args:
            file_path: Path to the local schedules JSON file.
            valid_station_codes: Optional iterable of verified station codes (e.g. from TW-103B).
            valid_train_numbers: Optional iterable of verified train numbers (e.g. from TW-103C).
            train_metadata: Optional mapping of train_number -> metadata (DataMeetTrainRecord or dict)
                            used for endpoint mismatch validation and train name resolution.

        Returns:
            ScheduleAdapterResult containing sequenced train schedules, accepted records,
            quarantined records, and cryptographic provenance.

        Raises:
            SourceFileNotFoundError: If the source file does not exist.
            SourceIOError: If an I/O error occurs reading the file or path is not a regular file.
            SourceEncodingError: If the file cannot be decoded as UTF-8.
            MalformedSourceError: If the file is not valid JSON or root element is not a list.
        """
        path = Path(file_path)
        if not path.exists():
            raise SourceFileNotFoundError(f"DataMeet schedule source file not found: {path}")

        if not path.is_file():
            raise SourceIOError(f"DataMeet schedule source path is not a regular file: {path}")

        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            raise SourceIOError(f"I/O error reading source file '{path}': {exc}") from exc

        file_size_bytes = len(raw_bytes)
        file_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceEncodingError(f"Failed to decode '{path}' as UTF-8: {exc}") from exc

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise MalformedSourceError(
                f"Malformed JSON in '{path}' at line {exc.lineno}, col {exc.colno}: {exc.msg}"
            ) from exc

        if not isinstance(payload, list):
            raise MalformedSourceError(
                f"Root JSON element in '{path}' must be a JSON array, got '{type(payload).__name__}'"
            )

        valid_stations_set: set[str] | None = None
        if valid_station_codes is not None:
            valid_stations_set = {str(c).strip().upper() for c in valid_station_codes}

        valid_trains_set: set[str] | None = None
        if valid_train_numbers is not None:
            valid_trains_set = {str(t).strip() for t in valid_train_numbers}
        elif train_metadata is not None:
            valid_trains_set = {str(t).strip() for t in train_metadata.keys()}

        quarantined_records: list[ScheduleQuarantineRecord] = []
        rejection_reason_counts: dict[str, int] = {}

        # Group valid raw records by train_number for sequencing
        # Key: train_number -> list of dicts with extracted fields
        accepted_by_train: dict[str, list[dict[str, Any]]] = {}

        for idx, raw_record in enumerate(payload):
            if not isinstance(raw_record, dict):
                rejection_codes = ("MALFORMED_RECORD_OBJECT",)
                validation_messages = (f"Record at index {idx} is not a JSON object",)
                rejection_reason_counts["MALFORMED_RECORD_OBJECT"] = (
                    rejection_reason_counts.get("MALFORMED_RECORD_OBJECT", 0) + 1
                )
                quarantined_records.append(
                    ScheduleQuarantineRecord(
                        source_file=path.name,
                        source_record_index=idx,
                        source_record_id=None,
                        original_train_number=None,
                        original_station_code=None,
                        rejection_codes=rejection_codes,
                        validation_messages=validation_messages,
                        raw_payload={},
                    )
                )
                continue

            raw_id = raw_record.get("id")
            raw_train_num = raw_record.get("train_number")
            raw_station_code = raw_record.get("station_code")

            rejection_codes_list: list[str] = []
            validation_messages_list: list[str] = []

            # Check ID
            if raw_id is None or not isinstance(raw_id, int) or isinstance(raw_id, bool):
                rejection_codes_list.append("MISSING_RECORD_ID")
                validation_messages_list.append(f"Record at index {idx} has invalid or missing 'id': {raw_id}")

            # Check train number
            train_num_str: str | None = None
            if raw_train_num is None or not str(raw_train_num).strip():
                rejection_codes_list.append("MISSING_TRAIN_NUMBER")
                validation_messages_list.append(f"Record at index {idx} has missing or empty 'train_number'")
            else:
                train_num_str = str(raw_train_num).strip()

            # Check station code
            station_code_str: str | None = None
            if raw_station_code is None or not str(raw_station_code).strip():
                rejection_codes_list.append("MISSING_STATION_CODE")
                validation_messages_list.append(f"Record at index {idx} has missing or empty 'station_code'")
            else:
                station_code_str = str(raw_station_code).strip().upper()

            # Check external reference validity
            if train_num_str is not None and valid_trains_set is not None:
                if train_num_str not in valid_trains_set:
                    rejection_codes_list.append("UNRESOLVED_TRAIN_REFERENCE")
                    validation_messages_list.append(
                        f"Train number '{train_num_str}' does not resolve against accepted train dataset"
                    )

            if station_code_str is not None and valid_stations_set is not None:
                if station_code_str not in valid_stations_set:
                    rejection_codes_list.append("UNRESOLVED_STATION_REFERENCE")
                    validation_messages_list.append(
                        f"Station code '{station_code_str}' does not resolve against accepted station dataset"
                    )

            if rejection_codes_list:
                for code in rejection_codes_list:
                    rejection_reason_counts[code] = rejection_reason_counts.get(code, 0) + 1

                quarantined_records.append(
                    ScheduleQuarantineRecord(
                        source_file=path.name,
                        source_record_index=idx,
                        source_record_id=raw_id if isinstance(raw_id, int) and not isinstance(raw_id, bool) else None,
                        original_train_number=str(raw_train_num) if raw_train_num is not None else None,
                        original_station_code=str(raw_station_code) if raw_station_code is not None else None,
                        rejection_codes=tuple(rejection_codes_list),
                        validation_messages=tuple(validation_messages_list),
                        raw_payload=raw_record,
                    )
                )
                continue

            # Parse fields for accepted candidate
            raw_station_name = raw_record.get("station_name")
            station_name: str | None = None
            if raw_station_name is not None and str(raw_station_name).strip() not in ("", "None", "null"):
                station_name = str(raw_station_name).strip()

            arr_time = _parse_time(raw_record.get("arrival"))
            dep_time = _parse_time(raw_record.get("departure"))

            warnings: list[str] = ["MISSING_DISTANCE"]

            is_arr_none = arr_time is None
            is_dep_none = dep_time is None

            if is_arr_none and is_dep_none:
                is_timing_complete = False
                warnings.append("INCOMPLETE_TIMING_INFO")
                is_commercial_halt = False
                is_waypoint = False
                has_equal_arr_dep = False
            else:
                is_timing_complete = True
                if arr_time is not None and dep_time is not None and arr_time == dep_time:
                    has_equal_arr_dep = True
                    warnings.append("EQUAL_ARRIVAL_DEPARTURE_TIME")
                    is_commercial_halt = False
                    is_waypoint = True
                else:
                    has_equal_arr_dep = False
                    is_commercial_halt = True
                    is_waypoint = False

            raw_day = raw_record.get("day")
            day: int | None = None
            day_offset: int | None = None

            if raw_day is None or str(raw_day).strip() in ("", "None", "null"):
                day = None
                day_offset = None
                warnings.append("MISSING_DAY_FIELD")
            else:
                try:
                    d_int = int(raw_day)
                    day = d_int
                    day_offset = d_int - 1
                    if d_int > 6:
                        warnings.append("SUSPICIOUS_DAY_VALUE")
                except (ValueError, TypeError):
                    day = None
                    day_offset = None
                    warnings.append("MISSING_DAY_FIELD")

            item = {
                "source_record_index": idx,
                "source_record_id": raw_id,
                "train_number": train_num_str,
                "station_code": station_code_str,
                "station_name": station_name,
                "arrival_time": arr_time,
                "departure_time": dep_time,
                "day": day,
                "day_offset": day_offset,
                "is_commercial_halt": is_commercial_halt,
                "is_waypoint": is_waypoint,
                "is_timing_complete": is_timing_complete,
                "has_equal_arrival_departure": has_equal_arr_dep,
                "validation_warnings": warnings,
                "raw_payload": raw_record,
            }

            if train_num_str not in accepted_by_train:
                accepted_by_train[train_num_str] = []
            accepted_by_train[train_num_str].append(item)

        # Reconstruct stop sequences per train and detect route-level warnings
        train_schedules: list[DataMeetTrainSchedule] = []
        all_accepted_records: list[AcceptedScheduleRecord] = []

        for train_num, stops in accepted_by_train.items():
            # Deterministic ordering: ascending source ID
            stops.sort(key=lambda s: s["source_record_id"])

            schedule_warnings: list[str] = []

            # Check repeated stations along route
            seen_stations: set[str] = set()
            repeated_stations: set[str] = set()
            for s in stops:
                st_code = s["station_code"]
                if st_code in seen_stations:
                    repeated_stations.add(st_code)
                    s["validation_warnings"].append("REPEATED_STATION_IN_ROUTE")
                seen_stations.add(st_code)

            if repeated_stations:
                schedule_warnings.append("REPEATED_STATION_IN_ROUTE")

            # Check chronological inversions
            prev_tot_minutes: int | None = None
            has_chronological_inversion = False
            for s in stops:
                t = s["departure_time"] if s["departure_time"] is not None else s["arrival_time"]
                d = s["day"]
                if t is not None and d is not None:
                    tot_minutes = (d - 1) * 1440 + t.hour * 60 + t.minute
                    if prev_tot_minutes is not None and tot_minutes < prev_tot_minutes:
                        has_chronological_inversion = True
                        s["validation_warnings"].append("CHRONOLOGICAL_INVERSION")
                    prev_tot_minutes = tot_minutes

            if has_chronological_inversion:
                schedule_warnings.append("CHRONOLOGICAL_INVERSION")

            # Resolve train metadata endpoints and train name
            train_name: str | None = None
            if train_metadata is not None and train_num in train_metadata:
                meta = train_metadata[train_num]
                train_name = getattr(meta, "name", None) or (
                    meta.get("name") if isinstance(meta, Mapping) else None
                )
                meta_origin = getattr(meta, "origin_code", None) or (
                    meta.get("origin_code") if isinstance(meta, Mapping) else None
                ) or (meta.get("from_station_code") if isinstance(meta, Mapping) else None)
                meta_dest = getattr(meta, "destination_code", None) or (
                    meta.get("destination_code") if isinstance(meta, Mapping) else None
                ) or (meta.get("to_station_code") if isinstance(meta, Mapping) else None)

                if meta_origin and stops and stops[0]["station_code"] != meta_origin:
                    schedule_warnings.append("ORIGIN_STATION_MISMATCH")
                    stops[0]["validation_warnings"].append("ORIGIN_STATION_MISMATCH")

                if meta_dest and stops and stops[-1]["station_code"] != meta_dest:
                    schedule_warnings.append("DESTINATION_STATION_MISMATCH")
                    stops[-1]["validation_warnings"].append("DESTINATION_STATION_MISMATCH")

            if train_name is None:
                # Find first non-empty train_name from raw records
                for s in stops:
                    raw_tn = s["raw_payload"].get("train_name")
                    if raw_tn is not None and str(raw_tn).strip() not in ("", "None", "null"):
                        train_name = str(raw_tn).strip()
                        break

            # Build DataMeetScheduleEntry instances with 1-based stop_sequence
            entries_list: list[DataMeetScheduleEntry] = []
            for seq_idx, s in enumerate(stops, start=1):
                entry = DataMeetScheduleEntry(
                    source_record_id=s["source_record_id"],
                    train_number=s["train_number"],
                    station_code=s["station_code"],
                    stop_sequence=seq_idx,
                    station_name=s["station_name"],
                    arrival_time=s["arrival_time"],
                    departure_time=s["departure_time"],
                    day=s["day"],
                    day_offset=s["day_offset"],
                    is_commercial_halt=s["is_commercial_halt"],
                    is_waypoint=s["is_waypoint"],
                    is_timing_complete=s["is_timing_complete"],
                    has_equal_arrival_departure=s["has_equal_arrival_departure"],
                    distance_km=None,
                    validation_warnings=tuple(s["validation_warnings"]),
                )
                entries_list.append(entry)

                accepted_rec = AcceptedScheduleRecord(
                    entry=entry,
                    source_record_index=s["source_record_index"],
                    original_train_number=s["train_number"],
                    original_station_code=s["station_code"],
                    raw_payload=s["raw_payload"],
                )
                all_accepted_records.append(accepted_rec)

            train_schedule = DataMeetTrainSchedule(
                train_number=train_num,
                train_name=train_name,
                origin_code=stops[0]["station_code"] if stops else "",
                destination_code=stops[-1]["station_code"] if stops else "",
                total_stops=len(entries_list),
                entries=tuple(entries_list),
                schedule_warnings=tuple(schedule_warnings),
            )
            train_schedules.append(train_schedule)

        # Sort all accepted records by source_record_index to preserve dataset audit ordering
        all_accepted_records.sort(key=lambda a: a.source_record_index)
        quarantined_records.sort(key=lambda q: q.source_record_index)

        provenance = SourceProvenance(
            source_repository_url=self.SOURCE_REPO_URL,
            source_file_path=str(path.resolve()),
            source_license=self.SOURCE_LICENSE,
            license_evidence=self.LICENSE_EVIDENCE,
            license_qualification=self.LICENSE_QUALIFICATION,
            file_sha256=file_sha256,
            file_size_bytes=file_size_bytes,
            adapter_version=self.ADAPTER_VERSION,
            total_source_records=len(payload),
            accepted_records_count=len(all_accepted_records),
            quarantined_records_count=len(quarantined_records),
            rejection_reason_counts=MappingProxyType(rejection_reason_counts),
        )

        return ScheduleAdapterResult(
            train_schedules=tuple(train_schedules),
            records=tuple(a.entry for a in all_accepted_records),
            accepted=tuple(all_accepted_records),
            quarantined=tuple(quarantined_records),
            provenance=provenance,
        )

