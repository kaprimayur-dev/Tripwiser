# TW-103F Implementation Plan: Batch Persistence Engine, Manifest Generator & Ingestion CLI

**Milestone**: TW-103F — Database Persistence, Administrative CLI & PostGIS Spatial Verification  
**Author**: Lead Backend Engineer (AI Pair Programmer)  
**Date**: November 1, 2026  
**Status**: PROPOSED — Standing by for CTO Review  
**Prerequisites**: TW-103A (Fixture Foundation), TW-103B (Station Adapter), TW-103C (Train Adapter), TW-103D (Schedule Adapter), TW-103E (Two-Tier Integration Service). Latest commit: `a62e771e44e0e2d1cd19c8fc2481aa011cd7f8f9`.

---

## 1. Executive Summary & Context

Across milestones TW-103A through TW-103E, TripWiser built a pure, in-memory railway data ingestion and integration pipeline:
- **TW-103A**: Curated development fixture covering 50 hubs and 20 iconic trains (`bootstrap_railway_data.json`).
- **TW-103B**: DataMeet station source adapter resolving 8,697 geocoded stations and quarantining 293 null-coordinate stations.
- **TW-103C**: DataMeet train source adapter resolving 5,175 accepted trains and quarantining 33 invalid headers.
- **TW-103D**: DataMeet schedule source adapter ingesting 417,080 schedule records, deterministically ordering stops, preserving 21,756 incomplete timing stops without loss, strictly preserving `day=None` (zero-fabrication), and quarantining 2,904 invalid stops.
- **TW-103E**: Two-tier integration service (`RailwayDataIntegrationService`) binding stations, trains, and schedules into:
  - **Tier 1 (Integrated Railway Dataset)**: Complete network topology, audit trails, and preserved anomalies.
  - **Tier 2 (Compiled Domain Dataset)**: Validated domain entities (`Train`, `Station`) gated by verified calendars, complete day offsets, and aligned endpoints.

### The Missing Capability
The PostgreSQL/PostGIS database currently remains **completely empty**. There is no persistence pathway, no bulk upsert mechanism, no administrative CLI to run the ingestion pipeline, no cryptographic manifest generator, and no spatial query verification on the ingested network dataset.

**TW-103F** closes this gap by bridging the in-memory integration foundation with the PostgreSQL/PostGIS persistence layer.

---

## 2. Answers to Strategic Evaluation Questions

### Question 1: What functionality is still missing?
1. **Empty Database / Lack of Ingestion Pipeline**:
   - The PostgreSQL/PostGIS database has all schema tables (`stations`, `trains`, `train_schedules`) defined by Alembic migrations, but zero production or fixture network data has been ingested.
2. **Bulk / Batch Persistence Engine**:
   - Existing repositories (`SQLAlchemyStationRepository` and `SQLAlchemyTrainRepository`) only provide single-entity `save()` methods using individual `session.get()` and `session.flush()` operations.
   - Inserting 8,697 stations and hundreds of train schedules using individual queries would be inefficient and risk PostgreSQL parameter limits ($65,535$ parameter maximum in asyncpg).
   - An optimized, chunked bulk upsert engine (`insert().on_conflict_do_update`) with GeoAlchemy2 point geometries is missing.
3. **Cryptographic Manifest & Quarantine Artifact Generator**:
   - While adapters track quarantined and uncompiled records in memory, these records are not written to persistent disk artifacts (`data/quarantine/*.json` and `data/manifests/*.json`).
   - There is no automated generation of SHA-256 cryptographic provenance digests for ingested source files.
4. **Administrative Importer CLI**:
   - Operators and developers have no CLI command (`python -m app.cli.import_railway_data`) to execute dry-runs, ingest fixtures, ingest DataMeet, or export audit reports.
5. **PostGIS Geospatial Verification on Ingested Data**:
   - PostGIS spatial distance queries (`ST_DWithin`) and route searches (`find_direct_trains`) have only been tested against mock single-row test data, never verified against the full geocoded station master (8,697 stations) or compiled multi-day train routes.

---

### Question 2: What should TW-103F accomplish?
1. **Batch Persistence Service (`RailwayDataPersistenceService`)**:
   - Implement efficient chunked bulk upserts (e.g. 1,000 stations per batch) using PostgreSQL dialect `insert(StationORM).on_conflict_do_update(...)` with PostGIS point geometry `SRID=4326;POINT(lon lat)`.
   - Implement transactional bulk upsert for compiled trains and their schedules:
     - Persist parent trains into `trains`.
     - Replace/upsert child schedules into `train_schedules` with deterministic stop sequences.
     - Enforce foreign key order: stations must be persisted and committed before trains or schedules.
2. **Audit Manifest & Quarantine Exporter (`ImportManifestService`)**:
   - Compute SHA-256 digests for all input files (`stations.json`, `trains.json`, `schedules.json`, `bootstrap_railway_data.json`).
   - Emit an immutable `import_manifest_<timestamp>.json` documenting total source counts, accepted counts, quarantined counts, compiled counts, uncompiled counts with reason breakdown, duration, and dry-run flag.
   - Export structured quarantine files:
     - `data/quarantine/unresolved_stations.json` (293 stations)
     - `data/quarantine/unresolved_trains.json` (33 trains)
     - `data/quarantine/unresolved_schedule_stops.json` (2,904 stops)
     - `data/quarantine/uncompiled_trains.json` (5,167 trains with compilation exclusion reasons)
