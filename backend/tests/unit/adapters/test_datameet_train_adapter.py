import json
import datetime
from collections import deque
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType
import pytest

from app.infrastructure.adapters.datameet.station_adapter import DataMeetStationAdapter
from app.infrastructure.adapters.datameet.train_adapter import DataMeetTrainAdapter
from app.infrastructure.adapters.datameet.train_models import (
    DataMeetTrainRecord,
    AcceptedTrainRecord,
    TrainQuarantineRecord,
    TrainAdapterResult,
)
from app.infrastructure.adapters.datameet.models import SourceProvenance
from app.infrastructure.adapters.exceptions import (
    SourceFileNotFoundError,
    SourceIOError,
    SourceEncodingError,
    MalformedSourceError,
)

STATIONS_DATA_PATH = Path("app/infrastructure/data/sources/datameet/stations.json")
TRAINS_DATA_PATH = Path("app/infrastructure/data/sources/datameet/trains.json")


def _make_feature(
    number: str = "12951",
    name: str = "Mumbai Rajdhani Express",
    from_code: str = "MMCT",
    to_code: str = "NDLS",
    from_name: str = "Mumbai Central",
    to_name: str = "New Delhi",
    train_type: str = "Rajdhani",
    zone: str = "WR",
    departure: str = "16:35:00",
    arrival: str = "08:35:00",
    duration_h: int = 16,
    duration_m: int = 0,
    distance: int = 1384,
    sleeper: int = 0,
    third_ac: int = 1,
    second_ac: int = 1,
    first_ac: int = 1,
    coords: list = None,
) -> dict:
    if coords is None:
        coords = [[72.8194, 18.9696], [77.2218, 28.6143]]
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
        "properties": {
            "number": number,
            "name": name,
            "from_station_code": from_code,
            "to_station_code": to_code,
            "from_station_name": from_name,
            "to_station_name": to_name,
            "type": train_type,
            "zone": zone,
            "departure": departure,
            "arrival": arrival,
            "duration_h": duration_h,
            "duration_m": duration_m,
            "distance": distance,
            "return_train": "12952",
            "sleeper": sleeper,
            "third_ac": third_ac,
            "second_ac": second_ac,
            "first_ac": first_ac,
            "first_class": 0,
            "chair_car": 0,
            "classes": "1A,2A,3A",
        },
    }


def _make_geojson(features: list) -> dict:
    return {
        "type": "FeatureCollection",
        "features": features,
    }


