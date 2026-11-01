# TW-104 Implementation Plan: Route Discovery Engine

**Milestone**: TW-104 — Route Discovery Engine  
**Author**: Lead Backend Engineer (AI Pair Programmer)  
**Date**: November 1, 2026  
**Status**: PROPOSED — Standing by for CTO Review  
**Prerequisites**: TW-103F committed (`1a18f74bf270055640423664ecb7272cc9d8077f`). Clean working tree verified.

---

## 1. User-Visible Functionality

1. **Direct Route Search**:
   - Searches direct trains connecting origin and destination stations on a chosen journey date.
   - Accurately checks train operating days taking into account the stop's route `day_offset`.
2. **Multi-Leg (1-Transfer / 2-Leg) Alternative Discovery**:
   - When direct trains are unavailable or as alternative options, discovers practical connecting journeys via intermediate transfer stations.
   - Enforces realistic transfer buffer windows (minimum 30 minutes, maximum 6 hours).
3. **Route Ranking**:
   - **Recommended**: Composite score prioritizing direct trains, optimal transfer buffers (45–120 min), and shortest total duration.
   - **Fastest**: Sorted strictly by total journey duration ascending.
   - **Fewest Transfers**: Direct trains first, then 1-stop connecting routes.
   - **Cheapest**: Explicitly deferred / flagged as unavailable pending commercial fare feeds (no fabricated fares).
4. **Transparent Diagnostics on Empty Results**:
   - Returns clear, actionable reasons when no route is found (`NO_DIRECT_OR_CONNECTING_TRAINS`, `NO_RUNNING_DAYS_MATCH`, `TRANSFER_BUFFER_VIOLATION`, `STATION_NOT_FOUND`).
5. **Station Autocomplete & Nearby Stations API**:
   - Exposes station search by code/name and PostGIS spatial nearby station lookup to power the frontend search inputs.

---

## 2. Proposed Algorithm and Flow

### Step A: Input Validation & Station Resolution
1. Validate `origin_code` and `destination_code` are non-empty and distinct.
2. Resolve origin and destination `Station` models from `StationRepository`.
3. Compute departure day of week from `journey_date`.

