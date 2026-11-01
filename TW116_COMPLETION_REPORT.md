# TW-116 Completion Report: Train Discovery & Passenger Intelligence

## Executive Summary
**Milestone:** TW-116 — Train Discovery & Passenger Intelligence  
**Role:** Lead Full-Stack Engineer  
**Status:** Completed & Fully Verified  
**Commit Message:** `feat(trains): implement passenger train discovery and comparison`  

TripWiser’s railway intelligence platform has been extended with a unified, passenger-first **Train Discovery & Comparison experience**. Passengers can now search any Indian Railways train, inspect its complete stoppage and timing sequence, discover all recorded trains calling at a selected station with deterministic operational role classification, and compare direct trains head-to-head with verified running days, durations, and stop counts.

All work conforms strictly to TripWiser's core data integrity principles:
- **No fabricated predictions:** Scheduled durations and intermediate stop counts are computed deterministically from compiled timetable timestamps and day offsets; missing timing fields return explicit `None`/`null` indicators rather than acting as midnight `00:00` or `0` minutes.
- **Canonical API endpoints:** `/api/v1/stations/{code}/trains` serves as the sole canonical endpoint for station-serving trains, avoiding route duplication.
- **Deterministic forward segments:** Multi-visit trains across a corridor are evaluated strictly for valid forward progressions (`origin.stop_sequence < destination.stop_sequence`) and deduplicated using canonical minimal sequence spans.
- **Database index efficiency:** Verified that existing B-Tree indexes (`idx_schedules_lookup`, `uq_train_stop_sequence`, `trains_pkey`) fully optimize all station-serving and direct-comparison joins (< 2ms query execution time), avoiding redundant indexes.

---

## 1. Capabilities Delivered

### A. Indexed Multi-Attribute Train Search
- Supports train number prefix matching (indexed), train name substring matching, origin/destination terminal codes, and intermediate calling stations via a correlated PostgreSQL `EXISTS` subquery.
- Pushes pagination and sorting down to the database, preventing full schedule loading into application memory.
- Clear empty state (`#train-search-empty-state`) with helpful search tips for invalid or unrecorded queries.

### B. Station-Serving Trains (`GET /api/v1/stations/{code}/trains`)
- Discovers all compiled trains recorded as calling, originating, or terminating at a selected railway station.
- Dynamically classifies each stoppage occurrence against each train's schedule boundaries:
  - `ORIGINATING`: `stop_sequence == min(stop_sequence)`
  - `TERMINATING`: `stop_sequence == max(stop_sequence)`
  - `EN_ROUTE`: `min_seq < stop_sequence < max_seq`
- Preserves repeated visits to the same station by a single train (e.g. loops or reversal junctions) with their respective sequence, arrival, departure, and day offsets.
- Sorts by scheduled departure/arrival time using `NULLS LAST` so unrecorded times are never falsely sorted as midnight.
- Derives operating frequency strictly from verified running calendars (`runs_on_days`), with provenance tier disclosures.

### C. Direct Train Comparison (`GET /api/v1/trains/compare`)
- Compares all direct railway services between any two selected stations.
- Strict forward sequence validation: only includes trains where `origin.stop_sequence < destination.stop_sequence`.
- Multi-visit corridor deduplication: selects the canonical forward segment with minimal stop span, tie-broken by earliest sequence.
- Mathematically rigorous duration:
  $$\text{scheduled\_duration\_minutes} = (\text{dest\_day\_offset} \times 1440 + \text{dest\_arrival\_minutes}) - (\text{orig\_day\_offset} \times 1440 + \text{orig\_departure\_minutes})$$
- Frontend interactive comparison controls: sortable by **Fastest**, **Earliest Departure**, or **Fewest Intermediate Stops**, with one-click navigation to inspect the complete stoppage timetable.

### D. Integrated Editorial Frontend
- Integrated mode switcher with **Compare Trains** (`compare`) in the top navigation bar.
- Station details view includes a dedicated `"Recorded Trains Serving This Station"` section with service type badges (`ORIGINATING`, `TERMINATING`, `EN_ROUTE`), arrival/departure times, and halt durations.
- Preserves the warm editorial transit journal visual design language (`#F4EFE4`, `#191612`, `#B9532D`, `#67664A`).

