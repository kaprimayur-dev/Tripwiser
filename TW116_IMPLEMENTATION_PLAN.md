# TW-116 Revised Implementation Plan: Train Discovery & Passenger Intelligence

## Executive Summary
This revised plan incorporates the mandatory engineering refinements for **TW-116**:
1. **Efficient Indexed Train Search**: Supporting train number, train name, origin/destination codes, and intermediate stations via SQL `EXISTS` subqueries without loading full schedules into memory.
2. **Station-Serving Trains with Multi-Visit Support**: Accurate classification of `ORIGINATING`, `TERMINATING`, and `EN_ROUTE` based on actual schedule sequence; supporting repeated visits (circular / reversal routes); sorting without treating `NULL` as midnight; deriving operating days strictly from verified calendars.
3. **Robust Direct Train Comparison**: Enforcing forward journey sequence (`origin.stop_sequence < destination.stop_sequence`), calculating journey duration via absolute date-aware timestamps and day offsets, preventing duplicate comparison results for loop routes, and returning clear `None`/`null` indicators when optional data is absent.
4. **Data Provenance & Transparency**: Reusing existing TAG provenance without implying live running status or seat availability; distinguishing unavailable data from zero values.
5. **Passenger-Centric Frontend**: Reusing existing timetable and station components, enabling direct timetable inspection from comparison cards, and adhering to the warm editorial transit journal design system.
6. **Exhaustive Testing**: Dedicated test cases for overnight journeys, repeated stations, multi-visit stops, missing calendars, incomplete timings, reverse sequences, and full regression verification.

---

## 1. Existing Infrastructure & Reusable Assets

### Backend Assets
- **Models**:
  - `backend/app/domain/models/train.py` (`Train`, `TrainSummary`, `TrainDetail`)
  - `backend/app/domain/models/station.py` (`Station`)
  - `backend/app/domain/models/schedule.py` (`ScheduleStop`, `TrainSchedule`)
  - `backend/app/infrastructure/database/models.py` (`TrainORM`, `StationORM`, `ScheduleORM`)
- **Repositories**:
  - `backend/app/infrastructure/database/repositories/train_repository.py`
  - `backend/app/infrastructure/database/repositories/station_repository.py`
  - `backend/app/infrastructure/database/repositories/schedule_repository.py`
- **APIs & Logic**:
  - Existing `GET /api/v1/trains/{train_number}` and `GET /api/v1/trains/{train_number}/schedule`
  - Existing date-aware day-offset duration calculation patterns from `RouteDiscoveryEngine` and `JourneyReliabilityService`

### Frontend Assets
- **Components**:
  - `frontend/src/components/trains/TrainScheduleView.tsx` (timetable and stoppage sequence inspector)
  - `frontend/src/components/trains/TrainSearchCard.tsx` (autocomplete lookup)
  - `frontend/src/components/stations/StationDetailView.tsx` (station metadata & coverage)
  - `frontend/src/components/stations/StationSearchCard.tsx` (station lookup)
  - `frontend/src/components/search/StationAutocomplete.tsx` (station picker with keyboard navigation)
  - `frontend/src/components/layout/Navbar.tsx` (mode navigation)
- **Services & Contracts**:
  - `frontend/src/services/api.ts`
  - `frontend/src/types/api.ts`

---

## 2. Exact Files to Modify & Create

### Backend Files
1. **`backend/app/infrastructure/database/repositories/train_repository.py`**
   - Refactor `search_trains(query, limit)`:
     - Use `EXISTS` subquery on `ScheduleORM` joined with `StationORM` for intermediate station matches.
     - Push pagination and limit down to SQL.
   - Refactor `get_trains_serving_station(station_code, limit)`:
     - Fetch schedule records for `station_code`.
     - Subquery train's minimum and maximum `stop_sequence` to determine `ORIGINATING`, `TERMINATING`, or `EN_ROUTE`.
     - Keep multiple records if a train calls at the station more than once in its journey.
     - Sort with `NULLS LAST` on scheduled departure/arrival times so missing times never sort as midnight (`00:00`).
     - Map operating frequency strictly from verified train operating day calendars.
   - Implement `compare_direct_trains(origin_code, destination_code)`:
     - Aliased self-join on `ScheduleORM` (`orig_sched` and `dest_sched`).
     - Strict sequence predicate: `orig_sched.stop_sequence < dest_sched.stop_sequence`.
     - Deduplicate using SQL `DISTINCT ON (train_number)` or deterministic sequence selection (choosing the minimal valid forward span) to avoid duplicate cards for multi-visit trains.
     - Calculate journey duration using `(dest_sched.day_offset * 1440 + dest_arr_min) - (orig_sched.day_offset * 1440 + orig_dep_min)`. If times are missing, return `None`.
     - Calculate intermediate stop count: `dest_sched.stop_sequence - orig_sched.stop_sequence - 1`.

