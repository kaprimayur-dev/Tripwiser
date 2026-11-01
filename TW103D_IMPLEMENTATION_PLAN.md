# TW-103D — IMPLEMENTATION PLAN
## Railway Source Adapters — DataMeet Schedule Source Adapter

**Milestone**: TW-103D  
**Role**: Senior Backend Architect & Engineer  
**Status**: PLANNING & ARCHITECTURAL SPECIFICATION (PHASE 1 ONLY)  
**Deliverable**: `TW103D_IMPLEMENTATION_PLAN.md`  

---

## 1. Executive Summary & Ticket Boundaries

### 1.1 Objective
Design and specify a dedicated, high-throughput source adapter for the DataMeet Railways `schedules.json` dataset (`DataMeetScheduleAdapter`), establishing a clean, immutable bridge between raw source schedule entries and TripWiser's backend architecture.

### 1.2 Strict Ticket Boundaries (Planning Phase)
In strict accordance with project directives:
- **No implementation code** is written in this milestone planning phase.
- **No domain models** (`Train`, `TrainScheduleEntry`, `Station`, `CandidateRoute`, `JourneyLeg`) are modified or weakened.
- **No missing railway data** (running days, intermediate distances, or stop timings) is invented or synthetically guessed.
- **No database schemas, ORM models, or migrations** are touched or executed.
- **No database writes** are performed.
- **No modifications** to committed TW-103A, TW-103B, or TW-103C deliverables.
- **No git staging or commits** will take place until the plan is reviewed and authorized by the CTO.

---

## 2. Source Dataset Forensics (`schedules.json`)

### 2.1 File Metrics & Cryptographic Provenance
- **Source Repository**: `https://github.com/datameet/railways`
- **Source File**: `schedules.json` (Local DataMeet baseline snapshot)
- **Local Path**: `backend/app/infrastructure/data/sources/datameet/schedules.json`
- **File Size**: `82,174,280 bytes` (~78.37 MB)
- **File SHA-256**: `105d63816acb177eac30a7d156eb2d312625a42ddebd273edee810d2989878ec`
- **Declared Licence**: **CC0 1.0 Universal** (Upstream DataMeet Railways README)
- **Licence Qualification**: *Underlying data provenance has not been independently audited.*

### 2.2 Raw Data Structure
Unlike `stations.json` and `trains.json` (which are RFC 7946 GeoJSON `FeatureCollection`s), `schedules.json` is a flat top-level JSON array containing **417,080 dictionary elements**:

```json
[
  {
    "id": 269390,
    "train_number": "12951",
    "train_name": "Mumbai Rajdhani Express",
    "station_code": "BCT",
    "station_name": "MUMBAI CENTRAL",
    "arrival": "None",
    "departure": "16:40:00",
    "day": 1
  },
  {
    "id": 269391,
    "train_number": "12951",
    "train_name": "Mumbai Rajdhani Express",
    "station_code": "MX",
    "station_name": "MAHALAKSHMI",
    "arrival": "16:41:00",
    "departure": "16:41:00",
    "day": 1
  }
]
```

### 2.3 Forensic Dataset Analysis (417,080 Total Records)

A complete automated inspection across all 417,080 records revealed the following exact metrics:

1. **Record Completeness & Schema Integrity**:
   - `id`: **417,080 / 417,080** present, integer, **0 nulls**, **0 duplicates**. Every record possesses a globally unique integer ID.
   - `train_number`: **417,080 / 417,080** present, string, **0 nulls**, **0 empty strings**. Preserves leading zeroes (e.g. `"04601"`).
   - `station_code`: **417,080 / 417,080** present, string, **0 nulls**, **0 empty strings**.
   - `train_name`: 417,072 valid strings, **8 empty strings**.
   - `station_name`: 417,078 valid strings, **2 empty strings**.

