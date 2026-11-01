# TW-103C — IMPLEMENTATION PLAN
## Railway Source Adapters — DataMeet Train Source Adapter

**Milestone**: TW-103C  
**Role**: Senior Backend Architect & Engineer  
**Status**: PLANNING & ARCHITECTURAL SPECIFICATION (PHASE 1 ONLY)  
**Deliverable**: `TW103C_IMPLEMENTATION_PLAN.md`  

---

## 1. Executive Summary & Ticket Boundaries

### 1.1 Objective
Design and specify a dedicated, high-throughput source adapter for the DataMeet Railways `trains.json` dataset (`DataMeetTrainAdapter`), establishing a clean, immutable bridge between raw source GeoJSON features and TripWiser's backend architecture.

### 1.2 Strict Ticket Boundaries (Planning Phase)
In accordance with instructions:
- **No implementation code** is written in this phase.
- **No domain models** (`Train`, `TrainScheduleEntry`, `Station`) are modified or weakened.
- **No missing running days** or schedule details are invented.
- **No database schemas, ORM models, or migrations** are touched.
- **No database writes** are performed.
- **No modifications** to TW-103A or TW-103B deliverables.
- **No git staging or commits** will take place until the plan is reviewed and authorized by the CTO.

---

## 2. Source Dataset Assessment (`trains.json`)

### 2.1 File Metrics & Cryptographic Provenance
- **Source Repository**: `https://github.com/datameet/railways`
- **Source File**: `trains.json` (local snapshot baseline)
- **Local Path**: `backend/app/infrastructure/data/sources/datameet/trains.json`
- **File Size**: `14,768,598 bytes` (~14.77 MB)
- **File SHA-256**: `e434d9c56016ccdf2291ccd446586ef87a7fab101084efa5f68871ab27800167`
- **Declared Licence**: **CC0 1.0 Universal** (Upstream DataMeet Railways README)
- **Licence Qualification**: *Underlying data provenance has not been independently audited.*

### 2.2 GeoJSON Schema Inventory
The dataset is structured as an RFC 7946 GeoJSON `FeatureCollection` containing **5,208 features**:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[lon, lat], [lon, lat], ...]
      },
      "properties": {
        "number": "04601",
        "name": "Jammu Tawi Udhampur Special",
        "type": "DEMU",
        "zone": "NR",
        "from_station_code": "JAT",
        "from_station_name": "JAMMU TAWI",
        "to_station_code": "UHP",
        "to_station_name": "UDHAMPUR",
        "departure": "10:40:00",
        "arrival": "12:15:00",
        "duration_h": 1,
        "duration_m": 35,
        "distance": 53,
        "return_train": "04602",
        "sleeper": 0,
        "third_ac": 0,
        "second_ac": 0,
        "first_ac": 0,
        "first_class": 0,
        "chair_car": 0,
        "classes": ""
      }
    }
  ]
}
```

### 2.3 Forensic Dataset Analysis (5,208 Total Features)

A comprehensive automated inspection of all 5,208 features revealed the following exact metrics:

1. **Train Numbers (`number`)**:
   - Total features: **5,208**
   - Unique train numbers: **5,208**
   - Missing/empty train numbers: **0**
   - Duplicate train numbers: **0**
   - String format: String preservation is vital (e.g. `"04601"` has leading zeroes representing special/holiday services).
2. **Train Names (`name`)**:
   - Missing/empty train names: **1** (Feature index 4918: Train number `"06345"`, from `"POY"` to `"PGTN"`, name is empty string `""`).
   - Valid train names: **5,207** (includes suffixes such as `"(Starts 5 April)"`, `"SF Special"`, which must be preserved as-is).
3. **Endpoint Stations (`from_station_code`, `to_station_code`)**:
   - Missing endpoint codes: **0**
   - Identical endpoints (`from_station_code == to_station_code`): **0**
   - Cross-referencing against DataMeet `stations.json` (8,990 stations):
     - All 5,208 origin codes and 5,208 destination codes exist in DataMeet `stations.json`.
   - Cross-referencing against TW-103B Accepted Stations (8,697 geocoded stations):
     - **5,176 trains** originate and terminate at valid, geocoded stations.
     - **32 trains** originate or terminate at one of the 11 unlocated/null-geometry stations quarantined in TW-103B (`CRND`, `TTP`, `BDRN`, `MKRL`, `LKKA`, `RGV`, `ARVI`, `JMB`, `LFG`, `UMPD`, `MGR`).
4. **Timing & Distance Anomaly Group**:
   - Exactly **15 features** contain missing operational metrics:
     - `departure`: `""` / `None`
     - `arrival`: `""` / `None`
     - `distance`: `-1`
     - `duration_h`: `-1`
     - `duration_m`: `-1`
     - `type`: `""`
     - `zone`: `""`
     *(Features: 24041, 12374, 12373, 13258, 13257, 57326, 57325, 12163, 12164, 12735, 12736, 12889, 12890, 56100, 56101).*
5. **Geometry Inspection (`LineString`)**:
   - All 5,208 geometries have type `"LineString"`.
   - **9 features** have degenerate LineStrings containing only 1 coordinate position (violating RFC 7946 Section 3.1.4 requiring $\ge 2$ positions).
   - All 9 degenerate LineString features belong to the 32 unlocated station trains where one endpoint lacked station coordinates.
   - Coordinate count range: Minimum = 1, Maximum = 684, Average = 79.57.
   - *Nature of geometry*: LineStrings are synthetic straight lines between mapped stations, **not physical surveyed railway tracks**.

---

## 3. Core Architectural Decisions & Domain Boundaries

### 3.1 Domain Model Isolation (Why `Train` Domain Model Cannot Be Instantiated Directly)
TripWiser's committed `Train` domain model in [`app/domain/models/train.py`](file:///c:/projects/tripwiser/backend/app/domain/models/train.py) represents a fully resolved operational passenger timetable:
```python
class Train(BaseModel):
    number: str
    name: str
    origin_code: str
    destination_code: str
    runs_on_days: list[int]          # Required: min 1 day, values 0..6
    schedule: list[TrainScheduleEntry]  # Required: min 1 stop, stop_sequence monotonic
