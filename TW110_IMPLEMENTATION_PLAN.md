# TW-110 Implementation Proposal: Train Schedule Intelligence & Intermediate Stoppage Inspector

**Milestone**: TW-110  
**Feature**: Train Schedule Intelligence & Intermediate Stoppage Inspector  
**Priority**: P1 (Core Product Usability)  
**Status**: PROPOSED — AWAITING CTO APPROVAL  
**Date**: November 2026  
**Authors**: Antigravity Pair Programming Engine  

---

## 1. Executive Summary & Problem Statement

### The Current State Post TW-109
In **TW-109**, TripWiser successfully expanded its timetable database from a bootstrap test set of 8 trains to a verified national network of **164 compiled domain trains, 23,602 schedule stop entries, and 8,697 stations** with an audited provenance catalog of 192 official Trains at a Glance (TAG) operating calendars.

### The Missing Capability
Despite storing **23,602 schedule stops** in PostgreSQL (`ScheduleORM`), this valuable data is currently **completely hidden from users**:
1. **No Intermediate Stop Visibility in Journey Search**: When a user finds a route (e.g., New Delhi $\rightarrow$ Bhopal on Train 12002 Shatabdi Express), the route card and `JourneyDetailsModal` only display the boarding and deboarding endpoints. The passenger cannot see intermediate halts (Mathura, Agra Cantt, Morena, Gwalior, Jhansi, Lalitpur), arrival/departure timings at those halts, or halt durations.
2. **No Dedicated Train Lookup API or UI**: TripWiser currently lacks any endpoint or interface to look up a train by number or name (e.g. searching "12951" or "Rajdhani") to view its schedule, route itinerary, and weekly running frequency.
3. **No Operating Day Frequency Guidance on Routes**: When viewing route options, users are not shown the train's operating day pattern (e.g., "Daily", "Except Fri", "Mon, Fri only"), making it impossible to understand why a train is unavailable on other dates.

### The Objective of TW-110
Unlock the 23,602 schedule records already in PostgreSQL to deliver **Train Schedule Intelligence**:
- Enable full intermediate stoppage inspection within route search results and the journey details modal.
- Build a dedicated Train Timetable Search API and UI console for direct train lookups.
- Display verified operating day patterns and running calendar provenance across all train cards.

---

## 2. User-Facing Outcome

1. **Expandable Intermediate Stops in Route Cards**:
   - On every direct and connecting journey leg, users can click **"View 5 Intermediate Stops"** to expand a clean timeline showing each intermediate halt, scheduled arrival, departure, halt duration in minutes (e.g. `2m halt`), distance from origin, and day offset.
2. **Intermediate Halts in Journey Details Modal**:
   - The `JourneyDetailsModal` expands to show the complete intermediate stoppage breakdown between the boarding station and deboarding station for each leg.
3. **Dedicated Train Timetable Console**:
   - A new navigation tab / search mode: **"Train Timetable"**.
   - Users can search any train number (e.g. `12002`) or name (e.g. `Shatabdi`) with autocomplete.
   - Renders a complete all-India route timeline from originating terminal to terminating destination, including total journey distance, average speed, operating days badges (`M T W T F S S`), and source provenance.
4. **Operating Frequency Badges**:
   - Route cards explicitly display operational frequency (e.g., `Runs Daily`, `Runs: Mon, Wed, Fri`, `Except Sun`) so users instantly understand train availability.

---

## 3. Scope and Explicit Non-Goals

