# TW-112 Implementation Plan: Train Network Intelligence & Multi-Transfer Route Discovery

## 1. Objectives & Architectural Context
TripWiser has cataloged 8,697 stations, 164 compiled trains, 23,602 schedule stops, and a working direct & 1-transfer journey search engine.
The objective of TW-112 is to:
1. Provide train network connectivity intelligence between any two stations (direct services, schedules, running days, intermediate halts, distances).
2. Discover interchange junction stations (both corridor-specific transfer hubs and network-wide interchange centers).
3. Safely extend route discovery to bounded multi-transfer journeys (**up to 2 transfers / 3 legs**), preserving operating-day accuracy, transfer buffer rules, loop avoidance, and zero-fabrication integrity.

## 2. Rationale for Maximum Transfer Limit (Max Transfers = 2)
- **Scale & Combinatorics:** With 164 trains and 23,602 schedule entries, 1-transfer has $O(T^2)$ combinations across $\approx 20$ hubs; 2-transfers has $O(T^3)$ combinations across hub pairs. 3-transfers ($O(T^4)$) would create millions of paths and impractical 48h+ journeys.
- **Real-World Feasibility:** In Indian Railways, 2 transfers (e.g. `PUNE -> KYN -> NDLS -> ASR`) comfortably bridges disparate regional corridors where no direct or single-junction train operates.
- **Safety & Performance:** Capping `max_transfers` at 2 guarantees sub-second response times, zero infinite loops, and strictly verified layover buffers (30m to 360m).

## 3. Implementation Steps

### Phase 2 & 3: Domain Models & Service Extension
- `backend/app/domain/models/network.py`:
  - `TrainConnectivity`: direct train service details between two stations.
  - `StationConnectivityResponse`: collection of direct train connections with stats.
  - `InterchangeStation`: junction metadata with inbound/outbound train counts.
- `backend/app/domain/services/route_engine.py`:
  - `_find_candidate_hub_pairs(origin_code, destination_code, limit=15)`: Indexed SQL join to discover intermediate `(hub1, hub2)` pairs.
  - `_find_two_transfer_routes(origin_code, destination_code, journey_date, min_transfer_minutes, max_transfer_minutes, limit=15)`: Constructs 3-leg journeys with transfer buffers and operating day validation.
  - `get_station_connectivity(origin_code, destination_code)`: Returns all direct trains between two stations.
  - `get_interchanges(origin_code=None, destination_code=None, limit=20)`: Discovers interchange hubs for a specific corridor or network-wide.

### Phase 4: API Endpoints
- `backend/app/api/v1/routes.py`:
  - `GET /api/v1/routes/search`: update docstring and support `max_transfers = 2`.
  - `GET /api/v1/routes/connectivity?origin_code={code}&destination_code={code}`: Returns station-to-station direct services.
  - `GET /api/v1/routes/interchanges?origin_code={code}&destination_code={code}&limit={limit}`: Discovers transfer hubs.

### Phase 5: Frontend UI
- `frontend/src/types/api.ts`: Add connectivity and interchange interfaces.
- `frontend/src/services/api.ts`: Add `getStationConnectivity` and `getInterchanges`.
- `frontend/src/components/search/JourneySearchCard.tsx`: Add connection option `Up to 2 Transfers`.
- `frontend/src/components/results/RouteCard.tsx` & `JourneyDetailsModal.tsx`: Handle `transfer_count = 2` labels (`2 TRANSFERS VIA HUB1, HUB2`) and layovers.
- `frontend/src/components/results/ResultsStream.tsx`: Surface discovered corridor interchange hubs.

### Phase 6: Verification & Testing
- Unit tests: `backend/tests/unit/domain/test_multi_transfer_route_engine.py`.
- Backend pytest full regression suite.
- Frontend production build (`npm run build`).
- Browser E2E test: `network_multi_transfer_flow.e2e.mjs`.
- Git commit & completion report.
