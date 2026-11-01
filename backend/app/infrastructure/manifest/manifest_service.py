"""
Import Manifest and Quarantine Export Service.

Computes cryptographic hashes, records mathematical reconciliation metrics,
and writes structured quarantine and uncompiled audit artifacts to disk.
"""

from typing import Dict, Any, Sequence, Optional, Mapping
from pathlib import Path
import hashlib
import json
import datetime
from collections import Counter
from types import MappingProxyType

from app.infrastructure.integration.models import IntegratedRailwayDataset


class ManifestJSONEncoder(json.JSONEncoder):
    """Handles MappingProxyType, sets, dates, and times gracefully during serialization."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (Mapping, MappingProxyType)):
            return dict(obj)
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if isinstance(obj, (datetime.date, datetime.time, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)


def _deep_unfreeze(obj: Any) -> Any:
    """Recursively converts MappingProxyType and collections into standard JSON-serializable types."""
    if isinstance(obj, (Mapping, MappingProxyType)):
        return {k: _deep_unfreeze(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_deep_unfreeze(v) for v in obj]
    if isinstance(obj, (datetime.date, datetime.time, datetime.datetime)):
        return obj.isoformat()
    return obj


class ImportManifestService:
    """
    Manages cryptographic provenance tracking, manifest generation, and quarantine artifact emission.
    """

    @staticmethod
    def compute_file_sha256(path: Path | str) -> str:
        """Computes SHA-256 digest of a local file in 64KB blocks."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Source file not found for hash computation: {p}")
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def inspect_file(path: Path | str) -> Dict[str, Any]:
        """Returns path, byte size, and SHA-256 hash of a file."""
        p = Path(path)
        return {
            "path": str(p.resolve()),
            "size_bytes": p.stat().st_size if p.is_file() else 0,
            "sha256": ImportManifestService.compute_file_sha256(p) if p.is_file() else None,
        }

    def generate_manifest(
        self,
        dataset: IntegratedRailwayDataset,
        source_paths: Sequence[Path | str],
        dry_run: bool = True,
        persisted_stations: int = 0,
        persisted_trains: int = 0,
        duration_sec: float = 0.0,
        manifest_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates an immutable audit dictionary detailing source provenance, reconciliation,
        and persistence metrics.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        m_id = manifest_id or f"manifest_{now.strftime('%Y%m%d_%H%M%S')}"

        sources = {}
        for sp in source_paths:
            p = Path(sp)
            if p.exists():
                sources[p.name] = self.inspect_file(p)

        # Count uncompiled reasons
        reason_counter: Counter[str] = Counter()
        for rec in dataset.uncompiled_trains:
            for r in rec.uncompilable_reasons:
                reason_counter[r] += 1

        # Calculate incomplete and missing day counts
        incomplete_count = sum(1 for s in dataset.schedule_stops if not s.is_timing_complete)
        missing_days_count = sum(1 for s in dataset.schedule_stops if s.day is None)

        total_stations = len(dataset.stations) + len(dataset.quarantined_stations)
        total_trains = len(dataset.train_records) + len(dataset.quarantined_trains)
        total_stops = len(dataset.schedule_stops) + len(dataset.quarantined_schedule_stops)

        manifest = {
            "manifest_id": m_id,
            "created_at": now.isoformat(),
            "dry_run": dry_run,
            "execution_duration_sec": round(duration_sec, 3),
            "sources": sources,
            "reconciliation": {
                "stations": {
                    "total": total_stations,
                    "accepted": len(dataset.stations),
                    "quarantined": len(dataset.quarantined_stations),
                },
                "trains": {
                    "total": total_trains,
                    "accepted": len(dataset.train_records),
                    "quarantined": len(dataset.quarantined_trains),
                    "compiled_domain": len(dataset.compiled_trains),
                    "uncompiled_tier1": len(dataset.uncompiled_trains),
                },
                "schedule_stops": {
                    "total": total_stops,
                    "accepted": len(dataset.schedule_stops),
                    "quarantined": len(dataset.quarantined_schedule_stops),
                    "accepted_incomplete": incomplete_count,
                    "missing_day_offset": missing_days_count,
                },
            },
            "uncompiled_train_exclusion_reasons": dict(reason_counter.most_common()),
            "persistence": {
                "stations_persisted": persisted_stations,
                "trains_persisted": persisted_trains,
            },
        }

        return manifest

    def save_manifest(self, manifest: Dict[str, Any], out_path: Path | str) -> Path:
        """Serializes and writes the audit manifest to disk."""
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(_deep_unfreeze(manifest), f, indent=2, cls=ManifestJSONEncoder)
        return target

    def export_quarantine_artifacts(
        self,
        dataset: IntegratedRailwayDataset,
        out_dir: Path | str,
    ) -> Dict[str, Path]:
        """
        Exports structured quarantine and uncompiled files to out_dir,
        preserving source payloads, failure reasons, and exclusion reasons.
        """
        target_dir = Path(out_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        artifacts: Dict[str, Path] = {}

        # 1. Unresolved Stations
        stations_path = target_dir / "unresolved_stations.json"
        stations_data = [
            {
                "station_code": q.original_station_code,
                "station_name": q.original_station_name,
                "rejection_codes": list(q.rejection_codes),
                "validation_messages": list(q.validation_messages),
                "raw_payload": _deep_unfreeze(q.raw_payload) if q.raw_payload else None,
            }
            for q in dataset.quarantined_stations
        ]
        with open(stations_path, "w", encoding="utf-8") as f:
            json.dump(stations_data, f, indent=2, cls=ManifestJSONEncoder)
        artifacts["unresolved_stations"] = stations_path

        # 2. Unresolved Trains
        trains_path = target_dir / "unresolved_trains.json"
        trains_data = [
            {
                "train_number": q.original_train_number,
                "train_name": q.original_train_name,
                "rejection_codes": list(q.rejection_codes),
                "validation_messages": list(q.validation_messages),
                "raw_payload": _deep_unfreeze(q.raw_payload) if q.raw_payload else None,
            }
            for q in dataset.quarantined_trains
        ]
        with open(trains_path, "w", encoding="utf-8") as f:
            json.dump(trains_data, f, indent=2, cls=ManifestJSONEncoder)
        artifacts["unresolved_trains"] = trains_path

        # 3. Unresolved Schedule Stops
        stops_path = target_dir / "unresolved_schedule_stops.json"
        stops_data = [
            {
                "source_record_id": q.source_record_id,
                "train_number": q.original_train_number,
                "station_code": q.original_station_code,
                "rejection_codes": list(q.rejection_codes),
                "validation_messages": list(q.validation_messages),
                "raw_payload": _deep_unfreeze(q.raw_payload) if q.raw_payload else None,
            }
            for q in dataset.quarantined_schedule_stops
        ]
        with open(stops_path, "w", encoding="utf-8") as f:
            json.dump(stops_data, f, indent=2, cls=ManifestJSONEncoder)
        artifacts["unresolved_schedule_stops"] = stops_path

        # 4. Uncompiled Trains (Tier 1 records awaiting calendars or endpoint resolution)
        uncompiled_path = target_dir / "uncompiled_trains.json"
        uncompiled_data = [
            {
                "train_number": rec.header.number if rec.header else None,
                "train_name": rec.header.name if rec.header else None,
                "origin_station_code": rec.header.origin_code if rec.header else None,
                "destination_station_code": rec.header.destination_code if rec.header else None,
                "stop_count": rec.schedule.total_stops if rec.schedule else 0,
                "exclusion_reasons": list(rec.uncompilable_reasons),
                "integration_warnings": list(rec.integration_warnings),
            }
            for rec in dataset.uncompiled_trains
        ]
        with open(uncompiled_path, "w", encoding="utf-8") as f:
            json.dump(uncompiled_data, f, indent=2, cls=ManifestJSONEncoder)
        artifacts["uncompiled_trains"] = uncompiled_path

        return artifacts
