# TW-103B — RAILWAY SOURCE ADAPTER LAYER
## Architectural Design & Implementation Plan (CTO Refinement)

**Ticket**: TW-103B  
**Author**: Senior Backend Architect  
**Status**: REFINED PLANNING SPECIFICATION (AWAITING CTO APPROVAL)  
**Scope**: Purpose-built DataMeet station adapter, strict GeoJSON validation, duplicate quarantine protocol, exact record accounting, source reproducibility, and test plan.  
**Strict Boundary**: Documentation and planning only. Zero implementation code, zero domain/ORM changes, zero database modifications.  

---

## 1. Simplified Architecture: Focused DataMeet Station Adapter

Per CTO guidance, all speculative generic plugin frameworks and multi-layered type abstractions (`RailwaySourceAdapter[T_Raw, T_Domain]`) have been removed. 

TW-103B delivers a single, concrete, purpose-built source adapter: **`DataMeetStationAdapter`**.

### 1.1 Ingestion Pipeline
```text
┌──────────────────────────────────────────────┐
│  Local DataMeet File: stations.json          │
└──────────────────────┬───────────────────────┘
                       │ (local Path)
                       ▼
┌──────────────────────────────────────────────┐
│ DataMeetStationAdapter                       │
│ 1. Verifies local file existence & UTF-8     │
│ 2. Computes file SHA-256 and size in bytes   │
│ 3. Parses JSON FeatureCollection             │
│ 4. Pass 1: Index all station codes for       │
│    duplicate detection                       │
│ 5. Pass 2: Feature-by-feature validation:    │
│    - Geometry type == "Point"                │
│    - Coordinates finite numeric [lon, lat]   │
│    - Explicit inversion to (lat, lon)        │
│    - Boundary checks & (0,0) rejection      │
│    - Non-empty code & name                   │
│    - Duplicate code collision screening      │
│ 6. Segregates into Accepted vs Quarantined   │
│ 7. Creates Station domain models for valid   │
│ 8. Assembles SourceProvenance & audit stats  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ AdapterResult                                │
│ - records: list[Station]                     │
│ - quarantined: list[QuarantineRecord]        │
│ - provenance: SourceProvenance               │
└──────────────────────────────────────────────┘
```

### 1.2 Out-of-Scope Items (Deferred from TW-103B)
1. **Curated Fixture Loader (`BootstrapFixtureLoader`)**: Kept separate from external source adapters. TW-103A's `bootstrap_railway_data.json` is an internal canonical fixture, not an external raw source. It will be addressed in a future ticket.
2. **Timetable Adapters**: No timetable adapter will be designed until an approved, authoritative, production-wide bulk timetable dataset is formally identified.
3. **Database Import Pipeline**: Persisting records via SQLAlchemy/PostgreSQL belongs to TW-103C/D.
4. **Remote Fetching / Network Scraping**: The adapter operates strictly on local files. Network downloads and scraping are prohibited.

---

## 2. Source Reproducibility & Provenance Structure

The adapter does not guess or invent repository metadata or timestamps. It computes dynamic cryptographic hashes from the physical file payload.

### 2.1 Authoritative Source Metadata
- **Source Repository**: `https://github.com/datameet/railways`
- **Source File Path**: `stations.json`
- **Source Licence**: `ODbL - Open Database License v1.0`
- **Verified Local Baseline File Size**: `1,864,683 bytes` (~1.86 MB)
- **Verified Local Baseline SHA-256**: `9bd5e1da3a859e5359a95f40b6009aa468efb177da4faac57ffdcd7daeb4df18`

### 2.2 Provenance Data Structure
```python
@dataclass(frozen=True)
class SourceProvenance:
    source_repository_url: str
    source_file_path: str
    repository_snapshot_id: str | None  # Git commit hash if known, else explicit local snapshot tag
    source_license: str
    file_sha256: str                    # Calculated via hashlib.sha256() over raw bytes
    file_size_bytes: int                # Exact byte count of input file
    import_timestamp: datetime.datetime # UTC ISO-8601 timestamp at execution
    adapter_version: str                # e.g., "1.0.0"
    total_source_records: int           # Total features in FeatureCollection
    accepted_records_count: int         # Count of valid Station objects produced
    quarantined_records_count: int      # Count of unique rejected features
    rejection_reason_counts: dict[str, int] # Failure occurrences per error code
```