### In Scope
- `GET /api/v1/trains/search`: Search trains by number prefix or name substring.
- `GET /api/v1/trains/{train_number}`: Fetch train metadata, origin, destination, operating days, and provenance.
- `GET /api/v1/trains/{train_number}/schedule`: Fetch complete ordered stops with halt durations and distances.
- `GET /api/v1/trains/{train_number}/intermediate-stops?from_code=X&to_code=Y`: Retrieve intermediate stops strictly bounded between a journey leg's boarding and deboarding stations.
- Frontend expandable stoppage timeline in `RouteCard.tsx` and `JourneyDetailsModal.tsx`.
- Frontend dedicated Train Search console and Schedule Viewer (`TrainScheduleView.tsx`).
- Operating days chips (`Mon`, `Tue`, `Wed`, etc.) and frequency verbal labels on route cards.
- Comprehensive unit, integration, and headless browser E2E test suites.

### Explicit Non-Goals
- **Live Running Status / GPS Tracking**: Strictly out of scope. TripWiser provides verified scheduled timetables; it will not fabricate real-time train positions.
- **Commercial Fares & Dynamic Pricing**: No fabrication of fares. The deferred fare policy established in TW-104/TW-105 remains untouched.
- **Seat Availability Predictions**: No fabrication of seat quotas or waiting list confirmation chances.
- **Modifications to Train Scheduling Algorithm**: Route discovery engine remains intact; it will simply attach intermediate stops to leg schemas or expose the on-demand query.

---

## 4. Architecture & Technical Design

### A. Backend Changes

#### 1. New API Router: `backend/app/api/v1/trains.py`
Exposes RESTful endpoints for train discovery and schedule retrieval:
```python
router = APIRouter(prefix="/trains", tags=["trains"])

@router.get("/search", response_model=List[TrainSummaryResponse])
async def search_trains(q: str = Query(..., min_length=2, max_length=50), limit: int = Query(10, le=25), session: AsyncSession = Depends(get_db)):
    ...

@router.get("/{train_number}", response_model=TrainDetailResponse)
async def get_train(train_number: str, session: AsyncSession = Depends(get_db)):
    ...

@router.get("/{train_number}/schedule", response_model=TrainScheduleResponse)
async def get_train_schedule(train_number: str, session: AsyncSession = Depends(get_db)):
    ...

@router.get("/{train_number}/intermediate-stops", response_model=IntermediateStopsResponse)
async def get_intermediate_stops(
    train_number: str,
    from_code: str = Query(..., min_length=1, max_length=10),
    to_code: str = Query(..., min_length=1, max_length=10),
    session: AsyncSession = Depends(get_db)
):
    ...
```

#### 2. Enhanced Train Repository: `SQLAlchemyTrainRepository`
Extend `backend/app/infrastructure/database/repositories/train_repository.py`:
- `search_trains(query: str, limit: int) -> list[Train]`: Queries `trains` table with `WHERE number ILIKE :q OR name ILIKE :q`.
- `get_schedule(train_number: str) -> list[ScheduleORM]`: Fetches ordered schedule stops joining `stations` for station names.
- `get_intermediate_stops(train_number: str, from_code: str, to_code: str) -> list[IntermediateStop]`: Efficiently slices the schedule between `from_sequence` and `to_sequence`.

#### 3. Halt Duration Calculation
In `ScheduleORM`, each stop has `arrival_time` and `departure_time`.
The halt duration (in minutes) is calculated cleanly:
$$\Delta t_{\text{halt}} = \text{departure\_time} - \text{arrival\_time}$$
(With overnight transition handling where departure is after midnight). Origin and terminating stations display `Origin` and `Destination` respectively.

### B. Frontend Changes

#### 1. API Client Extensions: `frontend/src/services/api.ts`
Add TypeScript functions:
- `searchTrains(query: string, limit?: number): Promise<TrainSummary[]>`
- `getTrainDetails(trainNumber: string): Promise<TrainDetail>`
- `getTrainSchedule(trainNumber: string): Promise<TrainSchedule>`
- `getIntermediateStops(trainNumber: string, fromCode: string, toCode: string): Promise<IntermediateStopsResponse>`

