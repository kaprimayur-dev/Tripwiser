# TW-107 Completion Report: Bachelor Special — Berth Segment Discovery

**Milestone**: TW-107  
**Feature**: Bachelor Special (TripWiser Signature Berth Segment Discovery)  
**Status**: COMPLETED & VERIFIED  
**Date**: November 2026  
**Authors**: Antigravity Pair Programming Engine  

---

## 1. Executive Summary

Milestone **TW-107** delivers TripWiser's signature innovation: **Bachelor Special**, an intelligent berth segment discovery engine designed to solve the waitlist dilemma on Indian Railways. 

When through tickets between origin and destination are unavailable on popular trains, vacant berths frequently exist across intermediate station legs. Bachelor Special identifies and combines multiple vacant berth segments on the **same train and journey date**, creating a continuous, gapless itinerary from boarding station to destination without requiring passengers to change trains.

---

## 2. Core Engineering Capabilities Implemented

### A. Pure Domain & Algorithmic Layer
- **Domain Contracts Reused**: Built on existing frozen domain models [`BerthSegment`](file:///c:/projects/tripwiser/backend/app/domain/models/bachelor.py) and [`BachelorSpecialItinerary`](file:///c:/projects/tripwiser/backend/app/domain/models/bachelor.py), enforcing strict consecutive stop-sequence continuity ($e_i.\text{to\_seq} == e_{i+1}.\text{from\_seq}$ and $e_i.\text{to\_station} == e_{i+1}.\text{from\_station}$), single-train matching, and zero-gap validation.
- **DAG Path Discovery Engine ([`BachelorEngine`](file:///c:/projects/tripwiser/backend/app/domain/services/bachelor_engine.py))**:
  - Traverses the Directed Acyclic Graph of stop sequences from origin to destination.
  - Strict pruning: rejects non-consecutive segments, gaps, overlaps, wrong trains, and conflicting dates.
  - Depth-bounded search: caps itineraries at 4 segments ($\le 3$ berth relocations) for passenger practicality.
  - Multi-tier ranking: ranks itineraries by fewest berth changes first, followed by coach consistency (minimizing movement between coaches).

### B. Persistence Layer
- **Repository Interface ([`VacancyRepository`](file:///c:/projects/tripwiser/backend/app/domain/repositories/vacancy_repository.py))**: Pure domain abstraction for querying active vacancies.
- **Postgres Implementation ([`PostgresVacancyRepository`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/repositories/vacancy_repository.py))**:
  - Queries [`chart_vacancies`](file:///c:/projects/tripwiser/backend/app/infrastructure/database/models/vacancy.py) table.
  - Applies active expiry filters (`expires_at > func.now()`), status filters (`status = 'VACANT'`), travel class matching, and sequence window bounding (`from_sequence >= min_seq` and `to_sequence <= max_seq`).

### C. Orchestration Service & API
- **Service ([`BachelorSpecialService`](file:///c:/projects/tripwiser/backend/app/domain/services/bachelor_service.py))**:
  - Resolves candidate direct trains connecting the origin and destination stations.
  - Computes train start dates factoring in station schedule day offsets (`departure_date - timedelta(days=orig_stop.day_offset)`).
  - Filters trains operating on the requested day of week against `runs_on_days`.
  - Queries active vacancies and coordinates discovery via `BachelorEngine`.
  - Returns honest status states: `SUCCESS`, `NO_CHART_VACANCIES`, or `NO_DIRECT_TRAINS`.
- **API Router ([`GET /api/v1/bachelor/search`](file:///c:/projects/tripwiser/backend/app/api/v1/bachelor.py))**:
  - Validates endpoints, executes service, and returns structured `BachelorSpecialSearchResponse`.
  - Registered in [`backend/app/main.py`](file:///c:/projects/tripwiser/backend/app/main.py).

### D. Frontend Experience (Next.js 14)
- **Top-Level Feature Switcher**: Seamlessly toggles between "Connecting Route Discovery" and "Bachelor Special (Berth Segments)" in both [`Navbar.tsx`](file:///c:/projects/tripwiser/frontend/src/components/layout/Navbar.tsx) and [`page.tsx`](file:///c:/projects/tripwiser/frontend/src/app/page.tsx).
- **Search Console ([`BachelorSearchCard.tsx`](file:///c:/projects/tripwiser/frontend/src/components/bachelor/BachelorSearchCard.tsx))**: Station autocompletes with station swapping, journey date selection, and travel class filtering (3A, 2A, 1A, SL, CC).
- **Discovered Itinerary Cards ([`BachelorSpecialCard.tsx`](file:///c:/projects/tripwiser/frontend/src/components/bachelor/BachelorSpecialCard.tsx))**:
  - Visual timeline displaying boarding and deboarding stations for each segment.
  - Explicit Coach and Berth Number badges (e.g. `Coach B2, Berth 43 — Upper Berth`).
  - Color-coded **Berth Relocation Indicator** detailing exactly where to move (e.g. *"Berth Relocation at JHS: Move from B2-43 to B3-21. No train interchange."*).
  - Regulatory disclosure explaining that combined itineraries do not guarantee a single PNR.
- **Results Stream ([`BachelorSpecialStream.tsx`](file:///c:/projects/tripwiser/frontend/src/components/bachelor/BachelorSpecialStream.tsx))**:
  - Handles loading skeletons, error states, and un-charted states.
  - **Zero-Fabrication Assurance**: Educates passengers on the Indian Railways charting timeline ($\approx 4\text{ hours}$ before departure) and declares that TripWiser never manufactures fake berth numbers.

---

## 3. Verification & Test Evidence

### A. Backend Regression Suite (221 / 221 Passed)
```text
tests/integration/api/test_bachelor_api.py ....                          [  1%]
tests/integration/api/test_route_search_api.py ......                    [  4%]
tests/integration/database/test_batch_persistence.py ..                  [  5%]
tests/integration/database/test_orm_models.py ....                       [  7%]
tests/integration/database/test_station_repository.py .                  [  7%]
tests/integration/database/test_train_repository.py .                    [  8%]
tests/integration/database/test_vacancy_repository.py .                  [  8%]
tests/test_health.py ...                                                 [  9%]
tests/unit/adapters/test_datameet_schedule_adapter.py .................. [ 18%]
tests/unit/adapters/test_datameet_station_adapter.py ................... [ 30%]
tests/unit/adapters/test_datameet_train_adapter.py ..................... [ 48%]
tests/unit/cli/test_import_cli.py .....                                  [ 54%]
tests/unit/domain/test_availability_domain.py .......                    [ 57%]
tests/unit/domain/test_bachelor_domain.py ...............                [ 64%]
tests/unit/domain/test_bootstrap_fixture_domain.py ....................  [ 73%]
tests/unit/domain/test_route_domain.py ..............                    [ 79%]
tests/unit/domain/test_station_domain.py .......                         [ 82%]
tests/unit/domain/test_train_domain.py ..............                    [ 89%]
tests/unit/integration/test_railway_integration_service.py ..........    [ 93%]
tests/unit/manifest/test_manifest_service.py ...                         [ 95%]
tests/unit/services/test_bachelor_engine.py .....                        [ 97%]
tests/unit/services/test_route_engine.py ......                          [100%]

============================= 221 passed in 58.19s =============================
```

### B. Next.js Production Build
```text
Route (app)                              Size     First Load JS
┌ ○ /                                    20.9 kB         105 kB
└ ○ /_not-found                          882 B            85 kB
+ First Load JS shared by all            84.1 kB

○  (Static)  prerendered as static content
```

### C. Browser-Based Headless Chrome E2E Test ([`bachelor_flow.e2e.mjs`](file:///c:/projects/tripwiser/frontend/tests/e2e/bachelor_flow.e2e.mjs))
```text
🚀 Starting Browser-Based E2E Bachelor Special Search Test...
1. Navigating to http://localhost:3000... (HTTP 200)
2. Switching to Bachelor Special Mode...
✓ Successfully activated Bachelor Special search console.
3. Selecting Origin Station (GWL)...
✓ Selected origin station (GWL).
4. Selecting Destination Station (BPL)...
✓ Selected destination station (BPL).
5. Executing search without vacancies to assert zero-fabrication honest response...
✓ Zero-Fabrication disclosure rendered: true
6. Inserting test continuous vacancy records into database for train 12002...
✓ Successfully inserted 2 continuous test segments (GWL->JHS and JHS->BPL).
7. Re-running search with active vacancies...
✓ Discovered Bachelor Special itinerary card rendered!
8. Verifying Card Details:
   - 1 Berth Change Badge: true
   - Coach B2 Berth 43: true
   - Coach B3 Berth 21: true
   - Berth Relocation at JHS: true
   - Policy Disclaimer: true
9. Testing Mobile Viewport (375x812)...
✓ Captured mobile viewport screenshot: frontend/tests/e2e/e2e_bachelor_special_success.png
10. Cleaning up test database records...
✓ Database cleaned up.

🎉 ALL BROWSER-BASED E2E TESTS PASSED FOR BACHELOR SPECIAL! 🎉
```

---

## 4. Key Limitations & Regulatory Compliance

1. **Zero-Fabrication Principle**: Vacancies are only populated when real PRS chart releases exist. In the absence of an active chart window (e.g. journeys $>4\text{ hours}$ before departure), the system refuses to generate synthetic berth numbers and explicitly displays the charting timeline to passengers.
2. **Ticketing Disclaimer**: The platform makes no claim that combined itineraries can be booked under a single PNR. Passengers are advised to book individual segments or coordinate with the on-board TTE.
