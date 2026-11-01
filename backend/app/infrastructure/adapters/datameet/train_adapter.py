from pathlib import Path
import json
import math
import hashlib
import datetime
from types import MappingProxyType
from typing import Iterable, Union

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
from app.infrastructure.adapters.datameet.train_models import (
    DataMeetTrainRecord,
    AcceptedTrainRecord,
    TrainQuarantineRecord,
    TrainAdapterResult,
)


class DataMeetTrainAdapter:
    """
    Dedicated source adapter for DataMeet Railways GeoJSON train routes dataset.

    Parses raw train route features into immutable DataMeetTrainRecord entities.
    Strictly quarantines missing required metadata (train number, train name,
    origin, destination, identical endpoints, duplicate train numbers) and unresolved
    station references when a verified station foundation is provided.
    Preserves optional metadata (departure, arrival, distance, duration, route geometry)
    as None/empty with validation warnings rather than quarantining viable train headers.
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
    ) -> TrainAdapterResult:
        """
        Process a local DataMeet trains.json GeoJSON file.

        Args:
            file_path: Path to the local GeoJSON file.
            valid_station_codes: Optional iterable of verified station codes (e.g. from TW-103B).
                                 When supplied, train endpoints not in this collection are quarantined.

        Returns:
            TrainAdapterResult containing immutable accepted DataMeetTrainRecord entities,
            full accepted audit records, quarantined records, and complete cryptographic/execution provenance.

        Raises:
            SourceFileNotFoundError: If the file does not exist on disk.
            SourceIOError: If an I/O error occurs reading the file or path is a directory.
            SourceEncodingError: If the file cannot be decoded as UTF-8.
            MalformedSourceError: If the file is not valid JSON or violates GeoJSON structure.
        """
        path = Path(file_path)
        if not path.exists():
            raise SourceFileNotFoundError(f"DataMeet source file not found: {path}")

        if not path.is_file():
            raise SourceIOError(f"DataMeet source path is not a regular file: {path}")

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

        if not isinstance(payload, dict):
            raise MalformedSourceError(f"Root GeoJSON element in '{path}' must be a JSON object")

        if payload.get("type") != "FeatureCollection":
            raise MalformedSourceError(
                f"Root GeoJSON element in '{path}' must have type 'FeatureCollection', got '{payload.get('type')}'"
            )

        features = payload.get("features")
        if not isinstance(features, list):
            raise MalformedSourceError(f"GeoJSON 'features' attribute in '{path}' must be a list")

        # Normalize valid station codes set if provided
        verified_station_set: set[str] | None = None
        if valid_station_codes is not None:
            verified_station_set = {
                code.strip().upper()
                for code in valid_station_codes
                if isinstance(code, str) and code.strip()
            }

        # =================================================================
        # PASS 1: Index train numbers to detect all duplicate number groups
        # =================================================================
        number_occurrences: dict[str, list[int]] = {}
        for idx, feat in enumerate(features):
            if isinstance(feat, dict) and isinstance(feat.get("properties"), dict):
                raw_number = feat["properties"].get("number")
                if raw_number is not None and isinstance(raw_number, str):
                    clean_number = raw_number.strip()
                    if clean_number:
                        number_occurrences.setdefault(clean_number, []).append(idx)

        duplicate_numbers = {num for num, indices in number_occurrences.items() if len(indices) > 1}

        # =================================================================
        # PASS 2: Feature validation and record instantiation
        # =================================================================
        accepted_records: list[AcceptedTrainRecord] = []
        quarantined_records: list[TrainQuarantineRecord] = []
        rejection_reason_counts: dict[str, int] = {}

        source_file_str = str(path)

        for idx, feat in enumerate(features):
            reasons: list[str] = []
            messages: list[str] = []
            warnings: list[str] = []

            orig_number: str | None = None
            orig_name: str | None = None
            orig_from_code: str | None = None
            orig_to_code: str | None = None
            from_name: str | None = None
            to_name: str | None = None
            train_type: str | None = None
            zone: str | None = None
            return_train: str | None = None
            classes_raw: str | None = None

            has_sleeper = False
            has_third_ac = False
            has_second_ac = False
            has_first_ac = False
            has_first_class = False
            has_chair_car = False

            departure_time: datetime.time | None = None
            arrival_time: datetime.time | None = None
            duration_hours: int | None = None
            duration_minutes: int | None = None
            distance_km: float | None = None
            route_coords: list[tuple[float, float]] = []

            if not isinstance(feat, dict):
                reasons.append("MALFORMED_FEATURE_OBJECT")
                messages.append("Feature element must be a JSON dictionary")
            else:
                if feat.get("type") != "Feature":
                    reasons.append("NOT_FEATURE_TYPE")
                    messages.append(f"Element type must be 'Feature', got '{feat.get('type')}'")

                if "properties" not in feat:
                    reasons.append("MISSING_PROPERTIES")
                    messages.append("Feature is missing 'properties' attribute")
                elif not isinstance(feat["properties"], dict):
                    reasons.append("MALFORMED_PROPERTIES_OBJECT")
                    messages.append("Feature properties must be a JSON dictionary")
                else:
                    props = feat["properties"]

                    # 1. Train Number (Required)
                    raw_num = props.get("number")
                    if raw_num is None or not isinstance(raw_num, str) or not raw_num.strip():
                        reasons.append("MISSING_TRAIN_NUMBER")
                        messages.append("Train number is missing, non-string, or whitespace-only")
                    else:
                        orig_num = raw_num.strip()
                        orig_number = orig_num
                        if orig_num in duplicate_numbers:
                            reasons.append("DUPLICATE_TRAIN_NUMBER")
                            collision_count = len(number_occurrences[orig_num])
                            messages.append(
                                f"Train number '{orig_num}' is duplicated across {collision_count} features; all instances collectively quarantined"
                            )

                    # 2. Train Name (Required)
                    raw_name = props.get("name")
                    if raw_name is None or not isinstance(raw_name, str) or not raw_name.strip():
                        reasons.append("MISSING_TRAIN_NAME")
                        messages.append("Train name is missing, non-string, or whitespace-only")
                    else:
                        orig_name = raw_name.strip()

                    # 3. Origin Station Code (Required)
                    raw_from = props.get("from_station_code")
                    if raw_from is None or not isinstance(raw_from, str) or not raw_from.strip():
                        reasons.append("MISSING_ORIGIN_STATION_CODE")
                        messages.append("Origin station code is missing, non-string, or whitespace-only")
                    else:
                        orig_from_code = raw_from.strip().upper()
                        if verified_station_set is not None and orig_from_code not in verified_station_set:
                            reasons.append("UNRESOLVED_ORIGIN_STATION")
                            messages.append(
                                f"Origin station code '{orig_from_code}' not found in verified station foundation"
                            )

                    # 4. Destination Station Code (Required)
                    raw_to = props.get("to_station_code")
                    if raw_to is None or not isinstance(raw_to, str) or not raw_to.strip():
                        reasons.append("MISSING_DESTINATION_STATION_CODE")
                        messages.append("Destination station code is missing, non-string, or whitespace-only")
                    else:
                        orig_to_code = raw_to.strip().upper()
                        if verified_station_set is not None and orig_to_code not in verified_station_set:
                            reasons.append("UNRESOLVED_DESTINATION_STATION")
                            messages.append(
                                f"Destination station code '{orig_to_code}' not found in verified station foundation"
                            )

                    # 5. Distinct Endpoints Check (Required)
                    if orig_from_code and orig_to_code and orig_from_code == orig_to_code:
                        reasons.append("IDENTICAL_ENDPOINT_STATIONS")
                        messages.append(
                            f"Origin station code '{orig_from_code}' and destination station code '{orig_to_code}' cannot be identical"
                        )

                    # Optional Station Names & Attributes
                    raw_from_name = props.get("from_station_name")
                    if isinstance(raw_from_name, str) and raw_from_name.strip():
                        from_name = raw_from_name.strip()

                    raw_to_name = props.get("to_station_name")
                    if isinstance(raw_to_name, str) and raw_to_name.strip():
                        to_name = raw_to_name.strip()

                    raw_type = props.get("type")
                    if isinstance(raw_type, str) and raw_type.strip():
                        train_type = raw_type.strip()

                    raw_zone = props.get("zone")
                    if isinstance(raw_zone, str) and raw_zone.strip():
                        zone = raw_zone.strip()

                    raw_return = props.get("return_train")
                    if isinstance(raw_return, str) and raw_return.strip():
                        return_train = raw_return.strip()

                    raw_classes = props.get("classes")
                    if isinstance(raw_classes, str) and raw_classes.strip():
                        classes_raw = raw_classes.strip()

                    # Coach flags
                    has_sleeper = bool(props.get("sleeper") in (1, "1", True))
                    has_third_ac = bool(props.get("third_ac") in (1, "1", True))
                    has_second_ac = bool(props.get("second_ac") in (1, "1", True))
                    has_first_ac = bool(props.get("first_ac") in (1, "1", True))
                    has_first_class = bool(props.get("first_class") in (1, "1", True))
                    has_chair_car = bool(props.get("chair_car") in (1, "1", True))

                    # Optional Departure Time
                    raw_dep = props.get("departure")
                    if isinstance(raw_dep, str) and raw_dep.strip():
                        try:
                            departure_time = datetime.time.fromisoformat(raw_dep.strip())
                        except ValueError:
                            warnings.append(f"INVALID_DEPARTURE_TIME: '{raw_dep}'")
                    else:
                        warnings.append("MISSING_DEPARTURE_TIME")

                    # Optional Arrival Time
                    raw_arr = props.get("arrival")
                    if isinstance(raw_arr, str) and raw_arr.strip():
                        try:
                            arrival_time = datetime.time.fromisoformat(raw_arr.strip())
                        except ValueError:
                            warnings.append(f"INVALID_ARRIVAL_TIME: '{raw_arr}'")
                    else:
                        warnings.append("MISSING_ARRIVAL_TIME")

                    # Optional Distance
                    raw_dist = props.get("distance")
                    if raw_dist is not None and not isinstance(raw_dist, bool) and isinstance(raw_dist, (int, float)):
                        if raw_dist >= 0:
                            distance_km = float(raw_dist)
                        else:
                            warnings.append(f"NEGATIVE_DISTANCE: {raw_dist}")
                    elif isinstance(raw_dist, str) and raw_dist.strip():
                        try:
                            d_val = float(raw_dist.strip())
                            if d_val >= 0:
                                distance_km = d_val
                            else:
                                warnings.append(f"NEGATIVE_DISTANCE: {d_val}")
                        except ValueError:
                            warnings.append(f"INVALID_DISTANCE_VALUE: '{raw_dist}'")
                    else:
                        warnings.append("MISSING_DISTANCE")

                    # Optional Duration
                    raw_dh = props.get("duration_h")
                    raw_dm = props.get("duration_m")
                    if (
                        raw_dh is not None
                        and not isinstance(raw_dh, bool)
                        and isinstance(raw_dh, (int, float))
                        and raw_dm is not None
                        and not isinstance(raw_dm, bool)
                        and isinstance(raw_dm, (int, float))
                    ):
                        dh = int(raw_dh)
                        dm = int(raw_dm)
                        if dh >= 0 and 0 <= dm < 60:
                            duration_hours = dh
                            duration_minutes = dm
                        else:
                            warnings.append(f"INVALID_DURATION: hours={dh}, minutes={dm}")
                    else:
                        warnings.append("MISSING_OR_INVALID_DURATION")

                # Geometry processing (Optional; non-quarantining)
                geo = feat.get("geometry")
                if geo is None:
                    warnings.append("MISSING_GEOMETRY")
                elif not isinstance(geo, dict):
                    warnings.append("MALFORMED_GEOMETRY_OBJECT")
                elif geo.get("type") != "LineString":
                    warnings.append(f"NOT_LINESTRING_GEOMETRY: '{geo.get('type')}'")
                else:
                    raw_coords = geo.get("coordinates")
                    if not isinstance(raw_coords, (list, tuple)):
                        warnings.append("MALFORMED_COORDINATES_COLLECTION")
                    else:
                        if len(raw_coords) < 2:
                            warnings.append(
                                f"DEGENERATE_LINESTRING: contains {len(raw_coords)} points (requires >= 2)"
                            )

                        for pt_idx, pt in enumerate(raw_coords):
                            if (
                                isinstance(pt, (list, tuple))
                                and len(pt) == 2
                                and not isinstance(pt[0], bool)
                                and isinstance(pt[0], (int, float))
                                and not isinstance(pt[1], bool)
                                and isinstance(pt[1], (int, float))
                                and math.isfinite(pt[0])
                                and math.isfinite(pt[1])
                            ):
                                route_coords.append((float(pt[0]), float(pt[1])))
                            else:
                                warnings.append(f"INVALID_COORDINATE_POINT at index {pt_idx}")

            raw_feature_payload = freeze_payload(feat if isinstance(feat, dict) else {"raw": feat})

            # Route to Quarantine or Accept
            if reasons:
                quarantine_entry = TrainQuarantineRecord(
                    source_file=source_file_str,
                    source_record_index=idx,
                    original_train_number=orig_number,
                    original_train_name=orig_name,
                    rejection_codes=tuple(reasons),
                    validation_messages=tuple(messages),
                    raw_payload=raw_feature_payload,
                )
                quarantined_records.append(quarantine_entry)
                for reason in reasons:
                    rejection_reason_counts[reason] = rejection_reason_counts.get(reason, 0) + 1
            else:
                assert orig_number is not None
                assert orig_name is not None
                assert orig_from_code is not None
                assert orig_to_code is not None

                train_record = DataMeetTrainRecord(
                    number=orig_number,
                    name=orig_name,
                    origin_code=orig_from_code,
                    destination_code=orig_to_code,
                    origin_name=from_name,
                    destination_name=to_name,
                    train_type=train_type,
                    zone=zone,
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    duration_hours=duration_hours,
                    duration_minutes=duration_minutes,
                    distance_km=distance_km,
                    return_train_number=return_train,
                    has_sleeper=has_sleeper,
                    has_third_ac=has_third_ac,
                    has_second_ac=has_second_ac,
                    has_first_ac=has_first_ac,
                    has_first_class=has_first_class,
                    has_chair_car=has_chair_car,
                    classes_raw=classes_raw,
                    route_geometry_coordinates=tuple(route_coords),
                    validation_warnings=tuple(warnings),
                )

                accepted_entry = AcceptedTrainRecord(
                    train=train_record,
                    source_record_index=idx,
                    original_train_number=orig_number,
                    raw_payload=raw_feature_payload,
                )
                accepted_records.append(accepted_entry)

        provenance = SourceProvenance(
            source_repository_url=self.SOURCE_REPO_URL,
            source_file_path=source_file_str,
            repository_snapshot_id=None,
            source_license=self.SOURCE_LICENSE,
            license_evidence=self.LICENSE_EVIDENCE,
            license_qualification=self.LICENSE_QUALIFICATION,
            file_sha256=file_sha256,
            file_size_bytes=file_size_bytes,
            import_timestamp=datetime.datetime.now(datetime.timezone.utc),
            adapter_version=self.ADAPTER_VERSION,
            total_source_records=len(features),
            accepted_records_count=len(accepted_records),
            quarantined_records_count=len(quarantined_records),
            rejection_reason_counts=MappingProxyType(rejection_reason_counts),
        )

        domain_records = tuple(entry.train for entry in accepted_records)

        return TrainAdapterResult(
            records=domain_records,
            accepted=tuple(accepted_records),
            quarantined=tuple(quarantined_records),
            provenance=provenance,
        )

