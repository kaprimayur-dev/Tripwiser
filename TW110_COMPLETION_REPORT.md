# TW-110 Completion Report — Train Schedule Intelligence & Intermediate Stoppage Inspector

**Milestone:** TW-110  
**Status:** Completed & Fully Verified (Post-Audit Terminology Aligned)  
**Date:** November 2, 2026  
**Commit Message:** `feat(trains): add timetable intelligence and intermediate stop inspection`

---

## 1. Executive Summary

TripWiser previously compiled and verified **164 trains** across major Indian Railway trunk corridors with individual evidence citations from **Trains at a Glance (TAG 2024–2026)**, backed by **23,602 schedule entries** in PostgreSQL.

Prior to TW-110, users could discover connecting routes and Bachelor Special berth segments, but intermediate stops inside journey legs were opaque numbers, and there was no dedicated interface to inspect a train's complete schedule, intermediate halts, running days, or official provenance.

Under **TW-110**, TripWiser unlocks full timetable intelligence:
1. **Dedicated Train Timetable Inspector:** Users can search any compiled train by number or name (e.g. `12002`, `12951`, `12621`, `Shatabdi`, `Rajdhani`) to inspect its verified stoppage timeline, arrival/departure timings, halt durations, total distance, operating running days (Mon–Sun chips), and official TAG table provenance.
2. **Intermediate Stoppage Inspection in Journey Discovery:** Route cards, transit timelines, and the Journey Details Modal now provide an expandable stoppage view showing every intermediate halt with arrival, departure, and halt duration pills between any origin and destination leg.
3. **Robust Backend APIs & Zero-Fabrication Architecture:** High-performance endpoints for train search, train details, full schedules, and sliced intermediate stops with zero N+1 database queries, strict quarantine handling, and zero invented timings, platforms, or running days.

---

## 2. Architecture & Backend Implementation

### 2.1 Domain & Data Layer Enhancements
- **`backend/app/domain/models/route.py`**:
  - Enhanced `JourneyLeg` domain model with `runs_on_days: Optional[list[int]] = None` and `intermediate_stop_count: int = 0`.
- **`backend/app/infrastructure/database/repositories/train_repository.py`**:
  - Added `search_trains(query, limit)` querying both train number prefix and train name substrings using case-insensitive SQL matching.
  - Added `get_schedule_with_stations(train_number)` joining `train_schedules` with `stations` to retrieve stop sequences, station names, codes, arrival/departure times, and distances in a single indexed query.
  - Added `get_station_names_for_codes(station_codes)` batch helper to avoid N+1 queries.
- **`backend/app/domain/services/route_engine.py`**:
  - Enhanced `_build_journey_leg` to count intermediate scheduled halts with positive dwell time (`arrival_time != departure_time`) and attach running days from verified calendars.

