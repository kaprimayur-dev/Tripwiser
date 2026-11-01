# TW-114 Completion Report: Passenger Journey Experience & Search Refinement

## 1. Executive Summary
**Milestone**: TW-114 — Passenger Journey Experience & Search Refinement  
**Scope**: Improve the end-to-end passenger journey search, comparison, saving, and sharing experience across TripWiser while preserving existing domain architecture, timetable data integrity, and multi-transfer routing capabilities.  
**Commit**: `feat(frontend): improve passenger journey experience and search`  

---

## 2. Features Delivered & User Flows Improved

### A. Journey Search Experience & Autocomplete
- **Station Autocomplete Refinement** ([`StationAutocomplete.tsx`](file:///c:/projects/tripwiser/frontend/src/components/search/StationAutocomplete.tsx)):
  - Prominent monospace code badge alongside city and state descriptions.
  - Dropdown options include `data-station-code` attributes, accessible minimum tap targets (>= 44px), and keyboard arrow navigation.
  - Clear selection button ("X") that clears selection and focuses input.
- **Origin/Destination Station Swap** ([`JourneySearchCard.tsx`](file:///c:/projects/tripwiser/frontend/src/components/search/JourneySearchCard.tsx)):
  - Added dedicated swap action (`#btn-swap-stations`) with smooth CSS rotation feedback.
  - Instantly interchanges boarding and arrival stations while preserving journey date and transfer settings.
- **Graceful Validation**:
  - Catches empty boarding/arrival fields and identical origin/destination selections (`#search-validation-error`) with clear inline warnings ("Origin and destination stations cannot be identical").
  - Prevents invalid submissions while keeping UI responsive.

### B. Route Discovery & Transfer Filtering
- **Transfer Count Filter Pills** ([`SortingFilterBar.tsx`](file:///c:/projects/tripwiser/frontend/src/components/results/SortingFilterBar.tsx)):
  - Added filter pills: `All Routes ({n})`, `Direct Only ({n})`, `1 Transfer ({n})`, and `2 Transfers ({n})`.
  - Enables passengers to instantly filter results without triggering redundant network calls.
- **Enhanced Visual Distinction on Route Cards** ([`RouteCard.tsx`](file:///c:/projects/tripwiser/frontend/src/components/results/RouteCard.tsx)):
  - Distinct styling for **Direct Services** (olive border and badge), **1-Transfer Routes** (terracotta badge), and **Multi-Transfer Routes** (espresso/indigo badge).
  - Clear timetable vs. live status notice: *"Scheduled Timetable Records — Live seat status and delay feeds deferred"*.

### C. Saved Journeys ("My Trips")
- **Lightweight Client-Side Persistence** ([`savedTrips.ts`](file:///c:/projects/tripwiser/frontend/src/lib/savedTrips.ts)):
  - Stores user itineraries in `localStorage` (`TRIPWISER_SAVED_TRIPS`) with duplicate prevention using deterministic composite IDs (`{ORIGIN}_{DEST}_{DATE}_{ROUTEID}`).
  - Dispatches `tripwiser:saved-trips-updated` event for real-time reactivity across components without full page reloads.
- **My Trips View** ([`SavedTripsView.tsx`](file:///c:/projects/tripwiser/frontend/src/components/trips/SavedTripsView.tsx)):
  - Accessible via header tab (`#nav-saved-trips-tab`) with a live badge showing the count of saved trips.
  - Shows travel time, transfer waiting time, train names/numbers, and overall connection risk.
  - **"Check Current Schedule & Search"** action immediately restores the route search with current timetable operating days.
  - One-click share and remove actions.
  - Honest timetable disclaimer reminding passengers that saved trips reflect timetable snapshots and should be rechecked for current operating days.

### D. Shareable Journey URLs
- **URL Parameter Preservation** ([`shareUrl.ts`](file:///c:/projects/tripwiser/frontend/src/lib/shareUrl.ts) & [`page.tsx`](file:///c:/projects/tripwiser/frontend/src/app/page.tsx)):
  - "Share Link" action copies shareable URL to clipboard with fallback and confirmation toast.
  - Generates URLs preserving search parameters: `?mode=connecting&origin=NDLS&destination=BPL&date=2026-11-04&transfers=0&sort=fastest`.
  - Avoids exposing internal database IDs.
  - Automatic restoration and execution of route searches on page load/refresh.
  - Robust error handling: invalid station codes or dates display a dismissible warning banner (`#url-validation-banner`) without crashing the application.

### E. Mobile-First Experience
- Fully audited on 375x667 (iPhone SE) and responsive viewports:
  - Form layout stacks cleanly with swap button centered between inputs.
  - Eliminated horizontal scroll overflow (`document.documentElement.scrollWidth <= window.innerWidth`).
  - Accessible touch targets across all interactive buttons (>= 44px min-height).

---

## 3. Verification & Test Results

1. **Next.js Production Build**:
   - `npm run build`: Compiled with **0 errors and 0 warnings**.
2. **Browser E2E Passenger Experience Test** ([`passenger_experience_flow.e2e.mjs`](file:///c:/projects/tripwiser/frontend/tests/e2e/passenger_experience_flow.e2e.mjs)):
   - **PASSED** in 18.2s across all 13 test scenarios:
     1. Origin/Destination station autocomplete and selection (BCT, HWH).
     2. Station swap button inversion and restoration.
     3. Identical station validation error handling.
     4. Route search with 2 transfers returning 20 route cards.
     5. Transfer filtering in SortingFilterBar (1-transfer filter verified).
     6. Save journey bookmark toggle and Navbar badge count increment (0 ➔ 1).
     7. My Trips view rendering saved itinerary cards.
     8. Recheck search restoring search console and executing query.
     9. Shareable URL parameter restoration (NDLS ➔ BPL on 2026-11-04).
     10. Invalid station code graceful banner warning.
     11. Mobile viewport test (375x667): verified zero horizontal scroll overflow.
     12. Desktop full-page screenshot captured: [`e2e_passenger_experience_desktop.png`](file:///c:/projects/tripwiser/frontend/tests/e2e/e2e_passenger_experience_desktop.png).
     13. Mobile screenshot captured: [`e2e_passenger_experience_mobile.png`](file:///c:/projects/tripwiser/frontend/tests/e2e/e2e_passenger_experience_mobile.png).
3. **Regression E2E Tests**:
   - [`journey_reliability_flow.e2e.mjs`](file:///c:/projects/tripwiser/frontend/tests/e2e/journey_reliability_flow.e2e.mjs): **PASSED** (zero regression on journey time breakdown and transfer risk).
   - [`network_multi_transfer_flow.e2e.mjs`](file:///c:/projects/tripwiser/frontend/tests/e2e/network_multi_transfer_flow.e2e.mjs): **PASSED** (zero regression on 2-transfer discovery and corridor interchange hubs).

---

## 4. Known Limitations & Honest Boundaries
- **Timetable Snapshot in Saved Trips**: Saved trips persist the route metadata locally. Because train running calendars may change across railway publication schedules, passengers are explicitly prompted to use "Check Current Schedule" to re-verify operating days.
- **Client-Side Persistence Scope**: Saved trips are bound to the user's current browser profile via `localStorage`. Cross-device syncing requires user accounts, which is intentionally deferred in accordance with milestone constraints.
