# Milestone Completion Report: TW-115 — Data Quality & Passenger Trust

**Milestone**: TW-115 — Railway Data Quality Validation, Quarantine Audit, and Passenger Trust Layer  
**Date**: November 2, 2026  
**Status**: COMPLETE & VERIFIED  
**Git Commit**: `feat(data): implement railway data quality and trust engine`  
**Audit Reproducibility Checksum (SHA-256)**: `bd76cfaf219516dd40310729c172a2d34b5dfbdd8a797c54b8fd5ad53c8732e9`

---

## 1. Executive Summary
TripWiser's railway intelligence system now features an institutional-grade **Data Quality & Passenger Trust Engine**. The system performs rigorous, deterministic data-quality audits across stations, trains, timetable stops, and operating calendars without fabricating missing records or silently altering source documents.

The engine classifies records into 4 deterministic quality statuses (`VALID`, `REJECTED`, `REVIEW_REQUIRED`, `RETAINED_INCOMPLETE`) across 4 severity levels (`CRITICAL`, `ERROR`, `WARNING`, `INFO`). An administrative CLI tool audits the entire dataset, outputs machine-readable JSON and human-readable Markdown reports, and computes a cryptographically stable SHA-256 checksum across all emitted findings.

---

## 2. Comprehensive Audit Results (34,182 Records Inspected)

The administrative audit CLI (`python -m app.cli.audit_data_quality --format both`) inspected **34,182 total records** across all source files:

| Record Category | Total Inspected | Valid | Retained Incomplete | Review Required | Rejected / Quarantined |
|---|---|---|---|---|---|
| **Stations** (`stations.json`) | 8,990 | 4,213 | 0 | 4,484 | 293 |
| **Trains** (`trains.json`) | 5,208 | 5,207 | 0 | 0 | 1 |
| **Train Schedules** (`schedules.json`) | 14,776 | 4,378 | 26 | 731 | 9,641 |
| **Running Calendars** (`railway_running_calendars.json`) | 5,208 | 192 | 0 | 5,016 | 0 |

### Findings by Severity
- **CRITICAL**: **293** (Fatal data errors: null or unparseable geometry coordinates, missing station code, missing train number).
- **ERROR**: **13** (Structural integrity failures: out-of-bounds geocoordinates, unresolved foreign station references, identical train endpoints, decreasing schedule day offsets).
- **WARNING**: **32,487** (Significant operational anomalies: missing state administration metadata, negative station dwell duration, trains awaiting verified official operating calendars).
- **INFO**: **305,825** (Timetable informational characteristics: 283,066 zero-dwell technical pass waypoints where arrival == departure time, 22,759 terminal endpoints or incomplete intermediate times, 22,561 missing day offsets).

### Top 10 Validation Failure Rules
1. `SCH_ZERO_DWELL_WAYPOINT`: **283,066** (Technical waypoints without passenger dwell)
2. `SCH_INCOMPLETE_TIMING`: **22,759** (Terminal stops or waypoints with missing time)
3. `SCH_MISSING_DAY_OFFSET`: **22,561** (Upstream records lacking explicit day offset)
4. `CAL_AWAITING_CALENDAR`: **5,016** (Trains awaiting official TAG running day verification)
5. `STN_MISSING_STATE`: **4,777** (Stations without state administration metadata)
6. `STN_NULL_GEOMETRY`: **293** (Quarantined stations with null coordinates)
7. `SCH_NEGATIVE_STATION_DWELL`: **112** (Inconsistent timetable entries where departure is before arrival)
8. `SCH_DEST_ENDPOINT_MISMATCH`: **16** (Last schedule stop does not align with train header destination)
9. `SCH_ANOMALOUS_DAY_OFFSET`: **6** (Day offset jumps > 3 days)
10. `SCH_ORIGIN_ENDPOINT_MISMATCH`: **5** (First schedule stop does not align with train header origin)

---

## 3. Core Architecture & Deliverables

### A. Data Quality Domain Model & Engine
- `backend/app/domain/models/data_quality.py`:
  - Structured enum definitions for `QualitySeverity`, `QualityStatus`, `RecordType`.
  - Pydantic models for `ValidationFinding`, `CategoryQualitySummary`, and `DataQualityAuditSummary`.