2. **Arrival & Departure Time Forensics**:
   - **Time String Parse Errors**: Exactly **0**. Every non-null time string strictly conforms to `HH:MM:SS`.
   - `arrival: "None"` and `departure: "None"` (Both None): **22,689 records**.
     - These represent unpopulated schedule placeholders (e.g. Train `"12412"` Amritsar-Chandigarh Intercity, Train `"12584"` Double Decker).
     - 17 trains have **all stops** with both arrival and departure set to `"None"`.
   - `arrival: "None"` with valid `departure`: **5,146 records** (Represents origin terminus departure).
   - `departure: "None"` with valid `arrival`: **5,138 records** (Represents destination terminus arrival).
   - **Both Times Present**: **384,107 records** (92.09% of dataset).
     - **Waypoints / Pass-Through Stations (`arrival == departure`)**: **290,315 records** (69.61% of total dataset). These represent track sensor points or non-commercial waypoints spaced 1 minute apart (e.g. suburban stations along the Rajdhani route).
     - **Commercial Passenger Halts (`arrival != departure`)**: **93,792 records** (22.49% of total dataset).

3. **Day Field Distribution & Anomalies**:
   - `day = 1`: 183,993 records
   - `day = 2`: 174,878 records
   - `day = 3`: 32,888 records
   - `day = 4`: 2,591 records
   - `day = 5`: 124 records
   - `day = 6`: 4 records
   - `day is None`: **22,561 records** (100% overlap with the `both_none` timing placeholder group).
   - `day >= 7` (Suspicious Corrupted Rollovers): **41 records** (Values: 7, 8, 9, 10, 11, 12, 13).
     - Found in local passenger services (e.g., Train `"53017"` Katwa-Azimganj Passenger, Train `"41112"` Velachery-Chennai Beach suburban local), where upstream scrapers improperly incremented the day counter during technical midnight transitions.

4. **Distance Field Absence**:
   - The field `distance` is **completely absent from `schedules.json`**. Not a single record contains distance or kilometer progression.

---

## 3. Stop Ordering and Sequence Reconstruction

### 3.1 Interleaved File Storage
Stops in `schedules.json` are **not stored contiguously** by train. In the raw JSON, stop #1 of many trains appears near the beginning, followed by stop #2, and so forth. Exactly **0 trains appear as contiguous blocks** in the raw file.

### 3.2 Monotonic ID Sequencing
Inspection of the `id` field proves that the original DataMeet extraction assigned sequentially increasing integer IDs along the route of each train:
- **5,022 trains (96.43%)** have **strictly consecutive** IDs ($id_{i+1} = id_i + 1$).
- **186 trains (3.57%)** have small non-consecutive ID gaps, but their IDs remain **strictly monotonically increasing**.
- **0 trains** have duplicate IDs or ID order inversions.

### 3.3 Terminus Validation
Sorting a train's stop records by `id` ascending perfectly reconstructs the physical journey order:
- **Origin Terminus**: In **5,174 trains (99.35%)**, the stop with the lowest `id` has `arrival: "None"`, identifying it as the journey starting point.
- **Destination Terminus**: In **5,164 trains (99.15%)**, the stop with the highest `id` has `departure: "None"`, identifying it as the journey termination point.

**Deterministic Sequencing Rule & Terminology**:
Sorting stops by `id` ascending and assigning 1-based ordinal integers ($1, 2, \dots, N$) produces the adapter's reconstructed `stop_sequence`.
- **Crucial Distinction**: `stop_sequence` is the adapter's deterministic reconstruction based on source database insertion order. It is **not** proof of official Indian Railways operating timetable sequence.
- **Chronological Inversions**: In 352 trains, chronological inversions occur along the ID sequence (due to missing day rollover increments in the source).
- **Rule**: Records must **not** be reordered by timestamps; inversions are preserved in source-reconstructed order and reported via `CHRONOLOGICAL_INVERSION`. Reordering by timestamps would scramble physical track topology.

---

## 4. Cross-Reference Resolution with TW-103B & TW-103C

### 4.1 Station Reference Resolution (Against TW-103B)
- **Unique station codes in `schedules.json`**: **8,539**
- **Match against raw DataMeet `stations.json` (8,990 stations)**: **8,539 / 8,539 (100%)**. Zero station codes are unknown to DataMeet.
- **Match against TW-103B Geocoded Stations (8,697 accepted stations)**:
  - **414,420 stop records (99.36%)** resolve to verified geocoded stations.
  - **2,660 stop records (0.64%)** reference one of the 292 unlocated/null-geometry stations quarantined in TW-103B.
  - **1,354 trains (26.00%)** pass through at least one unlocated station.

