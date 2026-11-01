# TW-106 Implementation Plan — Journey Details & Route Experience Enhancement

## 1. Inspection & High-Value Enhancement Areas

### Current Baseline (TW-105)
- Search console supports station autocomplete, swapping, relative dates, and 0/1 transfer mode.
- Results stream lists candidate routes (`RouteCard.tsx`) with an expandable `TransitTimeline.tsx`.
- Sorting filters (`recommended`, `fastest`, `fewest_transfers`, `cheapest`) handle commercial feed deferral honestly.
- All real data is backed by 8 compiled domain trains and 8,697 stations.

### Critical Gaps Addressed in TW-106
1. **Journey Details Modal & Itinerary Utility**:
   - Currently, expanding a card only shows departure/arrival times in an inline box.
   - Travelers need deep journey clarity: full transit path, train classification (e.g. Rajdhani Superfast), operating day confirmation, departure/arrival day of week, total elapsed journey time vs moving time, and an actionable "Share / Save Itinerary" feature.
2. **Transfer Experience & Interchange Intelligence**:
   - For 1-transfer routes (e.g. Mumbai to Delhi via TKJ or Kota), users need clear interchange advisories:
     - Waiting buffer assessment: `Comfortable Layover` (60m–180m), `Tight Connection` (30m–45m), or `Extended Layover` (> 180m).
     - Next-train departure prominence with countdown / timeline clarity.
     - Honest railway station platform disclosure: *"Platforms are designated dynamically on the date of travel via station master display boards; never rely on unverified static platform assignments."*
3. **Route Comparison & Quick Differential Metrics**:
   - When multiple routes are returned (direct vs 1-transfer), users need an at-a-glance comparison:
     - Quick comparison drawer/matrix comparing duration difference (e.g., *"Direct Rajdhani saves 1h 25m"*), total stops, and layovers.
4. **Nearby Boarding Station Recommendations**:
   - When searching major metropolitan clusters (e.g., Delhi, Mumbai), passengers frequently miss trains departing from twin/satellite stations (e.g., `NZM` or `DLI` for `NDLS`, `BDTS` or `CSMT` for `BCT`).
   - A contextual `NearbyAlternativesBanner` will suggest relevant twin terminal options with 1-click search re-triggering.
5. **Browser-Based E2E Testing**:
   - Real browser user interaction testing using `puppeteer-core` driving the local Chrome/Edge engine against the running Next.js app on `http://localhost:3000`.

---

## 2. Component Architecture & Planned Files

| Component / File | Purpose |
|---|---|
| `frontend/src/components/results/JourneyDetailsModal.tsx` | Comprehensive full-screen / drawer modal displaying complete journey breakdown, train details, schedule provenance, layover advisory, and share/print itinerary controls. |
| `frontend/src/components/results/TransferAdvisoryBadge.tsx` | Visual indicator classifying transfer buffer windows (Comfortable, Tight, Extended) with actionable travel advice. |
| `frontend/src/components/results/RouteComparisonMatrix.tsx` | At-a-glance comparative card/drawer contrasting direct vs connecting route options (time saved, transfer count, departure spread). |
| `frontend/src/components/results/NearbyAlternativesBanner.tsx` | Contextual recommendation ribbon surfacing nearby metropolitan twin boarding stations (e.g. NZM for NDLS, BDTS for BCT) with 1-click re-query. |
| `frontend/src/components/results/RouteCard.tsx` | Enhanced with deep-details trigger button, transfer advisory pill, and differential comparison chips. |
| `frontend/src/components/results/TransitTimeline.tsx` | Enhanced with platform dynamic guidance callout and next-train continuity markers. |
| `frontend/src/components/results/ResultsStream.tsx` | Integrated with comparison matrix and nearby alternatives banner. |
| `frontend/tests/e2e/journey_flow.e2e.js` | Browser-based E2E test script testing autocomplete, route search, card expansion, modal opening, and sorting toggles. |

---

## 3. Detailed Feature Specifications

### 1. Journey Details Modal
- **Trigger**: "Full Journey Details & Itinerary" button on each route card.
- **Header**: Route badge, origin ➔ destination, total duration, distance in km.
- **Train Section**:
  - Official Train Name & Number.
  - Timetable status: `Timetable Confirmed`.
  - Runs On Days: Verified day-of-week schedule.
  - Departure & Arrival: Full date, formatted 24h timestamp, station code & name.
- **Transfer Interchange Section** (for connecting routes):
  - Layover station name and code.
  - Transfer buffer duration with comfort rating badge.
  - Transfer advice: *"Proceed to connecting concourse upon arrival. Check electronic display boards for live platform updates."*
- **Action Bar**:
  - "Copy Route Summary": Copies clean text itinerary to clipboard.
  - "Print Itinerary": Opens browser print dialog.

### 2. Transfer Experience & Next-Train Cohesion
- Transfer comfort classification logic:
  - $30 \le \Delta T < 45$ min: `Tight Connection` (amber pill, advisory warning).
  - $45 \le \Delta T \le 180$ min: `Comfortable Layover` (olive pill, optimal buffer).
  - $> 180$ min: `Extended Layover` (slate pill, long buffer).
- Explicit platform policy: Transparently states that platforms are dynamic in Indian Railways and strictly avoids fabricating static platform numbers.

### 3. Route Comparison Matrix
- Appears when $\ge 2$ routes exist.
- Displays key comparative metrics:
  - Fastest option vs Recommended option.
  - Time delta (e.g. `+85m` compared to fastest).
  - Transfer penalty breakdown.

### 4. Nearby Boarding & Alternative Stations
- Recognizes metropolitan twin hub clusters:
  - Delhi NCR: `NDLS`, `NZM`, `DLI`, `ANVT`.
  - Mumbai: `BCT`, `BDTS`, `CSMT`, `LTT`.
  - Kolkata: `HWH`, `SDAH`.
- If user searches an origin in one of these clusters, offers one-click shortcuts to explore routes from twin terminals using existing real database timetable records.

---

## 4. Implementation & Verification Sequence

1. **Phase 1: Transfer & Journey Components**
   - Create `TransferAdvisoryBadge.tsx`.
   - Create `JourneyDetailsModal.tsx`.
   - Update `TransitTimeline.tsx` and `RouteCard.tsx`.
2. **Phase 2: Route Comparison & Nearby Alternatives**
   - Create `RouteComparisonMatrix.tsx`.
   - Create `NearbyAlternativesBanner.tsx`.
   - Integrate into `ResultsStream.tsx` and `page.tsx`.
3. **Phase 3: Browser-Based E2E Testing**
   - Write `frontend/tests/e2e/journey_flow.e2e.js` using `puppeteer-core`.
   - Execute against running app (`http://localhost:3000`), testing real user search interactions, dropdown selection, card interaction, and modal opening.
4. **Phase 4: Full Regression & Verification**
   - Run backend test suite (211 tests).
   - Run frontend production build (`npm run build`).
   - Run E2E test script.
5. **Phase 5: Commit & Report**
   - Create `TW106_COMPLETION_REPORT.md` (and artifact).
   - Stage and commit with message: `feat(routes): enhance journey details and route comparison experience`.