### Step B: Direct Route Search
1. Query candidate trains via `train_repository.find_direct_trains(origin_code, destination_code)`.
2. For each candidate train:
   - Slice schedule from `origin_code` to `destination_code`.
   - Calculate origin departure day of week:
     $$\text{route\_origin\_day} = (\text{journey\_date.weekday}() - \text{origin\_stop.day\_offset}) \pmod 7$$
   - Check if $\text{route\_origin\_day} \in \text{train.runs\_on\_days}$.
   - If operating:
     - $\text{dep\_datetime} = \text{journey\_date} + \text{origin\_stop.departure\_time}$
     - $\text{arr\_datetime} = \text{dep\_datetime} + (\text{dest\_stop.day\_offset} - \text{origin\_stop.day\_offset}) \text{ days} + (\text{dest\_stop.arrival\_time} - \text{origin\_stop.departure\_time})$
     - $\text{duration\_minutes} = \frac{\text{arr\_datetime} - \text{dep\_datetime}}{60}$
     - Assemble into [`JourneyLeg`](file:///c:/projects/tripwiser/backend/app/domain/models/route.py#L5) and [`CandidateRoute`](file:///c:/projects/tripwiser/backend/app/domain/models/route.py#L57) (`is_direct=True`, `transfer_count=0`).

### Step C: 1-Transfer (2-Leg) Connecting Route Search
1. Identify Candidate Transfer Hubs $H$:
   - Find intermediate stations reachable from `origin_code` on Leg 1, from which `destination_code` is reachable on Leg 2:
     $$H \in \{ s \mid \text{origin} < s \text{ on train}_A \} \cap \{ s \mid s < \text{destination} \text{ on train}_B \}$$
   - Restrict candidate hubs using indexed SQL subqueries and limit to top matching stations (max 20 hubs) to keep latency under 200ms.
2. Connection Feasibility & Transfer Buffer Validation:
   - For each valid Leg 1 arriving at hub $H$ at $T_{\text{arr}, 1}$:
     - For each valid Leg 2 departing hub $H$ at $T_{\text{dep}, 2}$:
       - Check Leg 2 operating days at hub $H$.
       - Compute transfer duration: $\Delta T = T_{\text{dep}, 2} - T_{\text{arr}, 1}$.
       - Enforce connection bounds: $30 \text{ min} \le \Delta T \le 360 \text{ min}$.
       - If valid: assemble `JourneyLeg 1` + `JourneyLeg 2` $\to$ `CandidateRoute` (`is_direct=False`, `transfer_count=1`, `transfer_durations_minutes=[\Delta T]`).

### Step D: Route Ranking
- Sort results based on selected strategy (`recommended`, `fastest`, `fewest_transfers`).
- Limit results to top $K$ (default: 20 routes).

---

## 3. Existing Components to Reuse

- **Domain Models**:
  - [`CandidateRoute`](file:///c:/projects/tripwiser/backend/app/domain/models/route.py#L57), [`JourneyLeg`](file:///c:/projects/tripwiser/backend/app/domain/models/route.py#L5)
  - [`AvailabilityResult`](file:///c:/projects/tripwiser/backend/app/domain/models/availability.py#L15), [`AvailabilityStatusCode`](file:///c:/projects/tripwiser/backend/app/domain/models/availability.py#L6)
  - [`Station`](file:///c:/projects/tripwiser/backend/app/domain/models/station.py#L10), [`Train`](file:///c:/projects/tripwiser/backend/app/domain/models/train.py#L11), [`TrainScheduleEntry`](file:///c:/projects/tripwiser/backend/app/domain/models/train.py#L48)
- **Database Layer**:
  - [`StationORM`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/models/station.py#L8), [`TrainORM`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/models/train.py#L7), [`ScheduleORM`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/models/train.py#L28)
  - [`SQLAlchemyStationRepository`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/repositories/station_repository.py#L9) (spatial distance and station lookups)
  - [`SQLAlchemyTrainRepository`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/repositories/train_repository.py#L9) (direct train queries)
  - [`AsyncSessionLocal`](file:///c:/projects/tripwiser/backend/app/core/db.py#L16)
- **Ingested Database Foundation**:
  - 8,697 geocoded stations in PostGIS `stations` table.
  - Verified compiled benchmark trains with schedules in `trains` and `train_schedules` tables.

---

## 4. New Files Expected

1. `backend/app/domain/services/__init__.py`
2. `backend/app/domain/services/route_engine.py`: Core route discovery service, operating day calendar logic, transfer validation, ranking engine.
3. `backend/app/api/v1/routes.py`: FastAPI route search endpoints (`GET /api/v1/routes/search`).
4. `backend/app/api/v1/stations.py`: FastAPI station search and nearby spatial endpoints.
5. `backend/tests/unit/services/test_route_engine.py`: Unit tests for calendar matching, day offsets, transfer timing, and ranking.
6. `backend/tests/integration/api/test_route_search_api.py`: Integration tests against FastAPI and PostGIS database.
7. `TW104_IMPLEMENTATION_PLAN.md` (this plan).

---

## 5. API Endpoints and Response Structure

### 5.1 Route Search: `GET /api/v1/routes/search`
**Parameters**:
- `origin`: `str` (e.g. `BCT`, `NDLS`, `GWL`)
- `destination`: `str` (e.g. `NDLS`, `BPL`, `HWH`)
- `date`: `str` (`YYYY-MM-DD`)
- `max_transfers`: `int = 1` (0 for direct only, 1 for 1 transfer)
- `sort_by`: `str = "recommended"` (`recommended`, `fastest`, `fewest_transfers`, `cheapest`)

**Response Schema**:
```json
{
  "query": {
    "origin": "BCT",
    "destination": "NDLS",
    "journey_date": "2026-11-05",
    "max_transfers": 1,
    "sort_by": "recommended"
  },
  "total_routes_found": 1,
  "direct_routes_count": 1,
  "transfer_routes_count": 0,
  "routes": [
    {
      "route_id": "route_12951_20261105",
      "is_direct": true,
      "transfer_count": 0,
      "total_duration_minutes": 930,
      "total_fare": 0.0,
      "fare_status": "DEFERRED",
      "legs": [
        {
          "train_number": "12951",
          "train_name": "Mumbai Central-New Delhi Rajdhani Express",
          "origin_code": "BCT",
          "destination_code": "NDLS",
          "departure_time": "2026-11-05T17:00:00",
          "arrival_time": "2026-11-06T08:30:00",
          "duration_minutes": 930,
          "distance_km": 1386.0,
          "travel_class": "3A",
          "availability": {
            "status": "AVAILABLE",
            "available_count": null,
            "quota": "GN",
            "travel_class": "3A",
            "fare": 0.0,
            "source": "verified_schedule"
          }
        }
      ]
    }
  ],
  "no_route_reason": null
}
```

### 5.2 Station Autocomplete: `GET /api/v1/stations/search?q=MUMBAI&limit=5`
Returns matching stations for frontend input dropdowns.

---

## 6. Essential Tests

1. **Operating Day & Day Offset Calculation**:
   - Verify that train operating once a week on Wednesdays correctly matches departure on Wednesday from route origin, and Thursday from intermediate stops with `day_offset=1`.
2. **Transfer Buffer Enforcement**:
   - Connections with $< 30$ min buffer are rejected.
   - Connections with $> 360$ min buffer are rejected.
   - Connections within 30–360 min are accepted with correct transfer duration.
3. **Route Continuity & Invariants**:
   - Verify all generated `CandidateRoute` and `JourneyLeg` objects satisfy domain validation (connectivity, timestamps, non-negative durations).
4. **Ranking Correctness**:
   - `fastest`: strictly ordered by total duration ascending.
   - `fewest_transfers`: direct routes listed before connecting routes.
   - `recommended`: balance of duration and connection quality.
5. **No Route Found Reasons**:
   - Returns clear error codes when no connections exist or constraints are unsatisfied.
6. **FastAPI End-to-End API Tests**:
   - HTTP status codes, parameter validation, JSON serialization against live database.

---

## 7. Risks or Blockers

- **Multi-Leg Hub Query Latency**:
  - Unbounded cartesian products across large schedules could cause slow response times.
  - *Mitigation*: Limit candidate hubs to stations appearing in both origin outbound and destination inbound sets, sorted by junction importance, capped at 20 hubs.
- **Fare Data Absence**:
  - Network-wide commercial fares are not present in open datasets.
  - *Mitigation*: Strictly defer fare ranking; report `total_fare=0.0` and `fare_status="DEFERRED"`. Never fabricate ticket prices.
- **Bachelor Special & Booking**:
  - Explicitly excluded from TW-104 scope per project guidelines.

---

## 8. Standing By for CTO Authorization

This plan is focused, practical, and reuses established components. **No code has been implemented, and nothing has been staged or committed.** Standing by for CTO review.