#### 2. Component Additions & Enhancements
- **`IntermediateStopsList.tsx`**: Lightweight, accessible collapsible list showing station code, station name, arrival time, departure time, halt duration (e.g. `2m halt`), and distance. Used inside `RouteCard.tsx` and `JourneyDetailsModal.tsx`.
- **`TrainSearchCard.tsx`**: Search box with autocomplete for train number / name.
- **`TrainScheduleView.tsx`**: Full schedule viewer featuring:
  - Header: Train number, train name, origin $\rightarrow$ destination, total distance (km), total stops.
  - Operating Days Strip: Visual chip indicators for `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun` highlighting active running days.
  - Interactive timeline of all stops with arrival, departure, halt, platform (if verified), and day offset indicators.
- **Main App Header / Mode Switcher (`Navbar.tsx` & `page.tsx`)**:
  - Add third mode tab: **"Routes"**, **"Bachelor Special"**, and **"Train Schedule"**.

---

## 5. Database & Migration Changes

- **No Schema Changes Required**:
  - The tables `trains`, `train_schedules`, and `stations` already exist and contain all necessary columns:
    - `trains`: `number`, `name`, `origin_code`, `destination_code`, `runs_on_days`.
    - `train_schedules`: `train_number`, `station_code`, `sequence`, `arrival_time`, `departure_time`, `day_offset`, `distance_km`.
    - `stations`: `code`, `name`, `latitude`, `longitude`, `zone`, `state`.
  - An index already exists on `train_schedules(train_number, sequence)`.
- **Optional Index Optimization (P2)**:
  - Add trigram or prefix B-tree index on `trains(name)` if substring search latency exceeds 50ms (with 164 rows, sequential scan is $<1$ms, so migration is deferred).

---

## 6. API Contracts & Example Payloads

### A. Train Search: `GET /api/v1/trains/search?q=shatabdi`
```json
[
  {
    "train_number": "12002",
    "train_name": "New Delhi-Bhopal Shatabdi Express",
    "origin_code": "NDLS",
    "destination_code": "BPL",
    "runs_on_days": [0, 1, 2, 3, 4, 5, 6],
    "frequency_description": "Daily (Mon-Sun)",
    "total_stops": 9,
    "distance_km": 707.0
  }
]
```

### B. Train Schedule: `GET /api/v1/trains/12002/schedule`
```json
{
  "train_number": "12002",
  "train_name": "New Delhi-Bhopal Shatabdi Express",
  "origin_code": "NDLS",
  "destination_code": "BPL",
  "runs_on_days": [0, 1, 2, 3, 4, 5, 6],
  "frequency_description": "Daily (Mon-Sun)",
  "provenance_tier": "OFFICIALLY_VERIFIED_INDIVIDUAL_TABLE_RECORD",
  "table_reference": "Table 3A: New Delhi - Rani Kamlapati (Bhopal) Shatabdi Express",
  "total_stops": 9,
  "total_distance_km": 707.0,
  "stops": [
    {
      "sequence": 1,
      "station_code": "NDLS",
      "station_name": "New Delhi",
      "arrival_time": null,
      "departure_time": "06:00:00",
      "halt_minutes": 0,
      "day_offset": 0,
      "distance_km": 0.0
    },
    {
      "sequence": 2,
      "station_code": "MTJ",
      "station_name": "Mathura Junction",
      "arrival_time": "07:19:00",
      "departure_time": "07:20:00",
      "halt_minutes": 1,
      "day_offset": 0,
      "distance_km": 141.0
    },
    {
      "sequence": 3,
      "station_code": "AGC",
      "station_name": "Agra Cantt",
      "arrival_time": "07:50:00",
      "departure_time": "07:55:00",
      "halt_minutes": 5,
      "day_offset": 0,
      "distance_km": 195.0
    },
    {
      "sequence": 9,
      "station_code": "BPL",
      "station_name": "Bhopal Junction",
      "arrival_time": "14:05:00",
      "departure_time": null,
      "halt_minutes": 0,
      "day_offset": 0,
      "distance_km": 707.0
    }
  ]
}
```

