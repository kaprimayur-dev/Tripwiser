import pytest
import json
import math
from pathlib import Path
from dataclasses import FrozenInstanceError

from app.domain.models.station import Station
from app.infrastructure.adapters.datameet.station_adapter import DataMeetStationAdapter
from app.infrastructure.adapters.datameet.models import (
    AcceptedRecord,
    QuarantineRecord,
    SourceProvenance,
    AdapterResult,
)
from app.infrastructure.adapters.exceptions import (
    SourceFileNotFoundError,
    SourceIOError,
    SourceEncodingError,
    MalformedSourceError,
)

DATAMEET_STATIONS_PATH = Path(__file__).resolve().parents[3] / "app" / "infrastructure" / "data" / "sources" / "datameet" / "stations.json"


@pytest.fixture
def adapter():
    return DataMeetStationAdapter()


def _write_geojson(tmp_path: Path, features: list, filename: str = "test_stations.json") -> Path:
    payload = {
        "type": "FeatureCollection",
        "features": features,
    }
    file_path = tmp_path / filename
    file_path.write_text(json.dumps(payload), encoding="utf-8")
    return file_path


# =====================================================================
# A. STRUCTURAL AND POSITIVE VALIDATION TESTS
# =====================================================================

def test_valid_feature_parsing_and_inversion(adapter, tmp_path):
    """Verifies that a valid GeoJSON feature parses into Station and inverts [lon, lat] to (lat, lon)."""
    feature = {
        "type": "Feature",
        "properties": {
            "code": "BDHL",
            "name": "Badhal",
            "state": "Rajasthan",
            "zone": "NWR",
            "address": "Kishangarh Renwal, Rajasthan",
        },
        "geometry": {
            "type": "Point",
            "coordinates": [75.4516454, 27.2520587],
        },
    }
    file_path = _write_geojson(tmp_path, [feature])
    result = adapter.adapt(file_path)

    assert len(result.records) == 1
    assert len(result.accepted) == 1
    assert len(result.quarantined) == 0

    stn = result.records[0]
    assert isinstance(stn, Station)
    assert stn.code == "BDHL"
    assert stn.name == "Badhal"
    # Inversion verification: GeoJSON lon=75.4516454, lat=27.2520587
    assert stn.latitude == pytest.approx(27.2520587)
    assert stn.longitude == pytest.approx(75.4516454)
    assert stn.state == "Rajasthan"
    assert stn.zone == "NWR"


def test_unknown_properties_preserved(adapter, tmp_path):
    """Extra source properties (e.g., address) are preserved in raw_payload, domain model remains clean."""
    feature = {
        "type": "Feature",
        "properties": {
            "code": "TEST",
            "name": "Test Station",
            "extra_field": "Extra Value",
            "custom_metadata": {"id": 123},
        },
        "geometry": {
            "type": "Point",
            "coordinates": [77.22, 28.64],
        },
    }
    file_path = _write_geojson(tmp_path, [feature])
    result = adapter.adapt(file_path)

    assert len(result.records) == 1
    assert len(result.accepted) == 1
    stn = result.records[0]
    assert stn.code == "TEST"
    assert not hasattr(stn, "extra_field")

    # Extra source properties preserved in accepted audit record
    accepted_audit = result.accepted[0]
    assert accepted_audit.raw_payload["properties"]["extra_field"] == "Extra Value"
    assert accepted_audit.raw_payload["properties"]["custom_metadata"]["id"] == 123


# =====================================================================
# B. QUARANTINE: GEOMETRY AND COORDINATE ANOMALIES
# =====================================================================

def test_null_geometry_quarantined(adapter, tmp_path):
    """Features with null geometry are quarantined with NULL_GEOMETRY."""
    feature = {
        "type": "Feature",
        "properties": {"code": "XX-BECE", "name": "XX-BECE"},
        "geometry": None,
    }
    file_path = _write_geojson(tmp_path, [feature])
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 1
    q = result.quarantined[0]
    assert "NULL_GEOMETRY" in q.rejection_codes
    assert q.original_station_code == "XX-BECE"


def test_non_point_geometry_quarantined(adapter, tmp_path):
    """Features with non-Point geometry are quarantined with NOT_POINT_GEOMETRY."""
    feature = {
        "type": "Feature",
        "properties": {"code": "LINE1", "name": "Line Feature"},
        "geometry": {
            "type": "LineString",
            "coordinates": [[75.0, 27.0], [76.0, 28.0]],
        },
    }
    file_path = _write_geojson(tmp_path, [feature])
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 1
    assert "NOT_POINT_GEOMETRY" in result.quarantined[0].rejection_codes


def test_missing_coordinates_quarantined(adapter, tmp_path):
    """Point geometry with missing coordinates is quarantined with MISSING_COORDINATES."""
    feature = {
        "type": "Feature",
        "properties": {"code": "MISS_C", "name": "Missing Coords"},
        "geometry": {"type": "Point", "coordinates": None},
    }
    file_path = _write_geojson(tmp_path, [feature])
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert "MISSING_COORDINATES" in result.quarantined[0].rejection_codes