---

## 3. Strict GeoJSON Validation Specification

Every feature in the GeoJSON payload must satisfy strict structural, type, and geographic constraints. Conversion of invalid types (e.g., string coordinates `"28.61"` or booleans `True`) is strictly forbidden.

### 3.1 Structural & Type Rules
1. **Root Object**:
   - Must be a JSON dictionary with `"type": "FeatureCollection"`.
   - Must contain a `"features"` key whose value is a JSON `list`.
2. **Feature Elements**:
   - Must be a JSON dictionary with `"type": "Feature"`.
   - Must contain a `"properties"` key whose value is a JSON `dict`.
   - Must contain a `"geometry"` key (may be `null` in invalid source records).
3. **Station Code (`properties.code`)**:
   - Must be present, non-null, and a string.
   - Stripped value `code.strip()` must be non-empty (`len >= 1`).
   - If missing, null, non-string, or whitespace-only $\to$ quarantine with `MISSING_STATION_CODE`.
4. **Station Name (`properties.name`)**:
   - Must be present, non-null, and a string.
   - Stripped value `name.strip()` must be non-empty (`len >= 1`).
   - If missing, null, non-string, or whitespace-only $\to$ quarantine with `MISSING_STATION_NAME`.
5. **Geometry & Coordinates (`geometry`)**:
   - If `geometry is None` $\to$ quarantine with `NULL_GEOMETRY`.
   - If `geometry.get("type") != "Point"` $\to$ quarantine with `NOT_POINT_GEOMETRY`.
   - If `geometry.get("coordinates") is None` $\to$ quarantine with `MISSING_COORDINATES`.
   - Coordinates must be a `list` or `tuple` with **exactly two elements** (`len == 2`). If not $\to$ quarantine with `MALFORMED_COORDINATES_COUNT`.
   - **Type Enforcement**: Each coordinate must be `isinstance(c, (int, float)) and not isinstance(c, bool)`.
     *(Note: in Python, `bool` is a subclass of `int`; `isinstance(True, int)` evaluates to `True`. Explicit boolean rejection is required).* If non-numeric or boolean $\to$ quarantine with `NON_NUMERIC_COORDINATE`.
   - **Finiteness**: `math.isfinite(lon) and math.isfinite(lat)` must be `True`. Reject `NaN`, `Infinity`, `-Infinity` $\to$ quarantine with `NON_FINITE_COORDINATE`.
6. **Coordinate Inversion**:
   - Standard GeoJSON defines coordinates as `[longitude, latitude]`.
   - The adapter explicitly unpacks and inverts:
     $$\text{longitude} = \text{coordinates}[0], \quad \text{latitude} = \text{coordinates}[1]$$
     Instantiating domain `Station(latitude=latitude, longitude=longitude)`.
7. **Geographic Boundaries**:
   - Latitude must be between $-90.0$ and $+90.0$ inclusive. If outside $\to$ quarantine with `OUT_OF_BOUNDS_LATITUDE`.
   - Longitude must be between $-180.0$ and $+180.0$ inclusive. If outside $\to$ quarantine with `OUT_OF_BOUNDS_LONGITUDE`.
   - Null Island check: If $\text{latitude} == 0.0$ and $\text{longitude} == 0.0$ $\to$ quarantine with `DUMMY_ZERO_COORDINATES`.
8. **Preservation of Raw Properties**:
   - Unknown properties (`address`, `zone`, etc.) are retained in `QuarantineRecord.raw_payload` or an external audit map. They are **not** appended to the immutable `Station` domain model.

---

## 4. Collective Duplicate Quarantine Protocol

The previous draft proposed keeping the first occurrence and quarantining subsequent duplicates. This arbitrary selection is unsafe for railway routing.

### 4.1 Strict Group Quarantine Protocol
When a station code appears more than once in the source dataset:
1. **Full Conflict Detection**: In Pass 1, the adapter scans all features and indexes feature indices by station code:
   ```python
   code_occurrences: dict[str, list[int]]
   ```
2. **Collective Quarantine**: If `len(indices) > 1`, **EVERY** feature in that duplicate group is quarantined with `DUPLICATE_STATION_CODE`.
3. **Zero Arbitrary Selection**: None of the conflicting duplicate records are accepted into the canonical `Station` list.
4. **Auditability**: The quarantine report records the duplicate code, the indices of all conflicting records, and the total collision count.