### 4.2 Train Reference Resolution (Against TW-103C)
- **Unique train numbers in `schedules.json`**: **5,208**
- **Match against DataMeet `trains.json` (5,208 trains)**: **5,208 / 5,208 (100%)**. Exact 1-to-1 parity.
- **Match against TW-103C Accepted Trains (5,175 accepted trains)**:
  - **416,669 stop records (99.90%)** belong to accepted trains.
  - **411 stop records (0.10%)** belong to the 33 quarantined trains from TW-103C.

### 4.3 Endpoint Alignment with `trains.json`
Comparing the first and last stops (by `id`) against `from_station_code` and `to_station_code` in `trains.json`:
- **Origin Matches**: **5,203 / 5,208 trains (99.90%)**. Exactly 5 mismatch (e.g. Train 55034 GD vs SPC, Train 18190 ROU vs ALLP).
- **Destination Matches**: **5,192 / 5,208 trains (99.69%)**. Exactly 16 mismatch (e.g. Train 15934 DBRT vs DBRG, Train 53647 TRG vs NXR).

---

## 5. Domain Model & Database Schema Alignment

### 5.1 Comparison with `TrainScheduleEntry` Domain Model
[`backend/app/domain/models/train.py`](file:///c:/projects/tripwiser/backend/app/domain/models/train.py):
```python
class TrainScheduleEntry(BaseModel):
    station_code: str
    arrival_time: Optional[datetime.time] = None
    departure_time: Optional[datetime.time] = None
    day_offset: int = Field(0, ge=0)
    distance_km: float = Field(0.0, ge=0.0)
    stop_sequence: int = Field(..., ge=1)
```

| Domain Field | `schedules.json` Source Availability | Alignment Strategy |
| :--- | :--- | :--- |
| `station_code` | `station_code` present in 100% of records | Direct mapping (upper case stripped). |
| `arrival_time` | `arrival` is `HH:MM:SS` or `"None"` | Parsed to `datetime.time` or `None`. |
| `departure_time` | `departure` is `HH:MM:SS` or `"None"` | Parsed to `datetime.time` or `None`. |
| `day_offset` | `day` is 1-indexed (1, 2, 3...) or `None` | `day_offset = (day - 1) if day else 0`. If `day is None`, flag warning. |
| `distance_km` | **Completely Absent** in source | Set to `0.0` or `None` in adapter; do not invent fake distances. |
| `stop_sequence` | Implicit via monotonic `id` ordering | Reconstructed as ordinal $1 \dots N$ by sorting on `id`. |

### 5.2 Comparison with `Train` Domain Model
The `Train` model requires:
1. `runs_on_days: list[int]` (0 to 6) — **Completely absent in DataMeet**.
2. Complete schedule matching `origin_code` and `destination_code`.

**Architectural Consequence**:  
Just as in TW-103C, **`DataMeetScheduleAdapter` must NOT attempt to directly instantiate `Train` domain entities**, as doing so would require inventing running days and fabricating missing intermediate distances.  
Instead, the adapter will produce an immutable adapter entity: **`DataMeetTrainSchedule`** (containing `DataMeetScheduleEntry` objects), ready for authoritative timetable merging in downstream milestone TW-103E.

### 5.3 Comparison with Database Schema (`ScheduleORM`)
[`backend/app/infrastructure/database/models/train.py`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/models/train.py):
- Table `train_schedules` enforces `UniqueConstraint("train_number", "stop_sequence", name="uq_train_stop_sequence")`.
- Repeated Station Codes: **465 trains** call at the same station more than once (e.g. circle routes, reversal junctions). Because `stop_sequence` is unique and monotonic, repeated stations are valid and supported by the schema.

---

## 6. Proposed Adapter Contract & Data Structures

All models will be `@dataclass(frozen=True)` and enforce genuine construction-time immutability via `freeze_payload` and `_normalize_to_tuple`.

### 6.1 Proposed File Layout
```text
backend/app/infrastructure/
├── adapters/
│   ├── datameet/
│   │   ├── __init__.py           # Exports Station, Train, and Schedule adapters & models
│   │   ├── models.py             # Station models + shared immutability helpers
│   │   ├── train_models.py       # TW-103C Train models
│   │   ├── train_adapter.py      # TW-103C Train adapter
│   │   ├── schedule_models.py    # TW-103D Schedule models
│   │   └── schedule_adapter.py   # TW-103D Schedule adapter implementation
├── data/
│   └── sources/
│       └── datameet/
│           ├── stations.json     # TW-103B baseline (1.86 MB)
│           ├── trains.json       # TW-103C baseline (14.77 MB)
│           └── schedules.json    # TW-103D baseline (82.17 MB)
```

### 6.2 Data Model Definitions (`schedule_models.py`)

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
class DataMeetScheduleEntry:
    """
    Immutable representation of an adapted DataMeet railway schedule stop/waypoint.
    Preserves exact timing, reconstructed 1-based stop sequence, and waypoint classification.
    """
    source_record_id: int
    train_number: str
    station_code: str
    station_name: str | None
    stop_sequence: int
    arrival_time: datetime.time | None
    departure_time: datetime.time | None
    day: int | None
    day_offset: int
    is_commercial_halt: bool
    is_waypoint: bool
    distance_km: float | None = None
    validation_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "validation_warnings",
            _normalize_to_tuple(self.validation_warnings, "validation_warnings"),
        )