```

**Critical Boundary Finding**:
1. DataMeet `trains.json` **completely lacks running days (`runs_on_days`)**.
2. DataMeet `trains.json` **completely lacks intermediate halts, halt times, and stop sequences**.
3. In strict compliance with ticket constraints:
   - *"Do not invent missing running days."*
   - *"Do not invent schedule details, distances or station relationships."*
4. Therefore, **`DataMeetTrainAdapter` must NOT instantiate the `Train` domain model directly**, as doing so would require inventing fake running days (e.g. `[0,1,2,3,4,5,6]`) and synthetic schedule entries.
5. Instead, the adapter will produce an immutable adapter-level entity: **`DataMeetTrainRecord`**, which faithfully captures the route metadata, coach classes, endpoint timing, and physical distance as declared by the source. Downstream timetable ingestion (TW-103D) will join these train route headers with verified operational timetable schedules.

### 3.2 Station Reference Validation Mode
The adapter will provide flexible, clean validation:
- `adapt(file_path, valid_station_codes=None)`:
  - If `valid_station_codes` is provided (e.g. the 8,697 accepted station codes from TW-103B):
    Trains with unlocated endpoints (the 32 affected trains) are quarantined with `UNRESOLVED_ORIGIN_STATION` or `UNRESOLVED_DESTINATION_STATION`.
  - If `valid_station_codes` is omitted (`None`):
    The adapter evaluates internal syntactic and structural validity of the train records.

---

## 4. Proposed Adapter Contract & Data Structures

Following the TW-103B architecture, all models will be `@dataclass(frozen=True)` and enforce genuine immutability at construction time via `__post_init__()` and `_normalize_to_tuple()`.

### 4.1 File Layout
```text
backend/app/infrastructure/
├── adapters/
│   ├── __init__.py
│   ├── exceptions.py             # Existing exceptions + Train-specific adapter errors
│   └── datameet/
│       ├── __init__.py           # Exports Station and Train adapters & models
│       ├── models.py             # Station models + shared helpers (_normalize_to_tuple, freeze_payload)
│       ├── station_adapter.py    # TW-103B Station adapter
│       ├── train_models.py       # DataMeetTrainRecord, AcceptedTrainRecord, TrainQuarantineRecord, TrainAdapterResult
│       └── train_adapter.py      # DataMeetTrainAdapter implementation
├── data/
│   └── sources/
│       └── datameet/
│           ├── stations.json     # TW-103B baseline snapshot (1,864,683 bytes)
│           └── trains.json       # TW-103C baseline snapshot (14,768,598 bytes)
```

### 4.2 Data Model Definitions (`train_models.py`)

```python
from dataclasses import dataclass, field
import datetime
from types import MappingProxyType
from typing import Any, Mapping

from app.infrastructure.adapters.datameet.models import (
    SourceProvenance,
    freeze_payload,
    _normalize_to_tuple,
)