---

## 5. Record Accounting & Disjoint Audit Verification

Forensic audit of `scratch/stations.json` (8,990 features) reveals the exact relationship between rejected features and failure reasons:

### 5.1 Rejection Forensics
```text
Total Features in Source:                  8,990
================================================
Unique Quarantined Records:                  293
Total Accepted Station Records:            8,697 (8,990 - 293)

Validation Failure Occurrences (Reasons):   294
  - NULL_GEOMETRY:                          293
  - MISSING_STATION_NAME:                     1
```

### 5.2 Disjoint Group Reconciliation & The Overlap
- The failure reasons are **not** fully disjoint across records.
- **Feature Index 3235** (`code: "P"`, `name: ""`, `geometry: None`) suffers from **both** `NULL_GEOMETRY` and `MISSING_STATION_NAME`.
- The previous calculation ($8,990 - 294 = 8,696$) erroneously conflated **failure reason occurrences (294)** with **unique rejected records (293)**.
- **Exact Equation**:
  $$\text{Total Records} (8,990) = \text{Accepted Records} (8,697) + \text{Unique Quarantined Records} (293)$$
  $$\text{Failure Occurrences} (294) = 293 \times (\text{NULL\_GEOMETRY only}) + 1 \times (\text{NULL\_GEOMETRY} \land \text{MISSING\_NAME})$$

The adapter's accounting cleanly separates `quarantined_records_count` (cardinality of rejected set = 293) from `rejection_reason_counts` (sum of failure codes = 294).

---

## 6. Minimal Data Structures

```python
from dataclasses import dataclass, field
import datetime
from pathlib import Path
from app.domain.models.station import Station

@dataclass(frozen=True)
class QuarantineRecord:
    source_file: str
    source_record_index: int               # 0-based index in GeoJSON features list
    original_station_code: str | None      # Code extracted if available, else None
    original_station_name: str | None      # Name extracted if available, else None
    rejection_codes: list[str]             # List of all failure reasons (e.g. ['NULL_GEOMETRY', 'MISSING_STATION_NAME'])
    validation_messages: list[str]         # Human-readable failure diagnostics
    raw_payload: dict                      # Safe copy of the raw GeoJSON feature dictionary

@dataclass
class AdapterResult:
    records: list[Station]                 # Successfully validated immutable domain models
    quarantined: list[QuarantineRecord]    # Quarantined raw records with diagnostics
    provenance: SourceProvenance           # Execution and cryptographic audit metadata
```

---

## 7. Proposed File Structure for TW-103B

The structure is minimal, maintainable, and free of speculative abstractions:

```text
backend/app/infrastructure/adapters/
├── __init__.py
├── exceptions.py             # SourceAdapterError, MalformedSourceError, SourceEncodingError
└── datameet/
    ├── __init__.py
    ├── models.py             # QuarantineRecord, SourceProvenance, AdapterResult
    └── station_adapter.py    # DataMeetStationAdapter implementation

backend/tests/unit/adapters/
├── __init__.py
└── test_datameet_station_adapter.py  # Comprehensive unit test suite
```

---

## 8. Test Plan

The test suite will be implemented in `backend/tests/unit/adapters/test_datameet_station_adapter.py`. 

*Note on performance testing: Benchmark execution time is tracked separately from correctness tests. No brittle, machine-dependent runtime threshold (e.g. `assert duration < 1.0`) will be used as a hard assertion in CI.*