@dataclass(frozen=True)
class DataMeetTrainSchedule:
    """
    Immutable representation of a train's complete schedule, grouping and sequencing its stops.
    """
    train_number: str
    train_name: str | None
    origin_code: str
    destination_code: str
    total_stops: int
    entries: tuple[DataMeetScheduleEntry, ...]
    schedule_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", _normalize_to_tuple(self.entries, "entries"))
        object.__setattr__(
            self,
            "schedule_warnings",
            _normalize_to_tuple(self.schedule_warnings, "schedule_warnings"),
        )


@dataclass(frozen=True)
class AcceptedScheduleRecord:
    """Audit record pairing adapted DataMeetScheduleEntry with source index and frozen payload."""
    entry: DataMeetScheduleEntry
    source_record_index: int
    original_train_number: str
    original_station_code: str
    raw_payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_payload", freeze_payload(self.raw_payload))


@dataclass(frozen=True)
class ScheduleQuarantineRecord:
    """Represents a rejected schedule stop record and its diagnostic failure metadata."""
    source_file: str
    source_record_index: int
    source_record_id: int | None
    original_train_number: str | None
    original_station_code: str | None
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
class ScheduleAdapterResult:
    """Complete immutable result of a DataMeet schedule adapter execution."""
    train_schedules: tuple[DataMeetTrainSchedule, ...]
    records: tuple[DataMeetScheduleEntry, ...]
    accepted: tuple[AcceptedScheduleRecord, ...]
    quarantined: tuple[ScheduleQuarantineRecord, ...]
    provenance: SourceProvenance

    def __post_init__(self) -> None:
        object.__setattr__(self, "train_schedules", _normalize_to_tuple(self.train_schedules, "train_schedules"))
        object.__setattr__(self, "records", _normalize_to_tuple(self.records, "records"))
        object.__setattr__(self, "accepted", _normalize_to_tuple(self.accepted, "accepted"))
        object.__setattr__(self, "quarantined", _normalize_to_tuple(self.quarantined, "quarantined"))
