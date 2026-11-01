"""
Unit tests for ImportManifestService.
"""

import pytest
import json
from pathlib import Path
from types import MappingProxyType

from app.infrastructure.manifest.manifest_service import (
    ImportManifestService,
    _deep_unfreeze,
    ManifestJSONEncoder,
)
from app.infrastructure.integration.models import (
    IntegratedRailwayDataset,
    IntegratedTrainRecord,
)
from app.domain.models.station import Station
from app.infrastructure.adapters.datameet.models import QuarantineRecord
from app.infrastructure.adapters.datameet.train_models import (
    DataMeetTrainRecord,
    TrainQuarantineRecord,
)
from app.infrastructure.adapters.datameet.schedule_models import (
    ScheduleQuarantineRecord,
)


class TestManifestServiceUnit:
    """Verifies SHA-256 calculation, manifest structure, and quarantine artifact emission."""

    def test_compute_file_sha256(self, tmp_path):
        sample_file = tmp_path / "sample.txt"
        sample_file.write_text("Hello TripWiser Ingestion", encoding="utf-8")
        # SHA-256 of "Hello TripWiser Ingestion"
        digest = ImportManifestService.compute_file_sha256(sample_file)
        assert isinstance(digest, str)
        assert len(digest) == 64

    def test_deep_unfreeze_and_encoder(self):
        nested = {
            "a": MappingProxyType({"b": MappingProxyType({"c": 123})}),
            "tags": {"hub", "junction"},
        }
        unfrozen = _deep_unfreeze(nested)
        assert isinstance(unfrozen["a"], dict)
        assert isinstance(unfrozen["a"]["b"], dict)
        assert unfrozen["a"]["b"]["c"] == 123

        dumped = json.dumps(nested, cls=ManifestJSONEncoder)
        assert '"c": 123' in dumped

    def test_manifest_generation_and_serialization(self, tmp_path):
        stn = Station(code="NDLS", name="New Delhi", latitude=28.64, longitude=77.22)
        q_station = QuarantineRecord(
            source_file="stations.json",
            source_record_index=1,
            original_station_code="NULL_ST",
            original_station_name="Unknown",
            rejection_codes=("NULL_COORDINATES",),
            validation_messages=("Coordinates missing",),
            raw_payload={"code": "NULL_ST"},
        )
        q_train = TrainQuarantineRecord(
            source_file="trains.json",
            source_record_index=1,
            original_train_number="00000",
            original_train_name="Invalid Train",
            rejection_codes=("SAME_ORIGIN_DESTINATION",),
            validation_messages=("Origin equals destination",),
            raw_payload={"number": "00000"},
        )
        q_stop = ScheduleQuarantineRecord(
            source_file="schedules.json",
            source_record_index=1,
            source_record_id=101,
            original_train_number="12951",
            original_station_code="UNLOC",
            rejection_codes=("UNLOCATED_STATION_REFERENCE",),
            validation_messages=("Station UNLOC not in station master",),
            raw_payload={"id": 101},
        )
        uncompiled_rec = IntegratedTrainRecord(
            header=DataMeetTrainRecord(
                number="12003",
                name="Lucknow Shatabdi",
                origin_code="LKO",
                destination_code="NDLS",
            ),
            uncompilable_reasons=("AWAITING_RUNNING_CALENDAR",),
        )

        dataset = IntegratedRailwayDataset(
            stations=(stn,),
            quarantined_stations=(q_station,),
            train_records=(uncompiled_rec,),
            uncompiled_trains=(uncompiled_rec,),
            quarantined_trains=(q_train,),
            quarantined_schedule_stops=(q_stop,),
        )

        sample_source = tmp_path / "source.json"
        sample_source.write_text("{}", encoding="utf-8")

        service = ImportManifestService()
        manifest = service.generate_manifest(
            dataset=dataset,
            source_paths=[sample_source],
            dry_run=True,
            persisted_stations=1,
            persisted_trains=0,
            duration_sec=1.5,
        )

        assert manifest["dry_run"] is True
        assert manifest["reconciliation"]["stations"]["total"] == 2
        assert manifest["reconciliation"]["stations"]["accepted"] == 1
        assert manifest["reconciliation"]["stations"]["quarantined"] == 1
        assert manifest["reconciliation"]["trains"]["total"] == 2
        assert manifest["reconciliation"]["trains"]["quarantined"] == 1
        assert manifest["reconciliation"]["trains"]["uncompiled_tier1"] == 1
        assert manifest["uncompiled_train_exclusion_reasons"]["AWAITING_RUNNING_CALENDAR"] == 1

        # Test Save Manifest
        manifest_out = tmp_path / "manifest.json"
        saved_path = service.save_manifest(manifest, manifest_out)
        assert saved_path.exists()

        # Test Export Quarantine Artifacts
        quarantine_dir = tmp_path / "quarantine"
        artifacts = service.export_quarantine_artifacts(dataset, quarantine_dir)
        assert "unresolved_stations" in artifacts
        assert "unresolved_trains" in artifacts
        assert "unresolved_schedule_stops" in artifacts
        assert "uncompiled_trains" in artifacts

        for key, p in artifacts.items():
            assert p.exists()
            with open(p, "r", encoding="utf-8") as f:
                content = json.load(f)
                assert len(content) == 1

