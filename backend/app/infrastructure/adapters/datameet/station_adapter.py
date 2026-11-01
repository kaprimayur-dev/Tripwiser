from pathlib import Path
import json
import math
import hashlib
import datetime
from types import MappingProxyType
from typing import Union

from app.domain.models.station import Station
from app.infrastructure.adapters.exceptions import (
    SourceFileNotFoundError,
    SourceIOError,
    SourceEncodingError,
    MalformedSourceError,
)
from app.infrastructure.adapters.datameet.models import (
    AcceptedRecord,
    QuarantineRecord,
    SourceProvenance,
    AdapterResult,
    freeze_payload,
)


class DataMeetStationAdapter:
    """
    Dedicated source adapter for DataMeet Railways GeoJSON station dataset.

    Reads a local GeoJSON file, applies strict validation and coordinate normalization,
    instantiates existing Station domain models for valid features, preserves original
    accepted payloads for auditability, and routes invalid or conflicting features to
    quarantine with diagnostic metadata and provenance.
    """

    ADAPTER_VERSION = "1.0.0"
    SOURCE_REPO_URL = "https://github.com/datameet/railways"
    SOURCE_LICENSE = "CC0 1.0 Universal"
    LICENSE_EVIDENCE = "Upstream DataMeet Railways README (https://github.com/datameet/railways)"
    LICENSE_QUALIFICATION = "Underlying data provenance has not been independently audited."

    def adapt(self, file_path: Union[str, Path]) -> AdapterResult:
        """
        Process a local DataMeet stations.json file.

        Args:
            file_path: Path to the local GeoJSON file.

        Returns:
            AdapterResult containing immutable accepted Station models, full accepted
            audit records, quarantined records, and complete cryptographic/execution provenance.

        Raises:
            SourceFileNotFoundError: If the file does not exist on disk.
            SourceIOError: If an I/O error occurs reading the file or path is a directory.
            SourceEncodingError: If the file is not valid UTF-8.
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
            raise MalformedSourceError(f"Malformed JSON in '{path}' at line {exc.lineno}, col {exc.colno}: {exc.msg}") from exc

        if not isinstance(payload, dict):
            raise MalformedSourceError(f"Root GeoJSON element in '{path}' must be a JSON object")

        if payload.get("type") != "FeatureCollection":
            raise MalformedSourceError(f"Root GeoJSON element in '{path}' must have type 'FeatureCollection', got '{payload.get('type')}'")

        features = payload.get("features")
        if not isinstance(features, list):
            raise MalformedSourceError(f"GeoJSON 'features' attribute in '{path}' must be a list")

        # =================================================================
        # PASS 1: Index station codes to detect all duplicate code groups
        # =================================================================
        code_occurrences: dict[str, list[int]] = {}
        for idx, feat in enumerate(features):
            if isinstance(feat, dict) and isinstance(feat.get("properties"), dict):
                raw_code = feat["properties"].get("code")
                if raw_code is not None and isinstance(raw_code, str):
                    clean_code = raw_code.strip()
                    if clean_code:
                        code_occurrences.setdefault(clean_code, []).append(idx)

        duplicate_codes = {code for code, indices in code_occurrences.items() if len(indices) > 1}

        # =================================================================
        # PASS 2: Strict feature validation and domain model instantiation
        # =================================================================
        accepted_records: list[AcceptedRecord] = []
        quarantined_records: list[QuarantineRecord] = []
        rejection_reason_counts: dict[str, int] = {}

        source_file_str = str(path)

        for idx, feat in enumerate(features):
            reasons: list[str] = []
            messages: list[str] = []
            orig_code: str | None = None
            orig_name: str | None = None
            lat: float | None = None
            lon: float | None = None
            state: str | None = None
            zone: str | None = None

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
                    # Station Code
                    raw_code = props.get("code")
                    if raw_code is None or not isinstance(raw_code, str) or not raw_code.strip():
                        reasons.append("MISSING_STATION_CODE")
                        messages.append("Station code is missing, non-string, or whitespace-only")
                    else:
                        orig_code = raw_code.strip()
                        # Collective Duplicate Code Quarantine: all instances of duplicate codes are quarantined
                        if orig_code in duplicate_codes:
                            reasons.append("DUPLICATE_STATION_CODE")
                            collision_count = len(code_occurrences[orig_code])
                            messages.append(
                                f"Station code '{orig_code}' is duplicated across {collision_count} features; all instances collectively quarantined"
                            )

                    # Station Name
                    raw_name = props.get("name")
                    if raw_name is None or not isinstance(raw_name, str) or not raw_name.strip():
                        reasons.append("MISSING_STATION_NAME")
                        messages.append("Station name is missing, non-string, or whitespace-only")
                    else:
                        orig_name = raw_name.strip()

                    # Optional metadata
                    raw_state = props.get("state")
                    if isinstance(raw_state, str) and raw_state.strip():
                        state = raw_state.strip()
                    raw_zone = props.get("zone")
                    if isinstance(raw_zone, str) and raw_zone.strip():
                        zone = raw_zone.strip()

                # Geometry and Coordinates
                if "geometry" not in feat:
                    reasons.append("MISSING_GEOMETRY")
                    messages.append("Feature is missing 'geometry' attribute")
                else:
                    geo = feat["geometry"]
                    if geo is None:
                        reasons.append("NULL_GEOMETRY")
                        messages.append("Feature geometry is null")
                    elif not isinstance(geo, dict):
                        reasons.append("MALFORMED_GEOMETRY_OBJECT")
                        messages.append("Feature geometry must be a dictionary")
                    else:
                        if "type" not in geo or not geo.get("type"):
                            reasons.append("MISSING_GEOMETRY_TYPE")
                            messages.append("Geometry is missing 'type' attribute")
                        elif geo.get("type") != "Point":
                            reasons.append("NOT_POINT_GEOMETRY")
                            messages.append(f"Geometry type must be 'Point', got '{geo.get('type')}'")

                        coords = geo.get("coordinates")
                        if coords is None:
                            reasons.append("MISSING_COORDINATES")
                            messages.append("Geometry coordinates attribute is missing or null")
                        elif not isinstance(coords, (list, tuple)) or len(coords) != 2:
                            reasons.append("MALFORMED_COORDINATES_COUNT")
                            messages.append(f"Geometry coordinates must be a 2-element sequence [lon, lat], got {coords}")
                        else:
                            raw_lon, raw_lat = coords
                            # Strict type check: boolean is a subclass of int in Python, so exclude bool explicitly
                            if (
                                isinstance(raw_lon, bool)
                                or isinstance(raw_lat, bool)
                                or not isinstance(raw_lon, (int, float))
                                or not isinstance(raw_lat, (int, float))
                            ):
                                reasons.append("NON_NUMERIC_COORDINATE")
                                messages.append(
                                    f"Coordinates must be numeric, got types: lon={type(raw_lon).__name__}, lat={type(raw_lat).__name__}"
                                )
                            elif not (math.isfinite(raw_lon) and math.isfinite(raw_lat)):
                                reasons.append("NON_FINITE_COORDINATE")
                                messages.append(f"Coordinates must be finite numbers, got lon={raw_lon}, lat={raw_lat}")
                            else:
                                # GeoJSON standard: [longitude, latitude] -> Invert explicitly to (lat, lon)
                                lat = float(raw_lat)
                                lon = float(raw_lon)

                                if lat < -90.0 or lat > 90.0:
                                    reasons.append("OUT_OF_BOUNDS_LATITUDE")
                                    messages.append(f"Latitude {lat} is out of bounds [-90.0, 90.0]")

                                if lon < -180.0 or lon > 180.0:
                                    reasons.append("OUT_OF_BOUNDS_LONGITUDE")
                                    messages.append(f"Longitude {lon} is out of bounds [-180.0, 180.0]")

                                if lat == 0.0 and lon == 0.0:
                                    reasons.append("DUMMY_ZERO_COORDINATES")
                                    messages.append("Dummy (0.0, 0.0) coordinates are rejected")

            raw_feature_payload = freeze_payload(feat if isinstance(feat, dict) else {"raw": feat})

            # Route to Quarantine or Accept
            if reasons:
                quarantine_entry = QuarantineRecord(
                    source_file=source_file_str,
                    source_record_index=idx,
                    original_station_code=orig_code,
                    original_station_name=orig_name,
                    rejection_codes=tuple(reasons),
                    validation_messages=tuple(messages),
                    raw_payload=raw_feature_payload,
                )
                quarantined_records.append(quarantine_entry)
                for reason in reasons:
                    rejection_reason_counts[reason] = rejection_reason_counts.get(reason, 0) + 1
            else:
                # Guaranteed valid fields -> instantiate pure Station domain model and audit record
                assert orig_code is not None
                assert orig_name is not None
                assert lat is not None
                assert lon is not None

                station = Station(
                    code=orig_code,
                    name=orig_name,
                    latitude=lat,
                    longitude=lon,
                    state=state,
                    zone=zone,
                )
                accepted_entry = AcceptedRecord(
                    station=station,
                    source_record_index=idx,
                    original_station_code=orig_code,
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

        domain_stations = tuple(entry.station for entry in accepted_records)

        return AdapterResult(
            records=domain_stations,
            accepted=tuple(accepted_records),
            quarantined=tuple(quarantined_records),
            provenance=provenance,
        )