```

---

## 7. Validation and Quarantine Rules

Following the principles established in the CTO's architecture corrections, the adapter preserves useful station topology even when commercial timing information is unavailable:

| Category | Rejection / Warning Code | Trigger Condition | Outcome |
| :--- | :--- | :--- | :--- |
| **Record Structure** | `MALFORMED_RECORD_OBJECT` | Record is not a dictionary | Quarantine |
| | `MISSING_RECORD_ID` | `id` field is missing or non-integer | Quarantine |
| **Required Keys** | `MISSING_TRAIN_NUMBER` | `train_number` is missing, null, or empty string | Quarantine |
| | `MISSING_STATION_CODE` | `station_code` is missing, null, or empty string | Quarantine |
| **Reference Validation** | `UNRESOLVED_TRAIN_REFERENCE` | `train_number` not in `valid_train_numbers` (when train filter provided) | Quarantine |
| | `UNRESOLVED_STATION_REFERENCE` | `station_code` not in `valid_station_codes` (when station filter provided) | Quarantine |
| **Timing & Day Warnings** | `INCOMPLETE_TIMING_INFO` | Record has `arrival == "None"` and `departure == "None"` (22,689 records) | **Accept (Incomplete)** |
| (Non-Quarantining) | `MISSING_DAY_FIELD` | `day` is None (defaults `day_offset = 0`) (22,561 records) | **Accept with Warning** |
| | `SUSPICIOUS_DAY_VALUE` | `day > 6` (values 7..13 in 41 records across 4 trains) | **Accept with Warning** |
| | `WAYPOINT_PASS_THROUGH` | `arrival == departure` (290,315 records) | **Accept with Warning** |
| | `TERMINUS_TIME_OMITTED` | First stop missing departure or last stop missing arrival | **Accept with Warning** |
| | `REPEATED_STATION_IN_ROUTE` | Train calls at same station more than once (465 trains) | **Accept with Warning** |
| | `ORIGIN_STATION_MISMATCH` | First stop station != `trains.json` `from_station_code` (5 trains) | **Accept with Warning** |
| | `DESTINATION_STATION_MISMATCH` | Last stop station != `trains.json` `to_station_code` (16 trains) | **Accept with Warning** |
| | `CHRONOLOGICAL_INVERSION` | Backward timestamp jump along route sequence (352 trains) | **Accept with Warning** |
| | `MISSING_DISTANCE` | Intermediate distance is absent in source (417,080 records) | **Accept with Warning** |

---

## 8. Exact Reconciliation Projection

When `DataMeetScheduleAdapter` processes the Local DataMeet baseline snapshot `schedules.json` (`82,174,280 bytes`, 417,080 records):

### 8.1 Standalone Structural Mode (No External Foundation Filters)
In standalone mode, evaluating intrinsic record validity without external filters:
```text
Total Source Records:                                            417,080 (100.00%)
Accepted Complete Records (Valid timing & identifiers):          394,391  (94.56%)
Accepted Incomplete Records (Both times None, topology preserved):22,689   (5.44%)
----------------------------------------------------------------------------------
Total Accepted Records:                                          417,080 (100.00%)
Quarantined Records (Missing required keys):                           0   (0.00%)
----------------------------------------------------------------------------------
Exact Reconciliation: 417,080 (Accepted) + 0 (Quarantined) =     417,080 (100.00%)
```

### 8.2 Foundation-Integrated Mode (Using TW-103B Stations & TW-103C Trains)
When validating against the **8,697 geocoded stations** (TW-103B) and **5,175 accepted trains** (TW-103C), each record is partitioned into exactly one mutually exclusive category (see [`TW103D_FORENSIC_ADDENDUM.md`](file:///c:/projects/tripwiser/TW103D_FORENSIC_ADDENDUM.md) for full breakdown):

```text
Total Source Records:                                            417,080 (100.00%)
Accepted Complete Records (Valid timing, geocoded station & train):392,420 (94.09%)
Accepted Incomplete Records (Both times None, geocoded & train):  21,756   (5.22%)
----------------------------------------------------------------------------------
TOTAL ACCEPTED RECORDS:                                          414,176  (99.30%)
----------------------------------------------------------------------------------
Quarantined: Unresolved Train Reference Only:                        244   (0.06%)
  (236 with timing + 8 both-none)
Quarantined: Unresolved Station Reference Only:                    2,493   (0.60%)
  (1,568 with timing + 925 both-none)
