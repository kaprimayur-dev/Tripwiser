# TW-113 Implementation Plan: Journey Reliability & Transfer Risk Intelligence

## 1. Executive Objective
Help railway passengers understand practical trade-offs of journeys:
- How much time is spent travelling aboard trains vs waiting at interchange stations?
- How long will they wait between trains, and how are scheduled connection windows classified?
- Are there timetable limitations passengers should be aware of?

This is **strictly timetable-data-backed intelligence**, not live delay prediction, fake probabilities, or unverified facility claims.

---

## 2. Core Architecture & Mathematical Definitions

### A. Journey Time Breakdown
For every `CandidateRoute`:
- $\text{total\_duration\_minutes} = \text{arrival\_time}_{\text{last\_leg}} - \text{departure\_time}_{\text{first\_leg}}$
- $\text{total\_travel\_time\_minutes} = \sum_{i=1}^{N} \text{duration\_minutes}(\text{leg}_i)$
- $\text{total\_wait\_time\_minutes} = \sum_{j=1}^{N-1} \text{duration\_minutes}(\text{layover}_j)$
- Identity Guarantee:
  $$\text{total\_duration\_minutes} = \text{total\_travel\_time\_minutes} + \text{total\_wait\_time\_minutes}$$

### B. Transfer Risk Classification
Given a scheduled transfer window $T_{\text{layover}}$ in minutes at an interchange station:
1. $T_{\text{layover}} < 30$: `INVALID_CONNECTION` ("Invalid Connection") — Violates minimum connection buffer.
2. $30 \le T_{\text{layover}} \le 44$: `TIGHT_CONNECTION` ("Tight Connection") — Minimal scheduled buffer. Delays to inbound train risk onward service.
3. $45 \le T_{\text{layover}} \le 89$: `MODERATE_CONNECTION` ("Moderate Connection") — Reasonable scheduled buffer for station transfer.
4. $90 \le T_{\text{layover}} \le 180$: `COMFORTABLE_CONNECTION` ("Comfortable Connection") — Ample scheduled connection window.
5. $T_{\text{layover}} > 180$: `LONG_WAIT` ("Long Wait") — Extended layover between connecting services.

Overall Route Transfer Risk ($\text{overall\_transfer\_risk}$):
- Direct journeys: `None`
- Multi-leg journeys:
  - If any transfer is `INVALID_CONNECTION`: `INVALID_CONNECTION`
  - Else if any transfer is `TIGHT_CONNECTION`: `TIGHT_CONNECTION`
  - Else if any transfer is `LONG_WAIT`: `LONG_WAIT`
  - Else if any transfer is `MODERATE_CONNECTION`: `MODERATE_CONNECTION`
  - Else: `COMFORTABLE_CONNECTION`

### C. Factual Journey Insights
Factual, calculated insights generated deterministically:
- Direct service: `"Direct service with no train changes."`
- Transfer breakdown: `"{transfers} transfer(s) across {legs} trains."`
- Time distribution: `"Total scheduled waiting time: {format_duration(wait_time)} ({wait_pct}% of journey)."`
- High travel ratio: `"Most of this journey ({travel_pct}%) is spent travelling aboard trains."` (if $travel\_pct \ge 80\%$)
- Connection warnings:
  - `"Includes a tight scheduled connection at {station} ({dur}m layover)."`
  - `"Extended layover of {dur} at {station} between connecting trains."`

---

## 3. Data Models & API Contracts

### A. Python Domain Models (`backend/app/domain/models/route.py`)
- `TransferRiskLevel` Enum:
  `INVALID_CONNECTION = "INVALID_CONNECTION"`
  `TIGHT_CONNECTION = "TIGHT_CONNECTION"`
  `MODERATE_CONNECTION = "MODERATE_CONNECTION"`
  `COMFORTABLE_CONNECTION = "COMFORTABLE_CONNECTION"`
  `LONG_WAIT = "LONG_WAIT"`
- `TransferLayover` Model:
  - `interchange_station_code: str`
  - `arriving_train_number: str`
  - `departing_train_number: str`
  - `arrival_time: datetime.datetime`
  - `departure_time: datetime.datetime`
  - `duration_minutes: int`
  - `risk_level: TransferRiskLevel`
  - `risk_label: str`
  - `risk_description: str`
- `CandidateRoute` extensions:
  - `total_travel_time_minutes: int`
  - `total_wait_time_minutes: int`
  - `layovers: list[TransferLayover]`
  - `insights: list[str]`
  - `overall_transfer_risk: Optional[TransferRiskLevel]`

### B. FastAPI Schemas (`backend/app/api/v1/routes.py`)
- `TransferLayoverSchema`: Serializes layover details for clients.
- `RouteSchema`: Includes `total_travel_time_minutes`, `total_wait_time_minutes`, `layovers`, `insights`, `overall_transfer_risk`.

### C. Frontend TypeScript Types (`frontend/src/types/api.ts`)
- `TransferRiskLevel`
- `TransferLayover`
- `CandidateRoute` updated with breakdown fields.

---

## 4. Frontend UI Components

1. `TransferAdvisoryBadge.tsx`:
   - Updated to support all 5 exact classification labels.
   - Clean, neutral styling without unauthorized facility/footbridge assumptions.
2. `RouteCard.tsx`:
   - Display a compact **Journey Time Breakdown** bar / indicator showing travel time vs waiting time.
   - Display key journey insights tags.
3. `TransitTimeline.tsx`:
   - Updated transfer connectors displaying the exact risk label and scheduled layover duration.
4. `JourneyDetailsModal.tsx`:
   - Detailed Time Breakdown cards:
     - Total Journey Time
     - Time Aboard Trains
     - Transfer Waiting Time
     - Legs & Transfers Count
   - Bulleted "Journey Reliability & Timetable Insights" section with honest operational disclaimer.

---

## 5. Verification Plan

1. **Unit Tests**:
   - `backend/tests/unit/domain/test_journey_reliability.py`:
     - Test calculations for direct routes (0 wait time, 100% travel time).
     - Test 1-transfer routes (travel time + wait time == total duration).
     - Test 2-transfer routes (multiple layovers, midnight crossing, day offset).
     - Test boundary classifications (29m, 30m, 44m, 45m, 89m, 90m, 180m, 181m).
     - Test deterministic insights generation.
2. **API Tests**:
   - `backend/tests/unit/api/test_routes_reliability_api.py`: Verify JSON responses contain breakdown and layovers.
3. **Full Pytest Regression**:
   - Run `docker exec tripwiser-backend pytest` to verify 252+ tests.
4. **Browser E2E Flow**:
   - `frontend/tests/e2e/journey_reliability_flow.e2e.mjs`:
     - Puppeteer testing of Journey Time Breakdown and Transfer Risk badges on route cards and details modal.
5. **Production Build & Git Commit**:
   - `npm run build` with 0 errors.
   - Commit message: `feat(routes): implement journey reliability and transfer risk intelligence`.