2. **`backend/app/api/v1/trains.py`**
   - Define Pydantic response models:
     - `StationTrainServiceSchema`: train number, name, origin, destination, service role (`ORIGINATING` | `TERMINATING` | `EN_ROUTE`), arrival/departure times, halt duration, day offset, operating frequency, and stop sequence.
     - `StationTrainsResponse`: station metadata, total count, list of services.
     - `TrainComparisonItem`: train number, name, origin, destination, departure time, arrival time, day offset, scheduled duration in minutes, formatted duration, intermediate stop count, operating frequency, verified days list, and timetable coverage disclosure.
     - `TrainComparisonResponse`: origin station, destination station, direct train count, comparison items.
   - Register endpoints:
     - `GET /api/v1/trains/compare?origin={code}&destination={code}`
     - `GET /api/v1/trains/station/{station_code}?limit={limit}`

3. **`backend/app/api/v1/stations.py`**
   - Register route alias: `GET /api/v1/stations/{code}/trains` delegating to train service.

4. **`backend/tests/unit/api/test_train_discovery_api.py`** & **`backend/tests/integration/database/test_train_discovery_refinements.py`**
   - Comprehensive test suite covering all 9 required testing scenarios.

### Frontend Files
1. **`frontend/src/types/api.ts`**
   - Add TypeScript interfaces for `StationTrainService`, `StationTrainsResponse`, `TrainComparisonItem`, `TrainComparisonResponse`.
2. **`frontend/src/services/api.ts`**
   - Add `compareTrains(originCode, destinationCode)` and `getStationTrains(stationCode, limit)`.
3. **`frontend/src/components/trains/TrainCompareView.tsx`** (New Component)
   - Origin/Destination station pickers with swap button.
   - Direct train comparison cards featuring scheduled departure, arrival, duration, stop count, operating days, and provenance disclosures.
   - Sorting controls: Fastest, Earliest, Fewest Stops.
   - Action button: "Inspect Full Timetable" navigating directly to the existing `TrainScheduleView`.
4. **`frontend/src/components/stations/StationDetailView.tsx`**
   - "Recorded Trains Serving This Station" section displaying calling trains, service type badge (`ORIGINATING`, `TERMINATING`, `EN_ROUTE`), halt duration, arrival/departure, and direct link to inspect schedule.
5. **`frontend/src/components/trains/TrainSearchCard.tsx`**
   - Multi-field search placeholder and informative empty state with actionable suggestions.
6. **`frontend/src/components/layout/Navbar.tsx`**
   - Mode switcher including Compare Trains (`compare`).
7. **`frontend/src/app/page.tsx`**
   - State management linking Compare and Station views to Timetable inspector without creating redundant duplicate pages.

---

## 3. Database Query Strategy

### A. Train Search
- Direct indexed lookup on `train_number` (`train_number ILIKE :q%`).
- Case-insensitive substring lookup on `train_name` (`train_name ILIKE %:q%`).
- Exact lookup on terminal stations (`origin_station_code = :q OR destination_station_code = :q`).
- Correlated `EXISTS` subquery against `schedules` and `stations` without in-memory schedule aggregation:
  ```sql
  EXISTS (
      SELECT 1 FROM schedules s
      JOIN stations st ON s.station_code = st.code
      WHERE s.train_number = trains.train_number
        AND (st.code ILIKE :q OR st.name ILIKE :q_like)
  )
  ```
- Combined with `UNION` / `OR`, ordered by match priority (`exact_number > name_prefix > station_match`), with `LIMIT` applied directly in PostgreSQL.

### B. Station-Serving Trains
- Query `schedules` filtered by `station_code = :station_code`.
- Determine service role dynamically by comparing with each train's overall schedule boundaries:
  - Subquery min and max sequence: `SELECT train_number, MIN(stop_sequence) AS min_seq, MAX(stop_sequence) AS max_seq FROM schedules GROUP BY train_number`.
  - Classification:
    - If `schedule.stop_sequence == min_seq` $\to$ `ORIGINATING`
    - If `schedule.stop_sequence == max_seq` $\to$ `TERMINATING`
    - Else $\to$ `EN_ROUTE`
- Multi-visit support: Retain distinct stops if a train calls at a station more than once (e.g. stop 3 and stop 12).
- Scheduled time sorting: `ORDER BY departure_time ASC NULLS LAST, arrival_time ASC NULLS LAST`, preventing `NULL` timings from being treated as `00:00` midnight.

