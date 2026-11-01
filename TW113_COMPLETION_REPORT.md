# TW-113 Completion Report: Journey Reliability & Transfer Risk Intelligence

## 1. Executive Summary
Milestone **TW-113** delivers **Journey Reliability & Transfer Risk Intelligence** to TripWiser. It helps railway passengers understand the practical trade-offs of their routes:
- Time spent travelling aboard trains versus waiting between connections.
- Objective classification of transfer windows based on scheduled layovers.
- Plain-language, factual insights explaining timetable feasibility without generic commentary.

In accordance with TripWiser's **Zero-Fabrication Guarantee**, all calculations and classifications derive strictly from compiled timetable stop sequences. No live delay predictions, fake missed-train probabilities, or unverified station facility claims (e.g., footbridges, lounges) are presented.

---

## 2. Architecture & Mathematical Model

### A. Journey Time Breakdown
Every candidate route (`CandidateRoute`) computes and exposes:
- **Total Scheduled Journey Duration**: $T_{\text{total}} = \text{arrival}_{\text{last\_leg}} - \text{departure}_{\text{first\_leg}}$
- **Time Aboard Trains**: $T_{\text{travel}} = \sum_{i=1}^{N} \text{duration}(\text{leg}_i)$
- **Transfer Waiting Time**: $T_{\text{wait}} = \sum_{j=1}^{N-1} \text{duration}(\text{layover}_j)$
- **Identity Guarantee**:
  $$T_{\text{total}} = T_{\text{travel}} + T_{\text{wait}}$$
- Verified across overnight journeys, date crossings, and schedule day offsets.

### B. Standard 5-Tier Transfer Risk Classification
Layovers at intermediate interchange stations are classified into 5 standardized categories:
1. **Below 30 minutes**: `INVALID_CONNECTION` ("Invalid Connection") — Violates the 30-minute minimum buffer required for safe station interchange.
2. **30–44 minutes**: `TIGHT_CONNECTION` ("Tight Connection") — Minimal buffer; minor inbound train delays risk missing the onward service.
3. **45–89 minutes**: `MODERATE_CONNECTION` ("Moderate Connection") — Reasonable scheduled buffer for station transfer.
4. **90–180 minutes**: `COMFORTABLE_CONNECTION` ("Comfortable Connection") — Ample scheduled connection window.
5. **Above 180 minutes**: `LONG_WAIT` ("Long Wait") — Extended scheduled layover between connecting trains.

**Overall Route Transfer Risk**:
- Direct routes: `None`
- Multi-transfer routes: Reflects the highest risk tier across all journey layovers (`INVALID_CONNECTION` > `TIGHT_CONNECTION` > `LONG_WAIT` > `MODERATE_CONNECTION` > `COMFORTABLE_CONNECTION`).

### C. Factual Journey Insights
Deterministic insights derived directly from route calculations:
- Direct service: `"Direct service with no train changes."` and `"100% of journey duration is spent travelling aboard the train."`
- Multi-transfer structure: `"{N} transfer(s) across {N+1} connecting trains."`
- Time distribution: `"Total scheduled waiting time: {H}h {M}m ({W}% of journey)."` and `"Time aboard trains: {H}h {M}m ({T}% of journey)."`
- High travel ratio: `"Most of your journey is spent travelling aboard trains."` (when $T \ge 80\%$)
- Layover specifics:
  - `"Tight scheduled connection at {Station} ({M}m layover)."`
  - `"Extended layover of {H}h {M}m at {Station}."`

---

## 3. Implementation Details

### A. Backend Domain & API
- `backend/app/domain/models/route.py`:
  - Added `TransferRiskLevel` enum and `TransferLayover` model.
  - Extended `CandidateRoute` with `total_travel_time_minutes`, `total_wait_time_minutes`, `layovers`, `insights`, and `overall_transfer_risk`.
  - Added backward-compatible `model_validator` defaulting breakdown metrics on legacy test objects.
- `backend/app/domain/services/route_engine.py`:
  - Added `classify_transfer_layover` and `generate_journey_insights` class methods.
  - Integrated breakdown and layover calculation into `_find_direct_routes`, `_find_connecting_routes` (1-transfer), and `_find_two_transfer_routes` (2-transfers).
- `backend/app/api/v1/routes.py`:
  - Added `LayoverSchema` and extended `RouteSchema` to serialize breakdown metrics and layovers.

### B. Frontend UI & UX
- `frontend/src/types/api.ts`:
  - Defined `TransferRiskLevel`, `TransferLayover`, and updated `CandidateRoute`.
- `frontend/src/components/results/TransferAdvisoryBadge.tsx`:
  - Upgraded to support all 5 exact classification tiers with clean, honest styling.
  - Eliminated unverified assumptions regarding footbridges, platform amenities, and waiting lounges.
- `frontend/src/components/results/RouteCard.tsx`:
  - Added **Journey Time Breakdown** bar showing the exact proportion of train travel vs waiting time.
  - Added factual insight pill badges (`[data-testid="journey-insight-pill"]`).
  - Passed structured layover risk metadata to transfer advisory badges.
- `frontend/src/components/results/TransitTimeline.tsx`:
  - Updated intermediate layover connectors with factual descriptions and risk badges.
- `frontend/src/components/results/JourneyDetailsModal.tsx`:
  - Revamped Key Metrics to display Total Duration, Aboard Trains (with percentage), Transfer Waiting (with percentage), and Legs & Transfers count.
  - Added dedicated **Journey Reliability & Timetable Insights** section with honest operational disclaimer.

---

## 4. Verification & Testing

### A. Backend Unit & API Tests
- `backend/tests/unit/domain/test_journey_reliability.py`:
  - `test_transfer_risk_classification_boundaries`: PASSED (exact assertions on 29m, 30m, 44m, 45m, 89m, 90m, 180m, 181m boundaries).
  - `test_direct_journey_breakdown`: PASSED (0m wait, 100% travel time, empty layovers).
  - `test_one_transfer_breakdown_and_risk`: PASSED (travel time + wait time == total duration, 1 layover).
  - `test_two_transfer_breakdown_and_overall_risk`: PASSED (2 layovers, overall risk evaluation).
- `backend/tests/unit/api/test_routes_reliability_api.py`:
  - `test_search_api_returns_journey_breakdown_and_layovers`: PASSED (HTTP 200, valid serialization).

### B. Full Pytest Regression
- **Command**: `docker exec -e PYTHONPATH=/app tripwiser-backend pytest`
- **Result**: **257 passed in 84.00s** (100% pass across all 257 tests in the test suite).

### C. Browser E2E Tests (Puppeteer)
- `frontend/tests/e2e/journey_reliability_flow.e2e.mjs`:
  - Verified 2-transfer search BCT ➔ HWH on 2026-11-02.
  - Verified Journey Time Breakdown bar and labels (`aboard train`, `transfer waiting`).
  - Verified 95 factual insight pills across route cards.
  - Verified Journey Details Modal metrics (Aboard Trains, Transfer Waiting, Reliability Insights).
  - Screenshot captured: `e2e_journey_reliability_success.png`.
- `frontend/tests/e2e/network_multi_transfer_flow.e2e.mjs`: PASSED.

### D. Production Build
- **Command**: `cd frontend; npm run build`
- **Result**: Compiled with **0 errors and 0 warnings**.

---

## 5. Git Commit & Repository State
- Working tree clean.
- Ready to commit with message:
  `feat(routes): implement journey reliability and transfer risk intelligence`