@dataclass(frozen=True)
class DataMeetTrainRecord:
    """
    Immutable representation of an adapted DataMeet railway train route header.
    Preserves exact source strings, coach flags, endpoints, and synthetic route points.
    """
    number: str
    name: str
    origin_code: str
    destination_code: str
    origin_name: str | None
    destination_name: str | None
    train_type: str | None
    zone: str | None
    departure_time: datetime.time | None
    arrival_time: datetime.time | None
    duration_hours: int | None
    duration_minutes: int | None
    distance_km: float | None
    return_train_number: str | None
    has_sleeper: bool
    has_third_ac: bool
    has_second_ac: bool
    has_first_ac: bool
    has_first_class: bool
    has_chair_car: bool
    classes_raw: str | None
    route_geometry_coordinates: tuple[tuple[float, float], ...]  # (lon, lat) sequence


@dataclass(frozen=True)
class AcceptedTrainRecord:
    """Audit record pairing adapted DataMeetTrainRecord with source index and frozen payload."""
    train: DataMeetTrainRecord
    source_record_index: int
    original_train_number: str
    raw_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_payload", freeze_payload(self.raw_payload))


@dataclass(frozen=True)
class TrainQuarantineRecord:
    """Represents a rejected train record, its validation rejection codes, and raw payload."""
    source_file: str
    source_record_index: int
    original_train_number: str | None
    original_train_name: str | None
    rejection_codes: tuple[str, ...]
    validation_messages: tuple[str, ...]
    raw_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rejection_codes",
            _normalize_to_tuple(self.rejection_codes, "rejection_codes"),
        )
        object.__setattr__(
            self,
            "validation_messages",
            _normalize_to_tuple(self.validation_messages, "validation_messages"),
        )
        object.__setattr__(self, "raw_payload", freeze_payload(self.raw_payload))


@dataclass(frozen=True)
class TrainAdapterResult:
    """Complete immutable result of a DataMeet train adapter execution."""
    records: tuple[DataMeetTrainRecord, ...]
    accepted: tuple[AcceptedTrainRecord, ...]
    quarantined: tuple[TrainQuarantineRecord, ...]
    provenance: SourceProvenance

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", _normalize_to_tuple(self.records, "records"))
        object.__setattr__(self, "accepted", _normalize_to_tuple(self.accepted, "accepted"))
        object.__setattr__(self, "quarantined", _normalize_to_tuple(self.quarantined, "quarantined"))
```

---

## 5. Validation and Quarantine Rules

Each feature in `trains.json` will be evaluated against strict multi-rule validation:

| Rule Category | Rejection Code | Trigger Condition |
| :--- | :--- | :--- |
| **Feature Structure** | `MALFORMED_FEATURE_OBJECT` | Feature element is not a JSON dictionary |
| | `NOT_FEATURE_TYPE` | Feature `type != "Feature"` |
| | `MISSING_PROPERTIES` | Feature is missing the `properties` attribute |
| | `MALFORMED_PROPERTIES_OBJECT` | Feature `properties` is not a dictionary |
| **Train Number** | `MISSING_TRAIN_NUMBER` | `properties.number` is null, empty string, or whitespace-only |
| | `DUPLICATE_TRAIN_NUMBER` | Train number occurs more than once; all instances collectively quarantined |
| **Train Name** | `MISSING_TRAIN_NAME` | `properties.name` is null, empty string, or whitespace-only |
| **Endpoints** | `MISSING_ORIGIN_STATION_CODE` | `properties.from_station_code` is missing or empty |
| | `MISSING_DESTINATION_STATION_CODE` | `properties.to_station_code` is missing or empty |
| | `IDENTICAL_ENDPOINT_STATIONS` | Origin code equals destination code |
| | `UNRESOLVED_ORIGIN_STATION` | Origin code is not in `valid_station_codes` (when foundation filter provided) |
| | `UNRESOLVED_DESTINATION_STATION` | Destination code is not in `valid_station_codes` (when foundation filter provided) |
| **Timing & Distance** | `INVALID_DEPARTURE_TIME` | `departure` is missing/empty or fails `HH:MM:SS` parsing |
| | `INVALID_ARRIVAL_TIME` | `arrival` is missing/empty or fails `HH:MM:SS` parsing |
| | `NEGATIVE_DISTANCE` | `distance < 0.0` (e.g. `-1` sentinel values) |
| | `INVALID_DURATION` | `duration_h < 0` or `duration_m < 0` or `duration_m >= 60` |
| **Geometry** | `MISSING_GEOMETRY` | Feature `geometry` attribute is missing or null |
| | `MALFORMED_GEOMETRY_OBJECT` | Feature `geometry` is not a dictionary |
| | `NOT_LINESTRING_GEOMETRY` | Geometry `type != "LineString"` |
| | `DEGENERATE_LINESTRING` | Geometry `coordinates` array length $< 2$ |
| | `INVALID_COORDINATE_FORMAT` | Coordinates are not numeric, non-finite, or out of lat/lon bounds |

---

## 6. Exact Dataset Reconciliation Projection

When `DataMeetTrainAdapter` processes the Local DataMeet baseline snapshot `trains.json` (`14,768,598 bytes`, 5,208 features):

### Scenario A: Standalone Structural Validation (Without Station Filter)
```text
Total Source Records:             5,208
Accepted Train Records:           5,192
Unique Quarantined Records:          16
  - MISSING_TRAIN_NAME:               1 (Train 06345, POY -> PGTN)
  - TIMING/DISTANCE SENTINEL:        15 (Negative distance, missing times)