---

## 2. API Specifications

| Endpoint | Method | Purpose | Key Parameters / Response |
| :--- | :--- | :--- | :--- |
| `/api/v1/trains/search` | `GET` | Multi-field train lookup | `q={query}&limit={limit}` $\to$ `List[TrainSummarySchema]` |
| `/api/v1/stations/{code}/trains` | `GET` | Canonical station-serving trains | `code={stn_code}&limit={limit}` $\to$ `StationTrainsResponse` |
| `/api/v1/trains/compare` | `GET` | Head-to-head train comparison | `origin={code}&destination={code}` $\to$ `TrainComparisonResponse` |
| `/api/v1/trains/{train_number}/schedule` | `GET` | Full stoppage sequence & halts | `train_number={num}` $\to$ `TrainScheduleResponse` |

---

## 3. Verification & Test Evidence

### A. Unit & Integration Test Suite (`backend/tests/unit/api/test_train_discovery_api.py`)
- `test_search_trains_by_number`: verified train 12002 prefix lookup.
- `test_search_trains_by_name`: verified substring search for "Rajdhani".
- `test_search_trains_by_station`: verified intermediate station search ("BPL" returning 12002).
- `test_station_serving_trains_endpoint`: verified canonical `/api/v1/stations/BPL/trains` response and 404 handling.
- `test_compare_trains_endpoint`: verified NDLS ➔ BPL direct comparison, deduplication across trains, 400 on identical stations, 404 on missing stations, and empty state for disconnected pairs.
- `test_overnight_train_duration_math`: verified midnight crossing and day-offset arithmetic.
- `test_station_trains_service_classification`: verified `ORIGINATING`, `TERMINATING`, and `EN_ROUTE` boundary checks.
- **Result:** **7 passed in 3.26s**.

### B. Full Backend Regression Suite
- Ran the entire backend test suite across all milestones (TW-101 through TW-115 + TW-116):
- **Result:** **274 passed in 82.92s (100% pass rate)**. Zero regressions.

### C. Frontend Production Build
- Ran `npm run build` in `frontend/`:
- **Result:** `✓ Compiled successfully`, zero TypeScript or linting errors, 4 static pages pre-rendered.

### D. Browser-Based E2E Test (`frontend/tests/e2e/train_discovery_flow.e2e.mjs`)
- Automated user journey across Chrome:
  1. Navigated to Timetable mode.
  2. Searched train by number (`12002`) and verified autocomplete suggestions.
  3. Tested empty state for `UNKNOWN9999` and verified helpful error messaging.
  4. Tested train search by station name (`Bhopal`) returning matching trains.
  5. Inspected full train timetable for 12002 with verified TAG provenance.
  6. Navigated to Stations mode and inspected recorded trains serving `BPL`.
  7. Navigated to Compare mode, selected `NDLS` and `BPL`, and executed head-to-head comparison.
  8. Verified sorting by Earliest Departure and Fewest Intermediate Stops.
  9. Captured and saved full-page screenshot: `e2e_train_discovery_success.png`.
- **Result:** **PASSED COMPLETELY**.

---

## 4. Database Index & Query Performance Review
- Inspected PostgreSQL indexes on `train_schedules`:
  - `idx_schedules_lookup`: `btree (station_code, train_number)`
  - `uq_train_stop_sequence`: `btree (train_number, stop_sequence)`
- `EXPLAIN ANALYZE` on direct comparison query:
  - Query execution time: **1.626 ms**
  - Utilizes `Bitmap Index Scan` on `idx_schedules_lookup` and primary key index scan on `trains_pkey`.
  - Confirmed no additional indexes are needed; existing schema provides optimal sub-2ms query performance.

---

## 5. Artifacts & Screenshots
- E2E Screenshot: `C:\Users\MAYUR\.gemini\antigravity\brain\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a\e2e_train_discovery_success.png`
- Implementation Plan: `C:\Users\MAYUR\.gemini\antigravity\brain\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a\TW116_IMPLEMENTATION_PLAN.md`