### 8.1 Test Matrix
| Test Case Name | Input Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `test_valid_feature_parsing_and_inversion` | Feature with coords `[75.45, 27.25]` | Instantiates `Station(code="BDHL", latitude=27.25, longitude=75.45)`. |
| `test_null_geometry_quarantined` | Feature with `"geometry": null` | Quarantined with `NULL_GEOMETRY`; absent from `records`. |
| `test_non_point_geometry_quarantined` | Feature with `"type": "LineString"` | Quarantined with `NOT_POINT_GEOMETRY`. |
| `test_missing_station_code_quarantined` | `"code": null`, `""`, or `"   "` | Quarantined with `MISSING_STATION_CODE`. |
| `test_missing_station_name_quarantined` | `"name": null`, `""`, or `"   "` | Quarantined with `MISSING_STATION_NAME`. |
| `test_missing_coordinates_quarantined` | `"coordinates": null` | Quarantined with `MISSING_COORDINATES`. |
| `test_wrong_coordinate_count_quarantined` | `"coordinates": [75.45]` or `[75.45, 27.25, 100.0]` | Quarantined with `MALFORMED_COORDINATES_COUNT`. |
| `test_string_coordinate_rejected` | `"coordinates": ["75.45", 27.25]` | Quarantined with `NON_NUMERIC_COORDINATE`; no silent string conversion. |
| `test_boolean_coordinate_rejected` | `"coordinates": [True, 27.25]` | Quarantined with `NON_NUMERIC_COORDINATE`; boolean rejected despite Python `int` inheritance. |
| `test_non_finite_coordinates_rejected` | Coordinates containing `NaN` or `Infinity` | Quarantined with `NON_FINITE_COORDINATE`. |
| `test_out_of_bounds_coordinates_quarantined` | Coordinates `[190.0, 27.25]` or `[75.45, 95.0]` | Quarantined with `OUT_OF_BOUNDS_LONGITUDE` or `OUT_OF_BOUNDS_LATITUDE`. |
| `test_dummy_zero_coordinates_quarantined` | Coordinates `[0.0, 0.0]` (Null Island) | Quarantined with `DUMMY_ZERO_COORDINATES`. |
| `test_collective_duplicate_quarantine` | 2 features sharing code `"GWL"` | Both records quarantined with `DUPLICATE_STATION_CODE`; neither accepted. |
| `test_malformed_json_raises_clean_error` | Non-JSON text content in file | Raises `MalformedSourceError` with line/col diagnostics; no unhandled crash. |
| `test_utf8_decoding_enforced` | Non-UTF-8 encoded binary payload | Raises `SourceEncodingError`. |
| `test_unknown_properties_preserved` | GeoJSON properties with extra metadata | Extra keys preserved in `QuarantineRecord.raw_payload`; domain model clean. |
| `test_provenance_and_checksum_verification` | Any valid input file | Calculates exact SHA-256 and byte size; verifies timestamps and counts. |
| `test_deterministic_parsing_output` | Executing twice on same payload | Outputs identical record counts, hashes, and quarantine ordering. |
| `test_full_datameet_dataset_reconciliation` | Full 8,990-feature `stations.json` | Total: 8,990; Accepted: 8,697; Quarantined: 293; Reasons: 294 (293 `NULL_GEOMETRY`, 1 `MISSING_STATION_NAME`). |

---

## 9. Implementation Steps for TW-103B

Once authorized by the CTO, implementation proceeds through four tightly scoped commits:

1. **Step 1: Data Structures & Exceptions**:
   - Implement `backend/app/infrastructure/adapters/exceptions.py`.
   - Implement `backend/app/infrastructure/adapters/datameet/models.py` (`QuarantineRecord`, `SourceProvenance`, `AdapterResult`).
2. **Step 2: DataMeet Station Adapter**:
   - Implement `backend/app/infrastructure/adapters/datameet/station_adapter.py`.
   - Implement SHA-256 calculation, strict GeoJSON validation, collective duplicate quarantine, and domain instantiation.
3. **Step 3: Unit Test Suite**:
   - Implement all 19 test cases in `backend/tests/unit/adapters/test_datameet_station_adapter.py`.
   - Verify full 8,990 feature reconciliation test.
4. **Step 4: Synthetic Identifier Hygiene in Existing Domain Tests**:
   - Update synthetic tests in `test_bootstrap_fixture_domain.py` to use explicit synthetic train numbers (`SYN901`, `SYN902`) instead of real train numbers.
   - Run full test suite in Docker to verify zero regressions.

---

## 10. Working Tree Status

```text
$ git status --short
?? TW103A_COMPLETION_REPORT.md
?? TW103B_IMPLEMENTATION_PLAN.md
?? TW103_REVISED_DATA_FOUNDATION_REPORT.md
?? backend/app/infrastructure/data/
?? backend/tests/unit/domain/test_bootstrap_fixture_domain.py
```

### Strict Observance:
- Zero implementation files created.
- Zero database changes or migrations.
- Zero remote data fetched.
- Zero files staged or committed.

*TW-103B architectural refinement complete. Awaiting CTO authorization to begin implementation.*
