# TW-111 Implementation Plan: Station Intelligence & Nearby Station Discovery

## 1. Objectives & Engineering Scope
Transform TripWiser's existing station dataset (8,697 stations) and PostGIS geography capabilities into a station intelligence experience:
1. **Station Search API (`/stations/search`):** Search by code or name with exact code matches prioritized first, case-insensitive, with input validation and zero N+1 queries.
2. **Nearby Stations API (`/stations/nearby`):** PostGIS `ST_DWithin` spatial query accepting `station_code` (and optional coordinates for GPS fallback), calculating true geodetic distance in kilometres, excluding the source station, sorted nearest-first.
3. **Station Details API (`/stations/{station_code}`):** Retrieve station location metadata, coordinates, and verified timetable coverage (number of compiled trains calling/originating/terminating), distinguishing unknown stations (404) from stations with no compiled schedules (200 with honest zero-coverage notice).
4. **Frontend Station Intelligence Experience:**
   - Dedicated "Stations" navigation tab (`AppMode = 'stations'`).
   - Station search autocomplete console.
   - Comprehensive station detail inspector with honest timetable coverage.
   - Spatial radius selector (15 km, 30 km, 50 km, 75 km) showing nearby stations sorted by distance.
   - 1-click route integration: "Use as Origin" / "Use as Destination" seamlessly linking to Journey Search.
   - Enhanced `NearbyStationsModal` with station-code proximity lookup.

---

## 2. Technical Architecture & Database Reuse

### 2.1 Database & PostGIS Layer
- Existing table `stations` (`code`, `name`, `city`, `state`, `zone`, `location: Geography(POINT, 4326)`).
- Existing table `train_schedules` (`train_number`, `station_code`, `stop_sequence`, `arrival_time`, `departure_time`).
- Existing table `trains` (`number`, `name`, `origin_code`, `destination_code`, `runs_on_days`).

### 2.2 Search Exact-Match Prioritization
SQL case expression in `SQLAlchemyStationRepository.search_by_name_or_code`:
```sql
ORDER BY
  CASE
    WHEN UPPER(code) = UPPER(:clean_q) THEN 0
    WHEN UPPER(code) LIKE UPPER(:prefix_q) THEN 1
    WHEN UPPER(name) LIKE UPPER(:prefix_q) THEN 2
    ELSE 3
  END,
  name ASC
```

### 2.3 Nearby Stations by Station Code
In `SQLAlchemyStationRepository.get_nearby_stations_by_code`:
- Query source station geometry.
- If not found $\rightarrow$ return None (raises 404).
- Query `stations` where `code != source_code` and `ST_DWithin(location, source_point, radius_meters)`.
- Order by `dist_km ASC`. Limit to `limit` (max 50).

### 2.4 Station Details with Verified Timetable Coverage
In `SQLAlchemyStationRepository.get_station_details_with_coverage`:
- Fetch station info & coordinates.
- Single query aggregate from `train_schedules` and `trains`:
  - `total_compiled_trains`: distinct trains scheduled at this station.
  - `originating_trains`: trains where `origin_code == code`.
  - `terminating_trains`: trains where `destination_code == code`.
  - Status: `"VERIFIED_TIMETABLE_COVERAGE"` if trains > 0 else `"AWAITING_COMPILED_SCHEDULES"`.

---

## 3. Implementation Steps

1. **Backend Repositories & Domain:**
   - Update `StationRepository` interface with `get_nearby_stations_by_code` and `get_station_coverage`.
   - Update `SQLAlchemyStationRepository` with prioritized search, code-based nearby lookup, and coverage queries.
2. **Backend API Endpoints (`/api/v1/stations`):**
   - Update `/search` with exact-match ranking and validation.
   - Update `/nearby` to accept `station_code` (and keep `latitude`/`longitude` as optional).
   - Update `/{code}` to return location metadata, coordinates, and timetable coverage metrics.
3. **Backend Unit & Integration Tests:**
   - Test exact code match priority.
   - Test nearby stations by code and radius boundary.
   - Test unknown station 404 vs uncompiled station 200.
4. **Frontend Service & Types:**
   - Update `frontend/src/types/api.ts` with `StationDetailResponse` and `StationCoverage`.
   - Update `frontend/src/services/api.ts` with `getNearbyStationsByCode` and `getStationDetails`.
5. **Frontend Components:**
   - Build `frontend/src/components/stations/StationSearchCard.tsx`.
   - Build `frontend/src/components/stations/StationDetailView.tsx`.
   - Update `Navbar.tsx` with `"Stations"` tab.
   - Update `page.tsx` to support `mode === 'stations'`.
   - Update `NearbyStationsModal.tsx` to support station code lookup.
6. **Verification & Testing:**
   - Backend pytest suite (240+ tests).
   - Next.js production build (`npm run build`).
   - Browser E2E test (`station_discovery_flow.e2e.mjs`).
7. **Git Commit & Completion Report.**