- `backend/app/domain/services/data_quality_engine.py`:
  - Reusable, deterministic validation methods for Stations, Train Headers, Train Schedules, and Operating Calendars.
  - India geodetic bounding box validation ($[6.0^\circ\text{N}-38.5^\circ\text{N}, 68.0^\circ\text{E}-98.5^\circ\text{E}]$).
  - Stop sequence strictly monotonic validator ($seq_i < seq_{i+1}$, no duplicates, no loops).
  - Checksum generator: Computes SHA-256 over deterministic JSON representation of all findings.

### B. Administrative Audit CLI & Reports
- `backend/app/cli/audit_data_quality.py`:
  - Standalone executable CLI supporting `--stations-file`, `--trains-file`, `--schedules-file`, `--calendars-file`, `--format json|md|both`, and `--out-dir`.
  - Generated reports:
    - `backend/data/reports/data_quality_report.json`
    - `DATA_QUALITY_REPORT.md` (root repository and artifact directory)

### C. Route Engine Defensive Protection
- `backend/app/domain/services/route_engine.py`:
  - Strictly isolates passenger journey discovery from unverified data.
  - Queries only compiled trains with verified operating calendars (`runs_on_days`).
  - Automatically rejects non-monotonic station sequences, stops with incomplete timing, negative durations, or transfers $< 30$ minutes.
  - Guarantees the mathematical identity: $\text{total\_duration} = \text{total\_travel\_time} + \text{total\_wait\_time}$.

### D. Passenger Trust & UI Transparency
- Passenger-facing components (`DataIntegrityBanner.tsx`, `RouteCard.tsx`, `TrainScheduleView.tsx`, `JourneyDetailsModal.tsx`) strictly describe timetable data as scheduled timetables rather than real-time tracking or seat feeds.
- Terminology strictly audited:
  - "Verified TAG Timetable"
  - "Scheduled Halts" (records with positive dwell time)
  - "All Recorded Stops" (complete timetable sequence including technical waypoints)
  - Explicit disclaimer: *"These labels describe timetable data only. They do not confirm whether passenger boarding or deboarding is permitted."*
  - "Fares Deferred" and "Seat Availability Deferred" pills prominently displayed.

---

## 4. Test Suite & Verification Results

1. **Data Quality Engine Unit Tests** (`backend/tests/unit/domain/test_data_quality_engine.py`):
   - 5 comprehensive test suites covering station integrity, train header constraints, timetable sequence rules, running calendar verification, and checksum reproducibility. **All passed**.
2. **Route Engine Quality Protection Tests** (`backend/tests/unit/domain/test_route_engine_quality_protection.py`):
   - 5 test suites verifying non-operating train rejection, non-monotonic sequence rejection, incomplete stop timing rejection, invalid connection layovers ($<30\text{m}$), and total duration mathematical identity. **All passed**.
3. **Full Backend Regression Suite**:
   - **267 passed in 90.55s** (100% pass rate across entire codebase).
4. **Frontend Production Build**:
   - Next.js 14.1.0 production build: **Compiled successfully with zero TypeScript or linting errors**.
5. **E2E Browser Journey Flow**:
   - Full browser test (`passenger_experience_flow.e2e.mjs`) verified station autocomplete, swap, validation errors, route search, 1-transfer filter, bookmarks, URL parameter restoration, invalid station warnings, and responsive mobile layouts.

---

## 5. Known Boundaries & Honest Limitations
- **Data Freshness Policy**: The dataset is compiled from public DataMeet snapshots and official Indian Railways Trains at a Glance (TAG 2024-2026) publication tables. Because upstream source files do not supply dynamic HTTP last-modified timestamps per record, freshness reflects documented publication release dates rather than real-time streaming updates.
- **Seat Availability & Commercial Fares**: Real-time reservation status and fare breakdowns require proprietary commercial railway feeds. Rather than fabricating placeholder prices or availability counts, TripWiser explicitly marks these feeds as deferred and displays clear trust disclaimers.