### C. Intermediate Stops: `GET /api/v1/trains/12002/intermediate-stops?from_code=MTJ&to_code=GWL`
```json
{
  "train_number": "12002",
  "from_station_code": "MTJ",
  "to_station_code": "GWL",
  "intermediate_stop_count": 2,
  "stops": [
    {
      "sequence": 3,
      "station_code": "AGC",
      "station_name": "Agra Cantt",
      "arrival_time": "07:50:00",
      "departure_time": "07:55:00",
      "halt_minutes": 5,
      "distance_km": 195.0
    },
    {
      "sequence": 4,
      "station_code": "DHO",
      "station_name": "Dholpur Junction",
      "arrival_time": "08:39:00",
      "departure_time": "08:40:00",
      "halt_minutes": 1,
      "distance_km": 248.0
    }
  ]
}
```

---

## 7. Reused vs New Modules

### Reused Modules
- `backend/app/infrastructure/database/models/train.py` (`TrainORM`, `ScheduleORM`)
- `backend/app/infrastructure/database/models/station.py` (`StationORM`)
- `backend/app/infrastructure/database/repositories/station_repository.py`
- `backend/app/infrastructure/database/repositories/train_repository.py`
- `backend/app/infrastructure/integration/calendar_provider.py`
- `frontend/src/components/layout/Navbar.tsx`, `Footer.tsx`
- `frontend/src/components/results/RouteCard.tsx`, `JourneyDetailsModal.tsx`
- `frontend/src/types/api.ts`

### New Modules Required
- `backend/app/api/v1/trains.py`: New FastAPI router for train lookup and schedules.
- `backend/tests/unit/api/test_trains_api.py`: Unit and integration test for trains API.
- `frontend/src/components/trains/TrainSearchCard.tsx`: Train search console with autocomplete.
- `frontend/src/components/trains/TrainScheduleView.tsx`: Full stoppage timetable and frequency inspector.
- `frontend/src/components/results/IntermediateStopsList.tsx`: Reusable expandable stoppage timeline.
- `frontend/tests/e2e/train_schedule_flow.e2e.mjs`: Headless Chrome E2E test verifying stoppage expansion and schedule lookup.

---

## 8. Data Sources & Limitations

1. **Static Railway Timetables (DataMeet + TAG 2024–2026)**:
   - Covers 164 compiled trains and 23,602 schedule stops.
   - Operating calendars verified for 192 services via official TAG tables.
2. **Limitations**:
   - Platform numbers are not present in static schedules (will be honestly labeled as "Platform assigned at station").
   - 5,011 uncompiled trains remain quarantined and will return `404 Train schedule awaiting verified operational calendar`.

---

## 9. Security, Data Integrity & Edge Cases

1. **Zero-Fabrication Principle**:
   - No synthetic intermediate halts or assumed timings.
   - If a train has no intermediate stops between two consecutive junctions (non-stop leg), the UI cleanly displays `Non-stop direct leg (0 intermediate stops)`.
2. **Endpoint Mismatch & Loop Protection**:
   - Validates that `from_code` precedes `to_code` in the train's sequence. Returns HTTP 400 if reversed.
3. **Overnight Halt Calculation**:
   - When a train arrives at 23:55 and departs at 00:05, halt duration is calculated as 10 minutes (not negative).
4. **Input Sanitization**:
   - Train numbers stripped, validated with regex `^[0-9A-Za-z\-]{1,20}$`.

---

## 10. Priority Classification