Quarantined: Unresolved Train & Station:                             167   (0.04%)
  (167 with timing + 0 both-none)
Quarantined: Missing Required Identifiers:                             0   (0.00%)
----------------------------------------------------------------------------------
TOTAL QUARANTINED RECORDS:                                         2,904   (0.70%)
==================================================================================
Exact Reconciliation: 414,176 (Accepted) + 2,904 (Quarantined) = 417,080 (100.00%)
```

### 8.3 Independent Validation Warning Counts (Non-Additive)
```text
WAYPOINT_PASS_THROUGH (arrival == departure):                    290,315 records
INCOMPLETE_TIMING_INFO (arrival and departure both None):         22,689 records
MISSING_DAY_FIELD (day is None, defaulted to 0):                  22,561 records
REPEATED_STATION_IN_ROUTE (duplicate station calls):               1,017 instances (465 trains)
SUSPICIOUS_DAY_VALUE (day > 6 preserved as-is):                       41 records (4 trains)
ORIGIN_STATION_MISMATCH (first stop != trains.json from_code):        5 trains
DESTINATION_STATION_MISMATCH (last stop != trains.json to_code):      16 trains
CHRONOLOGICAL_INVERSION (backward time jump along route):            352 trains
MISSING_DISTANCE (intermediate distance absent in source):       417,080 records
```

---

## 9. Comprehensive Test Plan

A dedicated test suite `backend/tests/unit/adapters/test_datameet_schedule_adapter.py` will be created covering:

1. **File Handling & Parsing**:
   - `SourceFileNotFoundError`, `SourceIOError`, `SourceEncodingError`, `MalformedSourceError`.
   - Rejects non-array root payloads.
2. **Positive Parsing & Preservation**:
   - Parses valid schedule record into `DataMeetScheduleEntry`.
   - String preservation for leading zeroes in train numbers (`"04601"`).
   - Reconstructs 1-based monotonic `stop_sequence` from `id` ordering.
   - Distinguishes commercial halts (`arr != dep`) from waypoints (`arr == dep`).
   - Normalizes 1-indexed `day` to 0-indexed `day_offset`.
3. **Optional Field & Warning Tests**:
   - Origin departure-only (`arrival: "None"`) accepted.
   - Destination arrival-only (`departure: "None"`) accepted.
   - Preserves `distance_km = None` with warning (no synthetic distances invented).
   - Preserves high `day >= 7` with warning.
4. **Quarantine Tests**:
   - Missing or empty `train_number`.
   - Missing or empty `station_code`.
   - Empty/placeholder stop records (`both arrival and departure None`).
   - Unresolved station code against foundation set.
   - Unresolved train number against foundation set.
5. **Immutability & Audit**:
   - `AcceptedScheduleRecord.raw_payload` is frozen `MappingProxyType`.
   - Normalization of collections (`deque`, `list`, `set` $\to$ `tuple`).
   - Mutation attempts raise `FrozenInstanceError` or `TypeError`.
6. **Full Baseline Reconciliation Audit**:
   - Full execution against local snapshot `schedules.json` (417,080 records).
   - Asserts exact cryptographic checksum: `105d63816acb177eac30a7d156eb2d312625a42ddebd273edee810d2989878ec`.
   - Proves mathematical reconciliation without double-counting.

---

## 10. Risks, Assumptions & Recommendation for Downstream (TW-103E)

1. **Absence of Intermediate Distances**:
   - `schedules.json` does not provide distances between intermediate halts.
   - Downstream route distance calculations (e.g. fare computation in `CandidateRoute`) must rely on geocoded station coordinates or verified route tables (TW-103A).
2. **Absence of Running Days**:
   - Neither `trains.json` nor `schedules.json` contains running days.
   - Full instantiation of the `Train` domain entity must occur in **TW-103E**, where timetable schedules are merged with verified train reference data and running calendars.
3. **Waypoints vs Halts**:
   - 69.6% of records are track waypoints (`arrival == departure`). Downstream journey planning queries should filter for `is_commercial_halt == True` when presenting passenger boarding options.

---

*Planning specification complete. Standing by for CTO review and authorization.*