3. **Administrative Importer CLI (`python -m app.cli.import_railway_data`)**:
   - Command-line interface with options:
     - `--source {fixture,datameet}`: Ingestion source (default: `fixture`).
     - `--dry-run`: Runs integration, checks integrity, and generates audit manifests without modifying the database.
     - `--persist-stations`: Ingest all accepted stations into the database.
     - `--persist-trains`: Ingest all compiled domain trains into the database.
     - `--persist-all`: Ingest both stations and compiled trains.
     - `--manifest-dir <path>`: Directory for audit manifests (default: `data/manifests`).
     - `--quarantine-dir <path>`: Directory for quarantine files (default: `data/quarantine`).
   - Clean, human-readable terminal table output detailing reconciliation metrics.
4. **PostGIS Spatial Verification & Integration Tests**:
   - Integration tests executing real PostGIS queries against the database populated by the batch persistence engine:
     - `ST_DWithin` radius queries around major hubs (Delhi, Mumbai, Bengaluru, Kolkata, Chennai).
     - Direct train route queries (`find_direct_trains`) across multiple legs.
     - Idempotency verification: running the importer multiple times results in zero duplicate rows and zero constraint errors.

---

### Question 3: Which existing components should it reuse?
- **Source Adapters**:
  - `DataMeetStationAdapter` ([`station_adapter.py`](file:///c:/projects/tripwiser/backend/app/infrastructure/adapters/datameet/station_adapter.py))
  - `DataMeetTrainAdapter` ([`train_adapter.py`](file:///c:/projects/tripwiser/backend/app/infrastructure/adapters/datameet/train_adapter.py))
  - `DataMeetScheduleAdapter` ([`schedule_adapter.py`](file:///c:/projects/tripwiser/backend/app/infrastructure/adapters/datameet/schedule_adapter.py))
- **Integration Engine**:
  - `RailwayDataIntegrationService` ([`service.py`](file:///c:/projects/tripwiser/backend/app/infrastructure/integration/service.py))
  - `IntegratedRailwayDataset`, `CompiledDomainDataset`, `IntegratedTrainRecord` ([`models.py`](file:///c:/projects/tripwiser/backend/app/infrastructure/integration/models.py))
  - `FixtureCalendarProvider`, `DictCalendarProvider` ([`calendar_provider.py`](file:///c:/projects/tripwiser/backend/app/infrastructure/integration/calendar_provider.py))
- **Domain Models (Unmodified)**:
  - `Station` ([`station.py`](file:///c:/projects/tripwiser/backend/app/domain/models/station.py))
  - `Train`, `TrainScheduleEntry` ([`train.py`](file:///c:/projects/tripwiser/backend/app/domain/models/train.py))
- **Database Layer (Unmodified ORM & Session)**:
  - `StationORM` ([`station.py`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/models/station.py))
  - `TrainORM`, `ScheduleORM` ([`train.py`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/models/train.py))
  - `AsyncSessionLocal`, `check_database_health` ([`db.py`](file:///c:/projects/tripwiser/backend/app/core/db.py))
- **Source Data & Fixtures**:
  - `bootstrap_railway_data.json` (curated fixture)
  - `stations.json`, `trains.json`, `schedules.json` (DataMeet sources)

---

### Question 4: What dependencies or blockers exist?
1. **Foreign Key Dependency**:
   - `trains.origin_code`, `trains.destination_code`, and `train_schedules.station_code` enforce foreign keys against `stations.code`.
   - *Requirement*: Stations must always be persisted and committed before trains or schedules are inserted.
2. **PostgreSQL Parameter Limits**:
   - asyncpg / PostgreSQL limits query parameters to 65,535.
   - Ingesting 8,697 stations (6 columns each = 52,182 parameters) is near the driver limit.
   - *Requirement*: Station and schedule bulk upserts must use batch chunking (e.g. 1,000 stations per chunk, 500 schedules per chunk).
3. **Zero-Fabrication Constraint on Persistence**:
   - Only Tier 2 compiled domain trains (which have verified running days from the calendar provider) can be persisted to the `trains` table, because the database column `trains.runs_on_days` is `NOT NULL` and domain integrity forbids synthetic calendars.
   - Tier 1 stations (all 8,697 geocoded stations) CAN and SHOULD be persisted into `stations` to establish the full spatial station master.
   - Non-qualifying trains remain in Tier 1 and are written to `data/quarantine/uncompiled_trains.json` with explicit exclusion reasons (`AWAITING_RUNNING_CALENDAR`, `UNKNOWN_DAY_OFFSET`, etc.).
4. **PostgreSQL/PostGIS Container Health**:
   - Persistence and spatial tests require the `tripwiser-db` Docker container to be healthy. The CLI and tests will include database health pre-checks.

---

### Question 5: What exact files are expected to change?

#### New Files (to be created):
1. `backend/app/infrastructure/persistence/__init__.py`
2. `backend/app/infrastructure/persistence/batch_persistence.py`
   - `RailwayDataPersistenceService` implementing chunked bulk upserts using SQLAlchemy PostgreSQL dialect (`insert().on_conflict_do_update(...)`).
3. `backend/app/infrastructure/manifest/__init__.py`
4. `backend/app/infrastructure/manifest/manifest_service.py`
   - `ImportManifestService` computing SHA-256 hashes, generating `import_manifest_<timestamp>.json`, and exporting quarantine/uncompiled JSON files.
5. `backend/app/cli/__init__.py`
6. `backend/app/cli/import_railway_data.py`
   - Administrative CLI entrypoint with `--source`, `--dry-run`, `--persist-stations`, `--persist-trains`, `--persist-all`, `--manifest-dir`, `--quarantine-dir`.
7. `backend/tests/unit/cli/test_import_cli.py`
   - Unit tests covering CLI argument parsing, dry-run flags, error handling, and terminal output.
8. `backend/tests/unit/manifest/test_manifest_service.py`
   - Unit tests covering cryptographic SHA-256 calculation, manifest structure, and quarantine file emission.
9. `backend/tests/integration/database/test_batch_persistence.py`
   - Integration tests covering chunked bulk upserts, transactional rollbacks, PostGIS `ST_DWithin` queries, route lookups, and idempotency across repeated runs.
10. `TW103F_IMPLEMENTATION_PLAN.md` (this plan)

#### Existing Files to be Modified:
- **Zero**. Existing domain models, database schemas, ORM models, migrations, and prior adapter tests remain completely untouched.

---

## 3. Detailed Component Architecture

### 3.1 Batch Persistence Service (`RailwayDataPersistenceService`)
```text
RailwayDataPersistenceService
├── bulk_upsert_stations(stations: Sequence[Station], chunk_size: int = 1000) -> int
│   ├── Chunks stations into slices of 1,000
│   ├── Converts Station domain entities to dictionary rows with WKT POINT geometries
│   ├── Executes postgresql.insert(StationORM).on_conflict_do_update(
│   │       index_elements=['code'],
│   │       set_={'name': ..., 'city': ..., 'state': ..., 'zone': ..., 'location': ...}
│   │   )
│   └── Returns total upserted station count
│
├── bulk_upsert_trains(trains: Sequence[Train], chunk_size: int = 500) -> int
│   ├── Upserts parent TrainORM records
│   ├── Clears and bulk-inserts ScheduleORM records per train
│   └── Returns total upserted train count
│
└── verify_postgis_health() -> bool
```

### 3.2 Import Manifest Service (`ImportManifestService`)
```text
ImportManifestService
├── compute_file_sha256(path: Path) -> str
├── generate_manifest(dataset: IntegratedRailwayDataset, dry_run: bool) -> ImportManifest
├── export_quarantine_artifacts(dataset: IntegratedRailwayDataset, out_dir: Path) -> None
│   ├── writes unresolved_stations.json
│   ├── writes unresolved_trains.json
│   ├── writes unresolved_schedule_stops.json
│   └── writes uncompiled_trains.json
└── save_manifest(manifest: ImportManifest, out_path: Path) -> None
```

### 3.3 Administrative CLI Interface (`python -m app.cli.import_railway_data`)
```bash
python -m app.cli.import_railway_data \
    --source [fixture|datameet] \
    --dry-run \
    --persist-all \
    --manifest-dir data/manifests \
    --quarantine-dir data/quarantine
```

---

## 4. Test Verification Plan

1. **Unit Test Suite**:
   - `test_import_cli.py`: Flag parsing, default arguments, dry-run simulation, stdout formatting.
   - `test_manifest_service.py`: SHA-256 accuracy, manifest JSON schema conformance, quarantine payload serialization.
2. **Integration Test Suite**:
   - `test_batch_persistence.py`:
     - Test chunked bulk upsert of 8,697 stations into PostGIS in under 5 seconds.
     - Test PostGIS `ST_DWithin` spatial distance query against real stations (e.g. stations within 50 km of New Delhi).
     - Test bulk upsert of compiled trains and schedules.
     - Test `find_direct_trains` query against persisted data.
     - Test idempotency: re-running upsert yields identical row counts without error.
3. **Full Regression Test Suite**:
   - All 189 existing tests must continue to pass without failure or degradation.

---

## 5. Architectural Guardrails & Commitments

- **No Domain Changes**: No modifications to `backend/app/domain/...`.
- **No Schema Changes**: No new migrations or alterations to database tables.
- **Zero Fabrication**: `day_offset=None` preserved in Tier 1; only verified trains compiled and persisted; zero synthetic running days.
- **Idempotency**: Running persistence multiple times must be completely safe and deterministic.

---

## 6. Standing By for CTO Authorization

This plan is complete and standing by for CTO review. **No implementation has begun, no existing files have been modified, and nothing has been staged or committed.**