class TestDataMeetTrainAdapterFileHandling:
    """Verifies file I/O, encoding, and schema parsing error handling."""

    def test_missing_file_raises_source_file_not_found(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        missing = tmp_path / "non_existent_trains.json"
        with pytest.raises(SourceFileNotFoundError) as exc_info:
            adapter.adapt(missing)
        assert "not found" in str(exc_info.value).lower()

    def test_directory_path_raises_source_io_error(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        with pytest.raises(SourceIOError) as exc_info:
            adapter.adapt(tmp_path)
        assert "not a regular file" in str(exc_info.value).lower()

    def test_invalid_utf8_encoding_raises_source_encoding_error(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        bad_file = tmp_path / "invalid_encoding.json"
        bad_file.write_bytes(b'{"type": "FeatureCollection", \xff\xfe invalid}')
        with pytest.raises(SourceEncodingError) as exc_info:
            adapter.adapt(bad_file)
        assert "utf-8" in str(exc_info.value).lower()

    def test_corrupted_json_syntax_raises_malformed_source_error(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        corrupt = tmp_path / "syntax_error.json"
        corrupt.write_text('{"type": "FeatureCollection", features: [}', encoding="utf-8")
        with pytest.raises(MalformedSourceError) as exc_info:
            adapter.adapt(corrupt)
        assert "malformed json" in str(exc_info.value).lower()

    def test_non_dictionary_root_raises_malformed_source_error(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        bad_root = tmp_path / "array_root.json"
        bad_root.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(MalformedSourceError) as exc_info:
            adapter.adapt(bad_root)
        assert "must be a json object" in str(exc_info.value).lower()

    def test_non_feature_collection_root_raises_malformed_source_error(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        wrong_type = tmp_path / "wrong_type.json"
        wrong_type.write_text('{"type": "Point", "features": []}', encoding="utf-8")
        with pytest.raises(MalformedSourceError) as exc_info:
            adapter.adapt(wrong_type)
        assert "featurecollection" in str(exc_info.value).lower()

    def test_features_attribute_not_list_raises_malformed_source_error(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        bad_features = tmp_path / "features_dict.json"
        bad_features.write_text('{"type": "FeatureCollection", "features": "invalid"}', encoding="utf-8")
        with pytest.raises(MalformedSourceError) as exc_info:
            adapter.adapt(bad_features)
        assert "must be a list" in str(exc_info.value).lower()


class TestDataMeetTrainAdapterFeatureParsing:
    """Verifies feature extraction, string preservation, and positive parsing."""

    def test_valid_train_feature_parsed_correctly(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature()
        file_path = tmp_path / "train.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)

        assert len(result.records) == 1
        assert len(result.accepted) == 1
        assert len(result.quarantined) == 0

        train = result.records[0]
        assert train.number == "12951"
        assert train.name == "Mumbai Rajdhani Express"
        assert train.origin_code == "MMCT"
        assert train.destination_code == "NDLS"
        assert train.origin_name == "Mumbai Central"
        assert train.destination_name == "New Delhi"
        assert train.train_type == "Rajdhani"
        assert train.zone == "WR"
        assert train.departure_time == datetime.time(16, 35, 0)
        assert train.arrival_time == datetime.time(8, 35, 0)
        assert train.duration_hours == 16
        assert train.duration_minutes == 0
        assert train.distance_km == 1384.0
        assert train.return_train_number == "12952"
        assert train.has_sleeper is False
        assert train.has_third_ac is True
        assert train.has_second_ac is True
        assert train.has_first_ac is True
        assert train.has_first_class is False
        assert train.has_chair_car is False
        assert len(train.route_geometry_coordinates) == 2
        assert train.validation_warnings == ()

    def test_leading_zero_in_train_number_preserved(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature(number="04601", name="Jammu Tawi Udhampur Special")
        file_path = tmp_path / "special_train.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 1
        assert result.records[0].number == "04601"
        assert isinstance(result.records[0].number, str)

    def test_train_name_special_characters_and_suffixes_preserved(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        name_with_suffix = "Ernakulam - Pune SF Express (Via Panvel) [Special]"
        feat = _make_feature(name=name_with_suffix)
        file_path = tmp_path / "suffix_train.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 1
        assert result.records[0].name == name_with_suffix

    def test_coach_flags_parsing_from_integers_and_strings(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature()
        feat["properties"]["sleeper"] = "1"
        feat["properties"]["chair_car"] = 1
        feat["properties"]["first_class"] = True
        file_path = tmp_path / "coach_flags.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        train = result.records[0]
        assert train.has_sleeper is True
        assert train.has_chair_car is True
        assert train.has_first_class is True


class TestDataMeetTrainAdapterOptionalFieldsAndWarnings:
    """Verifies Correction 2: Optional fields do not quarantine valid train headers."""

    def test_missing_departure_and_arrival_times_accepted_with_warnings(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature(departure="", arrival="")
        file_path = tmp_path / "no_times.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 1
        assert len(result.quarantined) == 0
        train = result.records[0]
        assert train.departure_time is None
        assert train.arrival_time is None
        assert any("DEPARTURE" in w for w in train.validation_warnings)
        assert any("ARRIVAL" in w for w in train.validation_warnings)

    def test_negative_distance_sentinel_accepted_with_warning(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature(distance=-1)
        file_path = tmp_path / "negative_dist.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 1
        assert len(result.quarantined) == 0
        train = result.records[0]
        assert train.distance_km is None
        assert any("NEGATIVE_DISTANCE" in w for w in train.validation_warnings)

    def test_negative_duration_sentinel_accepted_with_warning(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature(duration_h=-1, duration_m=-1)
        file_path = tmp_path / "negative_dur.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 1
        assert len(result.quarantined) == 0
        train = result.records[0]
        assert train.duration_hours is None
        assert train.duration_minutes is None
        assert any("INVALID_DURATION" in w for w in train.validation_warnings)

    def test_degenerate_linestring_geometry_accepted_with_warning(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        # 1-point LineString
        feat = _make_feature(coords=[[73.120353, 22.050722]])
        file_path = tmp_path / "single_point.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 1
        assert len(result.quarantined) == 0
        train = result.records[0]
        assert len(train.route_geometry_coordinates) == 1
        assert any("DEGENERATE_LINESTRING" in w for w in train.validation_warnings)

    def test_missing_or_null_geometry_accepted_with_warning(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature()
        feat["geometry"] = None
        file_path = tmp_path / "null_geom.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 1
        assert len(result.quarantined) == 0
        train = result.records[0]
        assert train.route_geometry_coordinates == ()
        assert any("MISSING_GEOMETRY" in w for w in train.validation_warnings)


class TestDataMeetTrainAdapterQuarantineRules:
    """Verifies strict quarantine of invalid required fields and station references."""

    def test_missing_train_number_quarantined(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature(number="")
        file_path = tmp_path / "no_number.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 0
        assert len(result.quarantined) == 1
        q = result.quarantined[0]
        assert "MISSING_TRAIN_NUMBER" in q.rejection_codes

    def test_missing_train_name_quarantined(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature(name="   ")
        file_path = tmp_path / "no_name.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 0
        assert len(result.quarantined) == 1
        q = result.quarantined[0]
        assert "MISSING_TRAIN_NAME" in q.rejection_codes

    def test_missing_origin_station_code_quarantined(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature(from_code="")
        file_path = tmp_path / "no_origin.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 0
        assert len(result.quarantined) == 1
        assert "MISSING_ORIGIN_STATION_CODE" in result.quarantined[0].rejection_codes

    def test_missing_destination_station_code_quarantined(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature(to_code="")
        file_path = tmp_path / "no_dest.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 0
        assert len(result.quarantined) == 1
        assert "MISSING_DESTINATION_STATION_CODE" in result.quarantined[0].rejection_codes

    def test_identical_origin_and_destination_quarantined(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature(from_code="NDLS", to_code="ndls")
        file_path = tmp_path / "identical_endpoints.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 0
        assert len(result.quarantined) == 1
        assert "IDENTICAL_ENDPOINT_STATIONS" in result.quarantined[0].rejection_codes

    def test_collective_duplicate_train_number_quarantined(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat1 = _make_feature(number="12345", name="Train A", from_code="MMCT", to_code="NDLS")
        feat2 = _make_feature(number="12345", name="Train B", from_code="HWH", to_code="CSMT")
        file_path = tmp_path / "duplicate_numbers.json"
        file_path.write_text(json.dumps(_make_geojson([feat1, feat2])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 0
        assert len(result.quarantined) == 2
        for q in result.quarantined:
            assert "DUPLICATE_TRAIN_NUMBER" in q.rejection_codes
            assert q.original_train_number == "12345"

    def test_unresolved_station_references_quarantined_when_filter_provided(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        # Train with origin in verified set, destination not in verified set
        feat = _make_feature(from_code="VALID1", to_code="UNKNOWN2")
        file_path = tmp_path / "unresolved.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path, valid_station_codes=["VALID1", "VALID2"])
        assert len(result.records) == 0
        assert len(result.quarantined) == 1
        q = result.quarantined[0]
        assert "UNRESOLVED_DESTINATION_STATION" in q.rejection_codes
        assert "UNRESOLVED_ORIGIN_STATION" not in q.rejection_codes

    def test_malformed_feature_and_properties_quarantined(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        features = [
            "not a dictionary",
            {"type": "NotAFeature"},
            {"type": "Feature"},  # Missing properties
            {"type": "Feature", "properties": "not a dict"},
        ]
        file_path = tmp_path / "malformed_features.json"
        file_path.write_text(json.dumps(_make_geojson(features)), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.records) == 0
        assert len(result.quarantined) == 4
        codes = [q.rejection_codes[0] for q in result.quarantined]
        assert "MALFORMED_FEATURE_OBJECT" in codes
        assert "NOT_FEATURE_TYPE" in codes
        assert "MISSING_PROPERTIES" in codes
        assert "MALFORMED_PROPERTIES_OBJECT" in codes


class TestDataMeetTrainAdapterImmutabilityAndAudit:
    """Verifies frozen immutability, collections normalization, and raw payload auditability."""

    def test_audit_record_preserves_untruncated_frozen_payload(self, tmp_path):
        adapter = DataMeetTrainAdapter()
        feat = _make_feature()
        feat["properties"]["custom_unmapped_field"] = "audit_data_value"
        file_path = tmp_path / "audit_test.json"
        file_path.write_text(json.dumps(_make_geojson([feat])), encoding="utf-8")

        result = adapter.adapt(file_path)
        assert len(result.accepted) == 1
        audit = result.accepted[0]

        assert isinstance(audit.raw_payload, MappingProxyType)
        assert audit.raw_payload["properties"]["custom_unmapped_field"] == "audit_data_value"

        with pytest.raises(TypeError):
            audit.raw_payload["new_key"] = "illegal"

    def test_direct_construction_normalizes_collections_to_tuples(self):
        train = DataMeetTrainRecord(
            number="12951",
            name="Rajdhani",
            origin_code="MMCT",
            destination_code="NDLS",
            route_geometry_coordinates=deque([(72.8, 18.9), (77.2, 28.6)]),
            validation_warnings=["WARN1", "WARN2"],
        )
        assert isinstance(train.route_geometry_coordinates, tuple)
        assert isinstance(train.validation_warnings, tuple)

        quarantine = TrainQuarantineRecord(
            source_file="test.json",
            source_record_index=0,
            original_train_number="12345",
            original_train_name="Test",
            rejection_codes=deque(["ERROR_A", "ERROR_B"]),
            validation_messages={"msg1", "msg2"},
            raw_payload={"k": "v"},
        )
        assert isinstance(quarantine.rejection_codes, tuple)
        assert isinstance(quarantine.validation_messages, tuple)
        assert isinstance(quarantine.raw_payload, MappingProxyType)

        prov = SourceProvenance()
        res = TrainAdapterResult(
            records=deque([train]),
            accepted=[AcceptedTrainRecord(train=train, source_record_index=0, original_train_number="12951", raw_payload={})],
            quarantined=deque([quarantine]),
            provenance=prov,
        )
        assert isinstance(res.records, tuple)
        assert isinstance(res.accepted, tuple)
        assert isinstance(res.quarantined, tuple)

    def test_invalid_collection_inputs_raise_type_error(self):
        with pytest.raises(TypeError) as exc:
            TrainAdapterResult(
                records="not a collection",
                accepted=(),
                quarantined=(),
                provenance=SourceProvenance(),
            )
        assert "must be an iterable collection" in str(exc.value)

        with pytest.raises(TypeError) as exc:
            TrainQuarantineRecord(
                source_file="test.json",
                source_record_index=0,
                original_train_number="123",
                original_train_name="A",
                rejection_codes={"not": "a list"},
                validation_messages=(),
                raw_payload={},
            )
        assert "must be an iterable collection" in str(exc.value)


class TestDataMeetTrainAdapterBaselineReconciliation:
    """
    Executes full reconciliation against the actual local DataMeet baseline snapshot.
    Verifies exact figures in compliance with CTO approvals and Correction 1 & 2.
    """

    def test_baseline_dataset_cryptographic_provenance_and_full_reconciliation(self):
        if not TRAINS_DATA_PATH.exists() or not STATIONS_DATA_PATH.exists():
            pytest.skip("DataMeet baseline datasets not present in expected source directory")

        # Load station adapter foundation to obtain geocoded station codes
        station_adapter = DataMeetStationAdapter()
        station_result = station_adapter.adapt(STATIONS_DATA_PATH)
        assert station_result.provenance.accepted_records_count == 8697
        geocoded_station_codes = {s.code for s in station_result.records}
        assert len(geocoded_station_codes) == 8697

        # Run train adapter
        train_adapter = DataMeetTrainAdapter()
        train_result = train_adapter.adapt(TRAINS_DATA_PATH, valid_station_codes=geocoded_station_codes)

        # 1. Total records check
        assert train_result.provenance.total_source_records == 5208

        # 2. Cryptographic checksum check
        assert train_result.provenance.file_sha256 == "e434d9c56016ccdf2291ccd446586ef87a7fab101084efa5f68871ab27800167"
        assert train_result.provenance.file_size_bytes == 14768598
        assert train_result.provenance.source_license == "CC0 1.0 Universal"

        # 3. Exact reconciliation under CTO approved rules:
        # Accepted: 5,175
        # Quarantined: 33 (1 missing name + 15 unresolved origin + 17 unresolved destination)
        # Sum: 5,175 + 33 = 5,208
        assert len(train_result.records) == 5175
        assert len(train_result.accepted) == 5175
        assert len(train_result.quarantined) == 33
        assert len(train_result.records) + len(train_result.quarantined) == 5208
        assert train_result.provenance.accepted_records_count == 5175
        assert train_result.provenance.quarantined_records_count == 33

        # 4. Quarantine category breakdown:
        counts = dict(train_result.provenance.rejection_reason_counts)
        assert counts.get("MISSING_TRAIN_NAME") == 1
        assert counts.get("UNRESOLVED_ORIGIN_STATION") == 15
        assert counts.get("UNRESOLVED_DESTINATION_STATION") == 17
        assert sum(counts.values()) == 33

        # 5. Missing name feature verification:
        missing_name_q = [q for q in train_result.quarantined if "MISSING_TRAIN_NAME" in q.rejection_codes]
        assert len(missing_name_q) == 1
        assert missing_name_q[0].original_train_number == "06345"
        assert missing_name_q[0].source_record_index == 4918

        # 6. Accepted records integrity:
        unique_accepted_numbers = {t.number for t in train_result.records}
        assert len(unique_accepted_numbers) == 5175

        # 7. Validation warnings on accepted records (Correction 2 verification):
        # 2 accepted records with degenerate LineString coordinates (DLN <-> TRG: 53647 & 53648)
        degenerate_geom_records = [
            t for t in train_result.records
            if any("DEGENERATE_LINESTRING" in w for w in t.validation_warnings)
        ]
        assert len(degenerate_geom_records) == 2
        deg_numbers = {t.number for t in degenerate_geom_records}
        assert deg_numbers == {"53647", "53648"}

        # 15 accepted records with timing/distance anomalies (sentinel -1 / empty times)
        timing_anomaly_records = [
            t for t in train_result.records
            if t.distance_km is None or t.departure_time is None or t.arrival_time is None
        ]
        assert len(timing_anomaly_records) == 15