```

### Scenario B: Fully Connected Foundation Validation (Using TW-103B Accepted Stations)
When validating endpoint references against the 8,697 geocoded stations from TW-103B:
```text
Total Source Records:             5,208
Accepted Train Records:           5,176 (100% connected to verified geocoded stations)
Accepted Audit Records:           5,176 (1-to-1 mapped with source payloads)
Unique Quarantined Records:          48
Total Failure Instances:             72 (due to multi-failure overlap: unlocated + degenerate line)

Quarantine Breakdown (48 unique records):
  - UNRESOLVED_ORIGIN_STATION:       16 (originates at null-geometry station)
  - UNRESOLVED_DESTINATION_STATION:  16 (terminates at null-geometry station)
  - DEGENERATE_LINESTRING:            9 (1-point route line, overlaps with unlocated endpoints)
  - TIMING/DISTANCE SENTINEL:        15 (negative distance / missing departure-arrival)
  - MISSING_TRAIN_NAME:               1 (Train 06345)
----------------------------------------------------------------------------------------
Exact Reconciliation: 5,208 = 5,176 (Accepted) + 48 (Unique Quarantined)
```

---

## 7. Test Plan

A dedicated test suite `backend/tests/unit/adapters/test_datameet_train_adapter.py` will be created covering:

1. **Structural & Positive Tests**:
   - Parses a valid Feature into `DataMeetTrainRecord`.
   - String preservation for leading zeroes (`"04601"`).
   - Preserves original names with special characters and parenthetical suffixes.
   - Converts boolean coach flags (`1` $\to$ `True`, `0` $\to$ `False`).
   - Parses valid `HH:MM:SS` strings into `datetime.time` objects.
2. **Quarantine & Negative Tests**:
   - Missing or empty train number (`MISSING_TRAIN_NUMBER`).
   - Missing or empty train name (`MISSING_TRAIN_NAME`).
   - Missing origin or destination station code.
   - Identical origin and destination codes (`IDENTICAL_ENDPOINT_STATIONS`).
   - Negative distance values (`NEGATIVE_DISTANCE`).
   - Missing or invalid arrival/departure times (`INVALID_ARRIVAL_TIME`, `INVALID_DEPARTURE_TIME`).
   - Non-LineString geometry or degenerate LineString with $< 2$ points (`DEGENERATE_LINESTRING`).
   - Collective duplicate train number quarantine (synthetic multi-record test).
3. **Station Foundation Integration Tests**:
   - Train with valid endpoints accepted.
   - Train with unlocated origin quarantined (`UNRESOLVED_ORIGIN_STATION`).
   - Train with unlocated destination quarantined (`UNRESOLVED_DESTINATION_STATION`).
   - Combined failure (unresolved endpoint + degenerate LineString) records both rejection codes.
4. **Immutability & Audit Tests**:
   - `AcceptedTrainRecord.raw_payload` survives with un-truncated source properties.
   - Direct construction freezes nested mappings (`MappingProxyType`) and sequences (`tuple`).
   - `collections.deque` inputs normalized cleanly to `tuple`.
   - Attempted mutations raise `FrozenInstanceError` or `TypeError`.
5. **Full Baseline Reconciliation Audit**:
   - Executes against the complete local baseline `trains.json`.
   - Asserts exact reconciliation: $5,208 = 5,176 \text{ accepted} + 48 \text{ quarantined}$.
   - Asserts zero duplicate train numbers among accepted records.

---

## 8. Risks, Assumptions & Unresolved Questions

1. **No Operational Timetables**:
   - `trains.json` is strictly a *route index*. It cannot substitute for a timetable.
   - Attempting to construct search itineraries or intermediate stop availability directly from `trains.json` is impossible.
   - It will serve as an authoritative train registry/header catalogue to be merged with timetable data in TW-103D.
2. **LineString Route Geometries**:
   - Route geometries are simple station-to-station connecting vectors.
   - They must not be presented to users as surveyed GPS track data or used to calculate curvature/gradient.
3. **Historical Train Numbers**:
   - DataMeet includes special trains with 5-digit numbers starting with `"0"` (e.g. `"04601"`).
   - Upstream IRCTC/NTES renumbers special trains periodically. The adapter must preserve the exact string from the source snapshot without numeric coercion.

---

*Planning specification complete. Standing by for CTO review and authorization.*