| Priority | Feature / Component | Description |
| :--- | :--- | :--- |
| **P0** | Intermediate Stoppage Endpoint & Logic | `GET /api/v1/trains/{train_number}/intermediate-stops` and halt duration calculation. |
| **P0** | Expandable Halts in Route Cards & Modal | UI timeline showing intermediate stops, arrival, departure, halt, and distance. |
| **P1** | Train Timetable Lookup API | `GET /api/v1/trains/{train_number}` and `/schedule`. |
| **P1** | Dedicated Train Timetable Search UI | Train autocomplete and schedule inspector view. |
| **P1** | Operating Day Frequency Chips | Visual `Mon–Sun` badges and verbal summary ("Except Fri"). |
| **P2** | Train Search Trigram Optimization | Optional database index if sequential scan exceeds threshold. |
| **P3** | Printable Stoppage PDF Export | Browser print stylesheet enhancement for stoppage tables. |

---

## 11. Testing Strategy

1. **Backend Tests (Pytest)**:
   - `test_trains_api_search`: Verifies search by train number ("12002") and train name ("Shatabdi").
   - `test_trains_api_schedule`: Validates sequence, monotonic distance, positive halt duration, and station names.
   - `test_trains_api_intermediate_stops`: Tests exact sequence slicing and 400 error on reversed station order.
   - `test_trains_api_not_found`: Asserts 404 on uncompiled or non-existent trains.
2. **Frontend Component Tests**:
   - `IntermediateStopsList` rendering halt durations and distance markers.
   - `TrainScheduleView` rendering operating day chips correctly for daily vs non-daily trains.
3. **Browser E2E (Puppeteer Headless Chrome)**:
   - `train_schedule_flow.e2e.mjs`:
     1. Search journey `NDLS` $\rightarrow$ `BPL`.
     2. Expand route card intermediate stops $\rightarrow$ assert `Agra Cantt` and `Gwalior` are present with halt durations.
     3. Open Journey Details modal $\rightarrow$ assert intermediate stops timeline renders inside modal.
     4. Switch to "Train Timetable" tab.
     5. Type "12002" $\rightarrow$ click suggestion $\rightarrow$ verify full 9-stop timetable and operating day chips.

---

## 12. Acceptance Criteria

- [ ] `GET /api/v1/trains/search?q={query}` returns matching trains from the 164 verified trains within 50ms.
- [ ] `GET /api/v1/trains/{train_number}/schedule` returns complete ordered stop sequences with station names and non-negative halt minutes.
- [ ] `GET /api/v1/trains/{train_number}/intermediate-stops` returns only stops between `from_code` and `to_code`.
- [ ] Route cards in Journey Search allow expanding and collapsing intermediate stops cleanly.
- [ ] Journey Details modal renders intermediate stops with halt times and cumulative distances.
- [ ] Users can navigate to "Train Timetable" search, enter a train number, and view its full schedule and operating days.
- [ ] Running days badges visually distinguish active operating days from inactive days without fabrication.
- [ ] 100% of existing 234 pytest tests continue to pass.
- [ ] New browser E2E test suite passes 10/10 assertions on headless Chrome.

---

## 13. Estimated Implementation Phases

- **Phase 1: Backend API & Repositories (1.5 hours)**
  - Implement `SQLAlchemyTrainRepository.get_schedule` and `get_intermediate_stops`.
  - Create `backend/app/api/v1/trains.py` and register router in `backend/app/main.py`.
  - Add backend unit and integration tests.
- **Phase 2: Frontend Stoppage Timeline & Modal Integration (1.5 hours)**
  - Build `IntermediateStopsList.tsx`.
  - Integrate into `RouteCard.tsx` and `JourneyDetailsModal.tsx`.
  - Add operating frequency badges (`Runs Daily`, etc.).
- **Phase 3: Dedicated Train Timetable Search Console (1.5 hours)**
  - Build `TrainSearchCard.tsx` and `TrainScheduleView.tsx`.
  - Integrate mode tab into `Navbar.tsx` and `page.tsx`.
- **Phase 4: Verification & E2E Validation (1 hour)**
  - Run full backend pytest regression suite.
  - Run Next.js production build (`npm run build`).
  - Execute browser-based Puppeteer E2E tests for journey flow, bachelor flow, and train schedule flow.