### 2.2 REST API Endpoints (`/api/v1/trains`)
Registered in `backend/app/main.py` before dynamic route parameters to avoid route collision:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/trains/search?q={query}&limit={limit}` | Fast autocomplete for compiled trains by number prefix or name substring. |
| `GET` | `/api/v1/trains/{train_number}` | Detailed train metadata, origin/destination, running days, and TAG table citation. |
| `GET` | `/api/v1/trains/{train_number}/schedule?only_commercial={true\|false}` | Complete stoppage timeline with sequence, station codes/names, arrival/departure, halt duration, and distance. |
| `GET` | `/api/v1/trains/{train_number}/intermediate-stops?from_code={code}&to_code={code}&only_commercial={true\|false}` | Slices schedule strictly between boarding and debarking station codes. |

### 2.3 Strict Quarantine & Error Distinction
- Non-existent train number $\rightarrow$ `404 Not Found` with detail: `"Train {train_number} not found"`.
- Train present in raw tables but uncompiled or quarantined $\rightarrow$ `404 Not Found` with detail: `"Train {train_number} is awaiting verified schedule compilation. Only trains with verified timetable evidence are served under TripWiser zero-fabrication rules."`.
- Static route `/search` is registered before `/{train_number}` to ensure autocomplete queries are never matched as train numbers.

### 2.4 Halt Duration Calculation
Halt durations in minutes are calculated from verified schedule arrival and departure times:
- Origin and terminus stations: `0` min halt.
- Passing stops (`arrival_time == departure_time`): `0` min halt.
- Daytime commercial stops: `(dep.hour * 60 + dep.minute) - (arr.hour * 60 + arr.minute)`.
- Overnight halts crossing midnight: handles `dep < arr` by adding 1,440 minutes.

---

## 3. Frontend Experience & Component Design

### 3.1 Train Timetable Search Console (`TrainSearchCard.tsx`)
- Instant autocomplete search input supporting train numbers (e.g. `12002`) and train names (e.g. `Bhopal Shatabdi`).
- Dropdown suggestion list displaying train number badge, train name, origin-destination route, and verified TAG badge.
- Preset quick-launch pills for iconic Indian Railway trains (`12002 Bhopal Shatabdi`, `12951 Mumbai Rajdhani`, `12301 Howrah Rajdhani`, `12621 Tamil Nadu Express`).

### 3.2 Train Timetable Viewer (`TrainScheduleView.tsx`)
- **Header Banner:** Displays train number, verified TAG status, official table reference (e.g. `Table 3A: New Delhi - Rani Kamlapati (Bhopal) Shatabdi Express`), total distance, and scheduled halts count.
- **Operating Running Days Strip:** Visual Mon–Sun chips highlighting active days with tooltips (e.g. `Runs on Mon`, `Does not run on Fri`).
- **Scheduled Halts vs All Recorded Stops Toggle:** Allows users to view either scheduled timetable halts with dwell time > 0 (e.g. 7 stops for 12002) or all recorded stops (87 entries including passing junctions).
- **Dwell Time Transparency Note:** Explicit disclosure confirms: *"These labels describe timetable data only. They do not confirm whether passenger boarding or deboarding is permitted."*
- **Stoppage Table:** Shows stop sequence, station code, station name, arrival time, departure time, halt duration pill (e.g. `3 min`, `8 min`), and cumulative distance.

### 3.3 Intermediate Halts in Journey Discovery (`IntermediateStopsList.tsx`)
- Embedded into `RouteCard.tsx`, `TransitTimeline.tsx`, and `JourneyDetailsModal.tsx`.
- Displays expandable intermediate halt count and disclosure button.
- Asynchronously slices schedule between the specific leg boarding and arrival stations.
- Non-stop legs clearly state: *"Non-stop direct leg: No intermediate scheduled halts recorded between X and Y"*.

### 3.4 Navigation & Deep Linking (`Navbar.tsx` & `page.tsx`)
- Added dedicated **"Timetable"** mode tab to navigation bar and hero mode selector.
- URL parameters automatically synchronized (`?mode=timetable&train=12002`).
- Deep links allow bookmarking or sharing specific train schedules directly.

---

## 4. Verification & Testing

### 4.1 Backend Pytest Suite
- **API Unit & Integration Tests:** `backend/tests/unit/api/test_trains_api.py` (6 tests covering search, details, complete schedules, sliced stops, halt durations, and 404 quarantine responses).
- **Full Backend Regression Suite:**
  ```text
  ======================== 240 passed in 80.77s ========================
  ```
  100% of all 240 backend unit and integration tests passed with zero failures.

### 4.2 Frontend Next.js Production Build
- Ran `next build` inside the Docker container:
  ```text
  ✓ Compiled successfully
  ✓ Linting and checking validity of types
  ✓ Generating static pages (4/4)
  ✓ Finalizing page optimization
  ```
  Zero TypeScript errors, zero lint warnings.

### 4.3 Browser End-to-End Testing (Puppeteer)
Executed real browser-driven E2E tests against Chromium:
1. **`train_schedule_flow.e2e.mjs`**:
   - Navigated to `http://localhost:3000`.
   - Switched to "Train Timetable" inspector mode.
   - Searched train `12002` (Bhopal Shatabdi).
   - Verified timetable header, TAG Table 3A citation, origin NDLS, destination BPL.
   - Verified operating days strip (7 active daily chips).
   - Verified 7 scheduled halts; toggled to all 87 recorded stops.
   - Switched to Connecting Routes, searched BCT $\rightarrow$ NDLS, expanded intermediate stops in leg timeline, and opened Journey Details Modal.
   - **Result:** PASSED (Exit code 0).
2. **`journey_flow.e2e.mjs`**:
   - Tested route search, sorting, modal, comparison matrix, and mobile viewport.
   - **Result:** PASSED (Exit code 0).
3. **`bachelor_flow.e2e.mjs`**:
   - Tested Bachelor Special vacancy discovery, berth segment continuity, and mobile viewport.
   - **Result:** PASSED (Exit code 0).

---

## 5. Visual Evidence Artifacts

| Artifact | Path | Description |
|---|---|---|
| Timetable Schedule View | `e2e_train_schedule_view_success.png` | Screenshot of Train 12002 timetable with TAG table badge, operating days strip, and stoppage table. |
| Intermediate Stoppage Timeline | `e2e_route_intermediate_stops_success.png` | Screenshot of journey search results with expanded intermediate stoppage timeline and halt duration pills. |

---

## 6. Zero-Fabrication Compliance Check

- [x] **No Invented Platform Numbers:** Platforms are not rendered as facts unless verified in official feeds; clear disclaimer explains platform confirmation occurs at stations.
- [x] **No Fabricated Operating Days:** Running days derive strictly from the 164 TAG 2024–2026 verified calendar records audited in TW-109.
- [x] **No Invented Halts:** Stoppage records come directly from compiled schedule data without synthetic filler.
- [x] **Honest Dwell vs Recorded Stop Distinction:** Explicit toggle differentiates scheduled halts (dwell > 0) from all recorded stops without overclaiming commercial passenger boarding permission.
- [x] **Awaiting Schedule Disclosure:** Quarantined or uncompiled trains return an explicit `AWAITING_VERIFIED_SCHEDULE` message rather than synthetic timetables.

---

## 7. Post-Implementation Terminology Correction (TW-110 Addendum)

Following focused data-integrity audit:
1. **`TrainScheduleView.tsx`:** Renamed "Commercial Halts" to "Scheduled Halts" and "All Stops" to "All Recorded Stops". Added explicit disclosure: *"These labels describe timetable data only. They do not confirm whether passenger boarding or deboarding is permitted."* Rendered neutral `0 min` dwell for zero-halt stops rather than unverified technical waypoint labels.
2. **`IntermediateStopsList.tsx`:** Replaced claims of verified commercial passenger halts with honest "Scheduled halts" and "Recorded stops" terminology.
3. **`trains.py`:** Documented that `only_commercial` filters by positive scheduled dwell time (halt > 0) rather than certified commercial booking quotas.

---

## 8. Conclusion

Milestone **TW-110** is fully implemented, audited, verified across unit, integration, build, and browser E2E test suites, and adheres strictly to TripWiser's engineering standards.