def test_wrong_coordinate_count_quarantined(adapter, tmp_path):
    """Coordinates not having exactly 2 elements are quarantined with MALFORMED_COORDINATES_COUNT."""
    feature_1 = {
        "type": "Feature",
        "properties": {"code": "ONE_C", "name": "One Coord"},
        "geometry": {"type": "Point", "coordinates": [75.45]},
    }
    feature_3 = {
        "type": "Feature",
        "properties": {"code": "THREE_C", "name": "Three Coords"},
        "geometry": {"type": "Point", "coordinates": [75.45, 27.25, 500.0]},
    }
    file_path = _write_geojson(tmp_path, [feature_1, feature_3])
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 2
    assert all("MALFORMED_COORDINATES_COUNT" in q.rejection_codes for q in result.quarantined)


def test_string_coordinate_rejected(adapter, tmp_path):
    """String coordinates are NOT silently coerced; quarantined with NON_NUMERIC_COORDINATE."""
    feature = {
        "type": "Feature",
        "properties": {"code": "STR_C", "name": "String Coord"},
        "geometry": {"type": "Point", "coordinates": ["75.45", 27.25]},
    }
    file_path = _write_geojson(tmp_path, [feature])
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert "NON_NUMERIC_COORDINATE" in result.quarantined[0].rejection_codes


def test_boolean_coordinate_rejected(adapter, tmp_path):
    """Boolean coordinates are rejected despite being Python int subclasses; quarantined with NON_NUMERIC_COORDINATE."""
    feature_bool_lon = {
        "type": "Feature",
        "properties": {"code": "BOOL_LON", "name": "Bool Lon"},
        "geometry": {"type": "Point", "coordinates": [True, 27.25]},
    }
    feature_bool_lat = {
        "type": "Feature",
        "properties": {"code": "BOOL_LAT", "name": "Bool Lat"},
        "geometry": {"type": "Point", "coordinates": [75.45, False]},
    }
    file_path = _write_geojson(tmp_path, [feature_bool_lon, feature_bool_lat])
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 2
    assert all("NON_NUMERIC_COORDINATE" in q.rejection_codes for q in result.quarantined)


def test_non_finite_coordinates_rejected(adapter, tmp_path):
    """Coordinates with NaN or Infinity are quarantined with NON_FINITE_COORDINATE."""
    raw_json = json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"code": "NAN_C", "name": "NaN Coord"},
                "geometry": {"type": "Point", "coordinates": [float("nan"), 27.25]},
            },
            {
                "type": "Feature",
                "properties": {"code": "INF_C", "name": "Inf Coord"},
                "geometry": {"type": "Point", "coordinates": [75.45, float("inf")]},
            },
        ],
    })
    file_path = tmp_path / "nan_inf.json"
    file_path.write_text(raw_json, encoding="utf-8")
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 2
    assert all("NON_FINITE_COORDINATE" in q.rejection_codes for q in result.quarantined)


def test_out_of_bounds_coordinates_quarantined(adapter, tmp_path):
    """Coordinates out of global bounds [-90, 90] and [-180, 180] are quarantined."""
    feature_lat = {
        "type": "Feature",
        "properties": {"code": "OOB_LAT", "name": "OOB Lat"},
        "geometry": {"type": "Point", "coordinates": [75.45, 95.0]},
    }
    feature_lon = {
        "type": "Feature",
        "properties": {"code": "OOB_LON", "name": "OOB Lon"},
        "geometry": {"type": "Point", "coordinates": [190.0, 27.25]},
    }
    file_path = _write_geojson(tmp_path, [feature_lat, feature_lon])
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert "OUT_OF_BOUNDS_LATITUDE" in result.quarantined[0].rejection_codes
    assert "OUT_OF_BOUNDS_LONGITUDE" in result.quarantined[1].rejection_codes


def test_dummy_zero_coordinates_quarantined(adapter, tmp_path):
    """Null Island (0.0, 0.0) coordinates are quarantined with DUMMY_ZERO_COORDINATES."""
    feature = {
        "type": "Feature",
        "properties": {"code": "ZERO_C", "name": "Null Island Station"},
        "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
    }
    file_path = _write_geojson(tmp_path, [feature])
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert "DUMMY_ZERO_COORDINATES" in result.quarantined[0].rejection_codes


# =====================================================================
# C. QUARANTINE: MISSING ATTRIBUTES AND DUPLICATES
# =====================================================================