### C. Direct Train Comparison
- Aliased self-join on `schedules` table (`orig_sched` and `dest_sched`):
  ```sql
  SELECT DISTINCT ON (t.train_number)
      t.train_number, t.train_name, t.origin_station_code, t.destination_station_code,
      orig_sched.departure_time, orig_sched.day_offset AS orig_day,
      dest_sched.arrival_time, dest_sched.day_offset AS dest_day,
      orig_sched.stop_sequence AS orig_seq, dest_sched.stop_sequence AS dest_seq,
      (dest_sched.stop_sequence - orig_sched.stop_sequence - 1) AS intermediate_stops
  FROM trains t
  JOIN schedules orig_sched ON orig_sched.train_number = t.train_number
  JOIN schedules dest_sched ON dest_sched.train_number = t.train_number
  WHERE orig_sched.station_code = :origin_code
    AND dest_sched.station_code = :dest_code
    AND orig_sched.stop_sequence < dest_sched.stop_sequence
  ORDER BY t.train_number, (dest_sched.stop_sequence - orig_sched.stop_sequence) ASC
  ```
- Forward sequence guarantee: Strictly `orig_sched.stop_sequence < dest_sched.stop_sequence`.
- Multi-visit deduplication: `DISTINCT ON (t.train_number)` ordered by minimal sequence span ensures exactly one canonical forward segment per train.

---

## 4. Data Integrity & Provenance Decisions

1. **Duration Mathematical Identity**:
   $$\text{scheduled\_duration\_minutes} = (\text{dest\_day\_offset} \times 1440 + \text{dest\_arrival\_minutes}) - (\text{orig\_day\_offset} \times 1440 + \text{orig\_departure\_minutes})$$
   - Handles multi-day overnight journeys seamlessly.
   - If either scheduled timestamp is missing, `scheduled_duration_minutes` is explicitly returned as `None`/`null` — never defaulted to `0`.
2. **Missing vs Zero Differentiation**:
   - `halt_minutes == 0` is presented as a "Passing / Brief Operational Call", whereas `halt_minutes is None` is presented as "Halt timing unrecorded".
   - `intermediate_stops_count == 0` is a true non-stop run; absence of intermediate records is disclosed if schedule compilation is incomplete.
3. **Verified Calendars Only**:
   - Operating frequencies (`Daily`, `Weekly (M, W, F)`, etc.) are extracted strictly from compiled `runs_on_days` metadata.
   - If calendar metadata is absent, the API returns `None` and the UI displays `"Operating calendar unrecorded"`.
4. **Transparent TAG Timetable Provenance**:
   - Disclose prominently: *"Based on compiled Indian Railways Trains at a Glance (TAG) records. Not a live GPS tracking or seat reservation system."*

---

## 5. Test Matrix & Verification Scenarios

| Category | Test Scenario | Expected Outcome |
| :--- | :--- | :--- |
| **Overnight Journeys** | Train departs 23:30 Day 1, arrives 06:15 Day 2 (`day_offset=1`). | Duration calculated exactly as $405\text{ min}$ ($6\text{h }45\text{m}$), crossing midnight accurately. |
| **Repeated Stations** | Train calls at Station X at stop 3, loops, and calls at Station X at stop 12. | Both calls preserved in station serving trains with accurate respective arrival/dep and sequence numbers. |
| **Reverse Sequence** | User queries comparison with origin sequence $>$ destination sequence. | Excluded from direct train comparison; returns zero matching forward trains. |
| **Multi-Visit Corridor** | Train visits A $\to$ B $\to$ C $\to$ B. | Comparison between A $\to$ B produces exactly 1 deduplicated result for the forward segment. |
| **Missing Calendars** | Train record with `runs_on_days = None` or empty bitmask. | Handled gracefully without crash; returns unrecorded status; no fake "Daily" claim. |
| **Missing Timing Data** | Schedule record with `arrival_time = None` or `departure_time = None`. | `scheduled_duration_minutes` returns `None`; sorting orders with `NULLS LAST` (never sorted as 00:00). |
| **Search Subquery** | Search by intermediate station name e.g. "Jhansi". | Returns trains calling at Jhansi without loading complete railway database into memory. |
| **Empty States** | Train search with non-existent query (e.g. `UNKNOWN9999`). | Clear, friendly empty state with helpful query guidance. |
| **Regressions** | Full test suite across TW-101 to TW-115. | 100% pass rate across route discovery, multi-transfer, journey reliability, and Bachelor Special. |