def test_missing_station_code_quarantined(adapter, tmp_path):
    """Missing, null, or empty station codes are quarantined with MISSING_STATION_CODE."""
    features = [
        {"type": "Feature", "properties": {"code": None, "name": "No Code"}, "geometry": {"type": "Point", "coordinates": [75.0, 27.0]}},
        {"type": "Feature", "properties": {"code": "", "name": "Empty Code"}, "geometry": {"type": "Point", "coordinates": [75.0, 27.0]}},
        {"type": "Feature", "properties": {"code": "   ", "name": "Whitespace Code"}, "geometry": {"type": "Point", "coordinates": [75.0, 27.0]}},
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 3
    assert all("MISSING_STATION_CODE" in q.rejection_codes for q in result.quarantined)


def test_missing_station_name_quarantined(adapter, tmp_path):
    """Missing, null, or empty station names are quarantined with MISSING_STATION_NAME."""
    features = [
        {"type": "Feature", "properties": {"code": "STN1", "name": None}, "geometry": {"type": "Point", "coordinates": [75.0, 27.0]}},
        {"type": "Feature", "properties": {"code": "STN2", "name": ""}, "geometry": {"type": "Point", "coordinates": [75.0, 27.0]}},
        {"type": "Feature", "properties": {"code": "STN3", "name": "   "}, "geometry": {"type": "Point", "coordinates": [75.0, 27.0]}},
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 3
    assert all("MISSING_STATION_NAME" in q.rejection_codes for q in result.quarantined)


def test_collective_duplicate_quarantine(adapter, tmp_path):
    """
    Business Rule: When a station code is duplicated, ALL instances belonging to that
    duplicate-code group are quarantined. None are accepted.
    """
    features = [
        {"type": "Feature", "properties": {"code": "GWL", "name": "Gwalior Jn A"}, "geometry": {"type": "Point", "coordinates": [78.18, 26.21]}},
        {"type": "Feature", "properties": {"code": "GWL", "name": "Gwalior Jn B"}, "geometry": {"type": "Point", "coordinates": [78.19, 26.22]}},
        {"type": "Feature", "properties": {"code": "NDLS", "name": "New Delhi"}, "geometry": {"type": "Point", "coordinates": [77.22, 28.64]}},
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    # NDLS accepted; both GWL records quarantined
    assert len(result.records) == 1
    assert result.records[0].code == "NDLS"

    assert len(result.quarantined) == 2
    assert all("DUPLICATE_STATION_CODE" in q.rejection_codes for q in result.quarantined)
    assert all(q.original_station_code == "GWL" for q in result.quarantined)
    assert result.provenance.rejection_reason_counts["DUPLICATE_STATION_CODE"] == 2


# =====================================================================
# D. ENCODING, SYNTAX, AND REPRODUCIBILITY TESTS
# =====================================================================

def test_nonexistent_file_raises_not_found(adapter):
    """Passing a nonexistent path raises SourceFileNotFoundError."""
    with pytest.raises(SourceFileNotFoundError):
        adapter.adapt("nonexistent_path_to_stations.json")


def test_malformed_json_raises_clean_error(adapter, tmp_path):
    """Corrupted JSON raises MalformedSourceError with diagnostic line and col."""
    bad_file = tmp_path / "corrupt.json"
    bad_file.write_text("{ unquoted_key: 123 ", encoding="utf-8")

    with pytest.raises(MalformedSourceError) as exc_info:
        adapter.adapt(bad_file)
    assert "Malformed JSON" in str(exc_info.value)


def test_utf8_decoding_enforced(adapter, tmp_path):
    """Non-UTF-8 binary bytes raise SourceEncodingError."""
    bad_encoding_file = tmp_path / "bad_encoding.json"
    bad_encoding_file.write_bytes(b"\xff\xfe\x00\x00\x12\x34")

    with pytest.raises(SourceEncodingError):
        adapter.adapt(bad_encoding_file)


def test_provenance_and_checksum_verification(adapter, tmp_path):
    """Verifies that SourceProvenance captures exact file size, SHA-256, and metadata."""
    features = [
        {"type": "Feature", "properties": {"code": "TEST", "name": "Test Stn"}, "geometry": {"type": "Point", "coordinates": [75.0, 25.0]}},
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    prov = result.provenance
    assert prov.source_repository_url == "https://github.com/datameet/railways"
    assert prov.source_license == "CC0 1.0 Universal"
    assert "CC0" in prov.source_license
    assert "README" in prov.license_evidence
    assert prov.file_size_bytes == file_path.stat().st_size
    assert len(prov.file_sha256) == 64
    assert prov.total_source_records == 1
    assert prov.accepted_records_count == 1
    assert prov.quarantined_records_count == 0


def test_deterministic_parsing_output(adapter, tmp_path):
    """Running adapt on the identical file multiple times yields identical outputs."""
    features = [
        {"type": "Feature", "properties": {"code": "A", "name": "Station A"}, "geometry": {"type": "Point", "coordinates": [75.0, 25.0]}},
        {"type": "Feature", "properties": {"code": "B", "name": "Station B"}, "geometry": None},
    ]
    file_path = _write_geojson(tmp_path, features)

    res1 = adapter.adapt(file_path)
    res2 = adapter.adapt(file_path)

    assert len(res1.records) == len(res2.records)
    assert len(res1.accepted) == len(res2.accepted)
    assert len(res1.quarantined) == len(res2.quarantined)
    assert res1.provenance.file_sha256 == res2.provenance.file_sha256
    assert res1.records[0].code == res2.records[0].code


# =====================================================================
# E. FOCUSED NEGATIVE AND AUDIT TESTS (CTO REVIEW FIX 3)
# =====================================================================

def test_feature_element_not_a_dictionary(adapter, tmp_path):
    """CTO Item 1: Feature element that is not a JSON dict is quarantined with MALFORMED_FEATURE_OBJECT."""
    features = [
        12345,
        "not_a_dictionary_feature",
        {"type": "Feature", "properties": {"code": "OK1", "name": "Valid Station"}, "geometry": {"type": "Point", "coordinates": [75.0, 27.0]}},
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 1
    assert result.records[0].code == "OK1"
    assert len(result.quarantined) == 2

    q0 = result.quarantined[0]
    assert q0.source_record_index == 0
    assert q0.rejection_codes == ("MALFORMED_FEATURE_OBJECT",)
    assert q0.raw_payload == {"raw": 12345}

    q1 = result.quarantined[1]
    assert q1.source_record_index == 1
    assert q1.rejection_codes == ("MALFORMED_FEATURE_OBJECT",)
    assert q1.raw_payload == {"raw": "not_a_dictionary_feature"}


def test_feature_type_not_feature(adapter, tmp_path):
    """CTO Item 2: Feature with 'type' other than 'Feature' is quarantined with NOT_FEATURE_TYPE."""
    features = [
        {
            "type": "Station",
            "properties": {"code": "STN_BAD_TYPE", "name": "Bad Type Station"},
            "geometry": {"type": "Point", "coordinates": [75.0, 27.0]},
        }
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 1
    q = result.quarantined[0]
    assert "NOT_FEATURE_TYPE" in q.rejection_codes
    assert "Element type must be 'Feature'" in q.validation_messages[0]


def test_properties_missing(adapter, tmp_path):
    """CTO Item 3: Feature missing the 'properties' attribute entirely is quarantined with MISSING_PROPERTIES."""
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [75.0, 27.0]},
        }
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 1
    q = result.quarantined[0]
    assert "MISSING_PROPERTIES" in q.rejection_codes


def test_properties_not_a_dictionary(adapter, tmp_path):
    """CTO Item 4: Feature where 'properties' is not a dict is quarantined with MALFORMED_PROPERTIES_OBJECT."""
    features = [
        {
            "type": "Feature",
            "properties": "string_properties",
            "geometry": {"type": "Point", "coordinates": [75.0, 27.0]},
        },
        {
            "type": "Feature",
            "properties": 42,
            "geometry": {"type": "Point", "coordinates": [75.0, 27.0]},
        },
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 2
    assert all("MALFORMED_PROPERTIES_OBJECT" in q.rejection_codes for q in result.quarantined)


def test_geometry_missing(adapter, tmp_path):
    """Feature missing the 'geometry' attribute entirely is quarantined with MISSING_GEOMETRY."""
    features = [
        {
            "type": "Feature",
            "properties": {"code": "NO_GEO", "name": "No Geometry Key"},
        }
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 1
    assert "MISSING_GEOMETRY" in result.quarantined[0].rejection_codes


def test_geometry_not_a_dictionary(adapter, tmp_path):
    """CTO Item 5: Feature where 'geometry' is not a dict is quarantined with MALFORMED_GEOMETRY_OBJECT."""
    features = [
        {
            "type": "Feature",
            "properties": {"code": "STR_GEO", "name": "String Geometry"},
            "geometry": "POINT(75.0 27.0)",
        },
        {
            "type": "Feature",
            "properties": {"code": "LST_GEO", "name": "List Geometry"},
            "geometry": [75.0, 27.0],
        },
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 2
    assert all("MALFORMED_GEOMETRY_OBJECT" in q.rejection_codes for q in result.quarantined)


def test_geometry_type_missing(adapter, tmp_path):
    """CTO Item 6: Feature where 'geometry' is missing 'type' attribute is quarantined with MISSING_GEOMETRY_TYPE."""
    features = [
        {
            "type": "Feature",
            "properties": {"code": "NO_GTYPE", "name": "No Geo Type"},
            "geometry": {"coordinates": [75.0, 27.0]},
        },
        {
            "type": "Feature",
            "properties": {"code": "NONE_GTYPE", "name": "None Geo Type"},
            "geometry": {"type": None, "coordinates": [75.0, 27.0]},
        },
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 2
    assert all("MISSING_GEOMETRY_TYPE" in q.rejection_codes for q in result.quarantined)


def test_duplicate_code_combined_with_another_validation_failure(adapter, tmp_path):
    """
    CTO Item 7: When a duplicated station code feature also suffers from another validation failure
    (e.g., null geometry), both failure reasons are accurately recorded on the quarantined record.
    """
    features = [
        {
            "type": "Feature",
            "properties": {"code": "DUP_COMBO", "name": "Station A (Valid Coords)"},
            "geometry": {"type": "Point", "coordinates": [78.18, 26.21]},
        },
        {
            "type": "Feature",
            "properties": {"code": "DUP_COMBO", "name": "Station B (Null Geo)"},
            "geometry": None,
        },
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 0
    assert len(result.quarantined) == 2

    # Feature 0: Valid geometry, quarantined solely due to duplicate code
    q0 = result.quarantined[0]
    assert q0.source_record_index == 0
    assert q0.original_station_code == "DUP_COMBO"
    assert q0.rejection_codes == ("DUPLICATE_STATION_CODE",)

    # Feature 1: Has both duplicate code AND null geometry
    q1 = result.quarantined[1]
    assert q1.source_record_index == 1
    assert q1.original_station_code == "DUP_COMBO"
    assert "DUPLICATE_STATION_CODE" in q1.rejection_codes
    assert "NULL_GEOMETRY" in q1.rejection_codes
    assert set(q1.rejection_codes) == {"DUPLICATE_STATION_CODE", "NULL_GEOMETRY"}


def test_three_or_more_duplicate_code_occurrences(adapter, tmp_path):
    """
    CTO Item 8: Collective quarantine must scale to 3 or more occurrences of the same code,
    quarantining all instances and accurately reporting the collision count.
    """
    features = [
        {"type": "Feature", "properties": {"code": "TRIP", "name": "Triplicate A"}, "geometry": {"type": "Point", "coordinates": [75.1, 25.1]}},
        {"type": "Feature", "properties": {"code": "TRIP", "name": "Triplicate B"}, "geometry": {"type": "Point", "coordinates": [75.2, 25.2]}},
        {"type": "Feature", "properties": {"code": "TRIP", "name": "Triplicate C"}, "geometry": {"type": "Point", "coordinates": [75.3, 25.3]}},
        {"type": "Feature", "properties": {"code": "SOLO", "name": "Unique Station"}, "geometry": {"type": "Point", "coordinates": [77.0, 28.0]}},
    ]
    file_path = _write_geojson(tmp_path, features)
    result = adapter.adapt(file_path)

    assert len(result.records) == 1
    assert result.records[0].code == "SOLO"

    assert len(result.quarantined) == 3
    for q in result.quarantined:
        assert q.original_station_code == "TRIP"
        assert "DUPLICATE_STATION_CODE" in q.rejection_codes
        assert "duplicated across 3 features" in q.validation_messages[0]

    assert result.provenance.rejection_reason_counts["DUPLICATE_STATION_CODE"] == 3


def test_source_file_io_failure_handling(adapter, tmp_path):
    """
    CTO Item 9: Source file I/O failure handling:
    - Passing a directory path raises SourceIOError.
    - An unreadable file (simulated OS error) raises SourceIOError.
    """
    # Passing a directory instead of a regular file
    with pytest.raises(SourceIOError) as exc_info:
        adapter.adapt(tmp_path)
    assert "not a regular file" in str(exc_info.value)

    # Simulating unreadable file via monkeypatch
    dummy_file = tmp_path / "locked.json"
    dummy_file.write_text("{}", encoding="utf-8")

    def _mock_read_bytes(self):
        raise OSError("Permission denied: simulated I/O failure")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(Path, "read_bytes", _mock_read_bytes)
        with pytest.raises(SourceIOError) as exc_info2:
            adapter.adapt(dummy_file)
        assert "I/O error reading source file" in str(exc_info2.value)


def test_accepted_raw_source_payload_preservation_and_immutability(adapter, tmp_path):
    """
    CTO Items 10 & Immutability:
    - Extra source properties survive in result.accepted[i].raw_payload.
    - Unambiguous mapping between accepted Station domain entity and raw payload.
    - All structures (AdapterResult, AcceptedRecord, QuarantineRecord, SourceProvenance)
      are strictly immutable and reject mutation attempts.
    """
    feature = {
        "type": "Feature",
        "properties": {
            "code": "NDLS",
            "name": "New Delhi",
            "address": "Paharganj, New Delhi, Delhi 110055",
            "state": "Delhi",
            "zone": "NR",
            "division": "DLI",
            "platforms": 16,
            "metadata": {
                "tags": ["major_junction", "capital_terminal"],
                "elevation_m": 214,
            },
        },
        "geometry": {
            "type": "Point",
            "coordinates": [77.22, 28.64],
        },
    }
    file_path = _write_geojson(tmp_path, [feature])
    result = adapter.adapt(file_path)

    # 1. Structure Verification
    assert len(result.records) == 1
    assert len(result.accepted) == 1
    assert len(result.quarantined) == 0

    domain_stn = result.records[0]
    audit_rec = result.accepted[0]

    # 2. Unambiguous 1-to-1 Mapping
    assert audit_rec.station is domain_stn
    assert audit_rec.source_record_index == 0
    assert audit_rec.original_station_code == "NDLS"

    # 3. Payload Preservation
    props = audit_rec.raw_payload["properties"]
    assert props["code"] == "NDLS"
    assert props["name"] == "New Delhi"
    assert props["address"] == "Paharganj, New Delhi, Delhi 110055"
    assert props["division"] == "DLI"
    assert props["platforms"] == 16
    assert props["metadata"]["tags"] == ("major_junction", "capital_terminal")
    assert props["metadata"]["elevation_m"] == 214

    # 4. Strict Immutability Verification: AdapterResult
    with pytest.raises(FrozenInstanceError):
        result.records = ()  # Cannot reassign attribute of frozen dataclass

    with pytest.raises(TypeError):
        result.records[0] = None  # Tuple does not support item assignment

    with pytest.raises(FrozenInstanceError):
        result.accepted = ()

    with pytest.raises(TypeError):
        result.accepted[0] = None

    # 5. Strict Immutability Verification: AcceptedRecord & raw_payload
    with pytest.raises(FrozenInstanceError):
        audit_rec.source_record_index = 99

    with pytest.raises(TypeError):
        audit_rec.raw_payload["properties"]["address"] = "MUTATED"

    with pytest.raises(TypeError):
        audit_rec.raw_payload["properties"]["metadata"]["tags"] = "MUTATED"

    # 6. Strict Immutability Verification: SourceProvenance counts
    with pytest.raises(FrozenInstanceError):
        result.provenance.accepted_records_count = 0

    with pytest.raises(TypeError):
        result.provenance.rejection_reason_counts["NEW_REASON"] = 1


# =====================================================================
# F. FULL DATAMEET DATASET RECONCILIATION AUDIT
# =====================================================================

def test_full_datameet_dataset_reconciliation(adapter):
    """
    Executes against the Local DataMeet baseline snapshot stations.json dataset and asserts
    exact baseline reconciliation:
    - 8,990 total features
    - 8,697 accepted records (1-to-1 mapped in result.records and result.accepted)
    - 293 unique quarantined records
    - 294 total validation failure occurrences (293 NULL_GEOMETRY, 1 MISSING_STATION_NAME)
    - Feature index 3235 accounts for both failures
    - No duplicate accepted codes
    - All accepted records deserialize into Station domain model
    - All accepted records preserve original source payloads
    """
    assert DATAMEET_STATIONS_PATH.is_file(), f"DataMeet stations.json not found at {DATAMEET_STATIONS_PATH}"

    result = adapter.adapt(DATAMEET_STATIONS_PATH)
    prov = result.provenance

    # Exact Counts Reconciliation
    assert prov.total_source_records == 8990
    assert prov.accepted_records_count == 8697
    assert prov.quarantined_records_count == 293

    assert len(result.records) == 8697
    assert len(result.accepted) == 8697
    assert len(result.quarantined) == 293

    # Exact Disjoint / Overlapping Rejection Reasons
    assert prov.rejection_reason_counts == {"NULL_GEOMETRY": 293, "MISSING_STATION_NAME": 1}
    assert sum(prov.rejection_reason_counts.values()) == 294

    # File Integrity Verification
    assert prov.file_size_bytes == 1864683
    assert prov.file_sha256 == "9bd5e1da3a859e5359a95f40b6009aa468efb177da4faac57ffdcd7daeb4df18"

    # Multi-failure Record Audit (Feature index 3235: code 'P', name '', geo None)
    overlap_records = [q for q in result.quarantined if len(q.rejection_codes) > 1]
    assert len(overlap_records) == 1
    assert overlap_records[0].source_record_index == 3235
    assert set(overlap_records[0].rejection_codes) == {"NULL_GEOMETRY", "MISSING_STATION_NAME"}

    # Accepted Records Quality & Referential Uniqueness
    accepted_codes = [s.code for s in result.records]
    assert len(accepted_codes) == len(set(accepted_codes)), "Accepted station codes contain duplicates"
    assert len(accepted_codes) == 8697

    # Geographic Bounds on all accepted records
    for stn in result.records:
        assert -90.0 <= stn.latitude <= 90.0
        assert -180.0 <= stn.longitude <= 180.0
        assert not (stn.latitude == 0.0 and stn.longitude == 0.0)

    # Sample audit verification: check first accepted record has preserved raw payload
    first_accepted = result.accepted[0]
    assert first_accepted.station is result.records[0]
    assert first_accepted.original_station_code == result.records[0].code
    assert "properties" in first_accepted.raw_payload
    assert "geometry" in first_accepted.raw_payload


# =====================================================================
# G. DIRECT MODEL CONSTRUCTION IMMUTABILITY ENFORCEMENT
# =====================================================================

def test_directly_constructed_accepted_record_freezes_mutable_nested_payload():
    """CTO Requirement: Directly constructed AcceptedRecord freezes mutable nested mappings and lists."""
    from types import MappingProxyType

    mutable_payload = {
        "properties": {
            "code": "TEST",
            "name": "Test Station",
            "lines": ["Line 1", "Line 2", {"nested_key": ["sub_val1", "sub_val2"]}],
            "details": {"platforms": 4, "state": "MH"},
        }
    }
    stn = Station(code="TEST", name="Test Station", latitude=19.0, longitude=72.8)
    record = AcceptedRecord(
        station=stn,
        source_record_index=0,
        original_station_code="TEST",
        raw_payload=mutable_payload,
    )

    # Payload internal collections are converted to immutable MappingProxyType and tuples
    assert isinstance(record.raw_payload, MappingProxyType)
    assert isinstance(record.raw_payload["properties"], MappingProxyType)
    assert isinstance(record.raw_payload["properties"]["lines"], tuple)
    assert isinstance(record.raw_payload["properties"]["lines"][2], MappingProxyType)
    assert isinstance(record.raw_payload["properties"]["lines"][2]["nested_key"], tuple)

    # Mutating original dictionary externally has zero effect on the record
    mutable_payload["properties"]["code"] = "MUTATED"
    mutable_payload["properties"]["lines"].append("Line 3")
    mutable_payload["properties"]["details"]["platforms"] = 99
    assert record.raw_payload["properties"]["code"] == "TEST"
    assert len(record.raw_payload["properties"]["lines"]) == 3
    assert record.raw_payload["properties"]["details"]["platforms"] == 4

    # Direct mutation attempts fail
    with pytest.raises(TypeError):
        record.raw_payload["properties"]["code"] = "MOD"
    with pytest.raises(TypeError):
        record.raw_payload["properties"]["details"]["platforms"] = 10
    with pytest.raises(AttributeError):
        record.raw_payload["properties"]["lines"].append("FAIL")


def test_directly_constructed_quarantine_record_freezes_payload_and_converts_lists_to_tuples():
    """CTO Requirement: Directly constructed QuarantineRecord converts lists to tuples and freezes payload."""
    from types import MappingProxyType

    mutable_codes = ["NULL_GEOMETRY", "MISSING_STATION_NAME"]
    mutable_messages = ["Message 1", "Message 2"]
    mutable_payload = {"raw": {"code": "X", "tags": [1, 2]}}

    q = QuarantineRecord(
        source_file="test.json",
        source_record_index=42,
        original_station_code="X",
        original_station_name=None,
        rejection_codes=mutable_codes,
        validation_messages=mutable_messages,
        raw_payload=mutable_payload,
    )

    assert isinstance(q.rejection_codes, tuple)
    assert q.rejection_codes == ("NULL_GEOMETRY", "MISSING_STATION_NAME")
    assert isinstance(q.validation_messages, tuple)
    assert q.validation_messages == ("Message 1", "Message 2")
    assert isinstance(q.raw_payload, MappingProxyType)
    assert isinstance(q.raw_payload["raw"]["tags"], tuple)

    # External mutations have zero effect
    mutable_codes.append("ANOTHER_CODE")
    mutable_messages.append("Another msg")
    mutable_payload["raw"]["code"] = "MOD"
    assert q.rejection_codes == ("NULL_GEOMETRY", "MISSING_STATION_NAME")
    assert q.validation_messages == ("Message 1", "Message 2")
    assert q.raw_payload["raw"]["code"] == "X"

    # Direct mutation attempts fail
    with pytest.raises(AttributeError):
        q.rejection_codes.append("FAIL")
    with pytest.raises(TypeError):
        q.raw_payload["raw"]["code"] = "FAIL"


def test_directly_constructed_source_provenance_freezes_dictionary_counts():
    """CTO Requirement: Directly constructed SourceProvenance freezes a normal dictionary passed as counts."""
    from types import MappingProxyType

    counts = {"NULL_GEOMETRY": 293, "MISSING_STATION_NAME": 1}
    prov = SourceProvenance(rejection_reason_counts=counts)

    assert isinstance(prov.rejection_reason_counts, MappingProxyType)
    assert prov.rejection_reason_counts == {"NULL_GEOMETRY": 293, "MISSING_STATION_NAME": 1}

    # External mutations have zero effect
    counts["NULL_GEOMETRY"] = 999
    counts["NEW_REASON"] = 5
    assert prov.rejection_reason_counts["NULL_GEOMETRY"] == 293
    assert "NEW_REASON" not in prov.rejection_reason_counts

    # Direct mutation attempts fail
    with pytest.raises(TypeError):
        prov.rejection_reason_counts["NULL_GEOMETRY"] = 100
    with pytest.raises(TypeError):
        prov.rejection_reason_counts["EXTRA"] = 1


def test_directly_constructed_adapter_result_converts_mutable_collections_to_tuples():
    """CTO Requirement: Directly constructed AdapterResult converts mutable collections to tuples."""
    stn = Station(code="BDHL", name="Badhal", latitude=27.25, longitude=75.45)
    acc = AcceptedRecord(station=stn, source_record_index=0, original_station_code="BDHL", raw_payload={})
    q = QuarantineRecord(
        source_file="f.json",
        source_record_index=1,
        original_station_code=None,
        original_station_name=None,
        rejection_codes=("ERR",),
        validation_messages=("Msg",),
        raw_payload={},
    )
    prov = SourceProvenance()

    mutable_records = [stn]
    mutable_accepted = [acc]
    mutable_quarantined = [q]

    result = AdapterResult(
        records=mutable_records,
        accepted=mutable_accepted,
        quarantined=mutable_quarantined,
        provenance=prov,
    )

    assert isinstance(result.records, tuple)
    assert isinstance(result.accepted, tuple)
    assert isinstance(result.quarantined, tuple)

    # External mutations have zero effect
    stn2 = Station(code="NDLS", name="New Delhi", latitude=28.64, longitude=77.22)
    mutable_records.append(stn2)
    mutable_accepted.clear()
    mutable_quarantined.pop()

    assert len(result.records) == 1
    assert result.records[0].code == "BDHL"
    assert len(result.accepted) == 1
    assert len(result.quarantined) == 1


def test_general_mapping_freezing_in_models():
    """CTO Requirement: freeze_payload handles general mappings safely, not only ordinary dicts."""
    from collections import UserDict
    from types import MappingProxyType

    custom_map = UserDict({"key1": "val1", "sub": UserDict({"nested": [1, 2, 3]})})
    stn = Station(code="MAP", name="Mapping Station", latitude=10.0, longitude=76.0)
    rec = AcceptedRecord(station=stn, source_record_index=0, original_station_code="MAP", raw_payload=custom_map)

    assert isinstance(rec.raw_payload, MappingProxyType)
    assert rec.raw_payload["key1"] == "val1"
    assert isinstance(rec.raw_payload["sub"], MappingProxyType)
    assert rec.raw_payload["sub"]["nested"] == (1, 2, 3)

    with pytest.raises(TypeError):
        rec.raw_payload["key1"] = "MUTATED"


def test_collections_deque_normalization_in_adapter_result():
    """CTO Requirement: collections.deque inputs to AdapterResult are normalized to tuples."""
    from collections import deque

    stn1 = Station(code="BDHL", name="Badhal", latitude=27.25, longitude=75.45)
    stn2 = Station(code="NDLS", name="New Delhi", latitude=28.64, longitude=77.22)
    acc = AcceptedRecord(station=stn1, source_record_index=0, original_station_code="BDHL", raw_payload={})
    q = QuarantineRecord(
        source_file="f.json",
        source_record_index=1,
        original_station_code=None,
        original_station_name=None,
        rejection_codes=("ERR",),
        validation_messages=("Msg",),
        raw_payload={},
    )
    prov = SourceProvenance()

    result = AdapterResult(
        records=deque([stn1, stn2]),
        accepted=deque([acc]),
        quarantined=deque([q]),
        provenance=prov,
    )

    assert isinstance(result.records, tuple)
    assert len(result.records) == 2
    assert result.records[0] is stn1
    assert result.records[1] is stn2

    assert isinstance(result.accepted, tuple)
    assert len(result.accepted) == 1
    assert result.accepted[0] is acc

    assert isinstance(result.quarantined, tuple)
    assert len(result.quarantined) == 1
    assert result.quarantined[0] is q


def test_collections_deque_normalization_in_quarantine_record():
    """CTO Requirement: collections.deque inputs to QuarantineRecord are normalized to tuples."""
    from collections import deque

    codes_deque = deque(["NULL_GEOMETRY", "MISSING_STATION_NAME"])
    messages_deque = deque(["Geometry is null", "Station name is missing"])

    q = QuarantineRecord(
        source_file="test.json",
        source_record_index=10,
        original_station_code="X",
        original_station_name=None,
        rejection_codes=codes_deque,
        validation_messages=messages_deque,
        raw_payload={},
    )

    assert isinstance(q.rejection_codes, tuple)
    assert q.rejection_codes == ("NULL_GEOMETRY", "MISSING_STATION_NAME")

    assert isinstance(q.validation_messages, tuple)
    assert q.validation_messages == ("Geometry is null", "Station name is missing")


def test_invalid_mapping_and_scalar_inputs_rejected_with_type_error():
    """CTO Requirement: Strings, bytes, mappings, and scalars raise clear TypeError when passed as collections."""
    stn = Station(code="TEST", name="Test Station", latitude=19.0, longitude=72.8)
    acc = AcceptedRecord(station=stn, source_record_index=0, original_station_code="TEST", raw_payload={})
    q = QuarantineRecord(
        source_file="f.json",
        source_record_index=0,
        original_station_code=None,
        original_station_name=None,
        rejection_codes=("ERR",),
        validation_messages=("Msg",),
        raw_payload={},
    )
    prov = SourceProvenance()

    # QuarantineRecord: string rejection_codes
    with pytest.raises(TypeError) as exc:
        QuarantineRecord(
            source_file="f.json",
            source_record_index=0,
            original_station_code=None,
            original_station_name=None,
            rejection_codes="NULL_GEOMETRY",
            validation_messages=("Msg",),
            raw_payload={},
        )
    assert "rejection_codes" in str(exc.value)

    # QuarantineRecord: bytes rejection_codes
    with pytest.raises(TypeError) as exc:
        QuarantineRecord(
            source_file="f.json",
            source_record_index=0,
            original_station_code=None,
            original_station_name=None,
            rejection_codes=b"NULL_GEOMETRY",
            validation_messages=("Msg",),
            raw_payload={},
        )
    assert "rejection_codes" in str(exc.value)

    # QuarantineRecord: mapping rejection_codes
    with pytest.raises(TypeError) as exc:
        QuarantineRecord(
            source_file="f.json",
            source_record_index=0,
            original_station_code=None,
            original_station_name=None,
            rejection_codes={"error": "NULL_GEOMETRY"},
            validation_messages=("Msg",),
            raw_payload={},
        )
    assert "mapping" in str(exc.value)

    # QuarantineRecord: scalar int rejection_codes
    with pytest.raises(TypeError) as exc:
        QuarantineRecord(
            source_file="f.json",
            source_record_index=0,
            original_station_code=None,
            original_station_name=None,
            rejection_codes=12345,
            validation_messages=("Msg",),
            raw_payload={},
        )
    assert "scalar" in str(exc.value)

    # QuarantineRecord: string validation_messages
    with pytest.raises(TypeError) as exc:
        QuarantineRecord(
            source_file="f.json",
            source_record_index=0,
            original_station_code=None,
            original_station_name=None,
            rejection_codes=("ERR",),
            validation_messages="Single string message",
            raw_payload={},
        )
    assert "validation_messages" in str(exc.value)

    # AdapterResult: scalar Station as records
    with pytest.raises(TypeError) as exc:
        AdapterResult(
            records=stn,
            accepted=(acc,),
            quarantined=(q,),
            provenance=prov,
        )
    assert "records" in str(exc.value)

    # AdapterResult: string as records
    with pytest.raises(TypeError) as exc:
        AdapterResult(
            records="NDLS",
            accepted=(acc,),
            quarantined=(q,),
            provenance=prov,
        )
    assert "records" in str(exc.value)

    # AdapterResult: mapping as records
    with pytest.raises(TypeError) as exc:
        AdapterResult(
            records={"stn": stn},
            accepted=(acc,),
            quarantined=(q,),
            provenance=prov,
        )
    assert "mapping" in str(exc.value)

    # AdapterResult: scalar AcceptedRecord as accepted
    with pytest.raises(TypeError) as exc:
        AdapterResult(
            records=(stn,),
            accepted=acc,
            quarantined=(q,),
            provenance=prov,
        )
    assert "accepted" in str(exc.value)

    # AdapterResult: scalar QuarantineRecord as quarantined
    with pytest.raises(TypeError) as exc:
        AdapterResult(
            records=(stn,),
            accepted=(acc,),
            quarantined=q,
            provenance=prov,
        )
    assert "quarantined" in str(exc.value)


