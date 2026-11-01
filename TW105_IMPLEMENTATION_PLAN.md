# TW-105 Implementation Plan — TripWiser Frontend Experience

## 1. Current Frontend Assessment

### Existing Foundation
- **Framework & Tooling**: Next.js 14.1.0 (App Router), React 18, TypeScript 5.3, Tailwind CSS 3.4.
- **Installed Libraries**: `@tanstack/react-query` v5, `lucide-react`, `clsx`, `tailwind-merge`.
- **Current State**:
  - `src/app/page.tsx` contains a static, read-only placeholder search form with unlinked inputs.
  - No active state management, API services, or search result views.
  - `next.config.js` already configures an API rewrite proxy forwarding `/api/v1/:path*` to the backend (`http://localhost:8000` / `NEXT_PUBLIC_API_URL`), eliminating client CORS friction.
- **Inspiration Artifacts (`generated/stitch/`)**:
  - Warm editorial travel journal aesthetic: Archival cream canvas (`#F4EFE4`), Deep espresso (`#191612`), Burnt terracotta (`#B9532D`), and Muted olive (`#67664A`).
  - Typography: Epilogue (editorial headlines) paired with Plus Jakarta Sans (functional body & metrics).
  - Clean tactile cards with 1px border rules, timeline route nodes, transfer layover markers, and clear transit status chips.

---

## 2. Proposed Screen Structure

The frontend will be structured around an integrated, single-page reactive journey discovery workflow with deep linking (`/search?origin=...&destination=...&date=...&sort=...`):

```
┌────────────────────────────────────────────────────────────────────────┐
│ Top Navigation Bar                                                     │
│ [TripWiser Logo] ✦ Travel Intelligence      [Bachelor Special (Teaser)]│
├────────────────────────────────────────────────────────────────────────┤
│ Hero & Search Dispatch Console                                         │
│ "The direct route isn't the only route."                              │
│ ┌──────────────────────┐  [⇄ Swap]  ┌────────────────────────────────┐ │
│ │ Boarding From: [NDLS]│             │ Arriving At: [BCT]             │ │
│ └──────────────────────┘             └────────────────────────────────┘ │
│ ┌──────────────────────┐ ┌─────────┐ ┌───────────────┐ ┌─────────────┐ │
│ │ Date: [2026-11-05]   │ │Transfers│ │ Nearby Station│ │ Find Routes │ │
│ └──────────────────────┘ └─────────┘ └───────────────┘ └─────────────┘ │
├────────────────────────────────────────────────────────────────────────┤
│ Live Query Ribbon & Diagnostic Banner                                  │
│ NDLS ➜ BCT • Thu, 5 Nov • Timetable Confirmed • Fares Deferred Notice  │
├────────────────────────────────────────────────────────────────────────┤
│ Sorting & Filter Rail                                                  │
│ [✦ Recommended]  [⚡ Fastest]  [⤹ Fewest Transfers]  [₹ Cheapest (Def)] │
├────────────────────────────────────────────────────────────────────────┤
│ Results Stream                                                         │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ ✦ RECOMMENDED ROUTE  •  DIRECT                                     │ │
│ │ 12951 Mumbai Rajdhani Express                                      │ │
│ │ 16:40 NDLS ──────── 15h 52m (1384 km) ──────── 08:32 BCT (+1d)     │ │
│ │ Timetable Confirmed  •  Seat Availability Deferred                 │ │
│ │ [View Route Timeline ▾]                                            │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ 1 TRANSFER VIA KOTA JN  •  RECOMMENDED ALTERNATIVE                 │ │
│ │ Leg 1: 12953 (NDLS ➜ KOTA) • 75m Guaranteed Layover • Leg 2: ...  │ │
│ │ 17:15 NDLS ─── 4h 45m ─── 22:00 KOTA ─── 75m ─── 23:15 ─── 08:45  │ │
│ │ Platform Cluster Layover  •  Timetable Confirmed                   │ │
│ │ [View Transfer Details ▾]                                          │ │
│ └────────────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────┤
│ Trust & Provenance Footer                                              │
│ Real Indian Railways Timetable Data • Zero Fabrication Guarantee      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Architecture

All components will reside in `frontend/src/components/`:

### 1. `search/`
- **`JourneySearchCard.tsx`**: Main interactive console with origin/destination inputs, swap button, date picker, quick-date pills (Today, Tomorrow, Weekend), and max transfers selector.
- **`StationAutocomplete.tsx`**: Debounced dropdown calling `GET /api/v1/stations/search?q={query}`. Displays station name, code, city, and state. Supports keyboard navigation (Arrow keys + Enter).
- **`NearbyStationsModal.tsx`**: Modal/flyout displaying nearby stations within radius km using browser Geolocation or coordinates via `GET /api/v1/stations/nearby`.

### 2. `results/`
- **`ResultsStream.tsx`**: Renders candidate routes list or informative empty states with backend diagnostic reasons (`SAME_ORIGIN_DESTINATION`, `STATION_NOT_FOUND`, `TRANSFER_BUFFER_VIOLATION`, `NO_DIRECT_OR_CONNECTING_TRAINS`).
- **`RouteCard.tsx`**: Primary journey card presenting:
  - Route header with badges (`RECOMMENDED`, `DIRECT`, `1 CHANGE VIA [HUB]`).
  - Total duration, distance, and transfer count.
  - High-clarity transit graph showing departure, intermediate layover, and arrival nodes.
  - Interactive accordion drawer for leg-by-leg details.
- **`TransitTimeline.tsx`**: Visual multi-leg timeline detailing train number/name, departure station/time, layover station with connection buffer time, and destination station/time.
- **`SortingFilterBar.tsx`**: Single-select pill rail (`recommended`, `fastest`, `fewest_transfers`, `cheapest`). Displays explanatory tooltip/banner when `cheapest` is selected (explaining commercial fare deferral).

### 3. `layout/` & `common/`
- **`Navbar.tsx`**: Editorial branding, tagline, and clean "Bachelor Special — Multi-friend routing coming soon" teaser badge.
- **`DataIntegrityBanner.tsx`**: Prominent informational notice distinguishing timetable-confirmed schedules from live IRCTC seat availability and explaining that commercial fares are deferred.
- **`Footer.tsx`**: Data provenance notice and project links.

---

## 4. API Integration Mapping

| UI Action | Backend Endpoint | Request Parameters | Response Handled |
|---|---|---|---|
| **Station Autocomplete** | `GET /api/v1/stations/search` | `q`: query string, `limit=8` | List of `{ code, name, city, state, zone, latitude, longitude }` |
| **Nearby Station Finder** | `GET /api/v1/stations/nearby` | `latitude`, `longitude`, `radius_km=30` | List of `{ station: {...}, distance_km }` |
| **Route Discovery** | `GET /api/v1/routes/search` | `origin`, `destination`, `date`, `max_transfers`, `sort_by` | Full `RouteSearchResponse` including `routes`, `timetable_status`, `fare_status`, `sorting_applied`, `sorting_note`, and `no_route_reason` |

### Zero-Fabrication Integrity Rules:
1. **Fares**: When `total_fare` is `null`, display "Fare data deferred (No verified commercial feed)". Never display `₹0` or mock prices.
2. **Availability**: When `availability` is `null`, display "Timetable Confirmed" badge with an informational tooltip: "Seat availability requires live IRCTC feed (deferred)". Never display fictitious seat counts or quotas.
3. **Cheapest Sorting**: When selected, reflect backend's `sorting_applied="recommended"` and display `sorting_note` prominently.

---

## 5. Design System & Styling Tokens

### Color Palette (Tailwind extensions)
- **Canvas Base**: `#F4EFE4` (Archival Warm Cream)
- **Card Surface**: `#FFFFFF` / `#FAF7F2` with 1px border `#D8D1BF`
- **Text Primary**: `#191612` (Espresso)
- **Text Secondary**: `#564F44` (Muted Warm Umber)
- **Accent Primary**: `#B9532D` (Burnt Terracotta)
- **Accent Secondary**: `#67664A` (Muted Olive)
- **Elevated Inverted**: `#191612` with text `#F4EFE4`

### Typography (Next.js font optimization)
- **Headlines & Station Codes**: `Epilogue` (Google Font via `next/font/google`, variable font).
- **Body & Metrics**: `Plus Jakarta Sans` (Google Font via `next/font/google`).

---

## 6. Implementation Sequence

1. **Step 1: Design Tokens & Typography Setup**
   - Configure `next/font/google` for `Epilogue` and `Plus Jakarta Sans` in `layout.tsx`.
   - Update `tailwind.config.js` with editorial color tokens and typography classes.
2. **Step 2: API Client & TypeScript Contracts**
   - Create `src/types/api.ts` mirroring TW-104 backend schemas (`RouteSearchResponse`, `CandidateRoute`, `JourneyLeg`, `StationResponse`).
   - Create `src/services/api.ts` with typed fetchers for stations and routes.
3. **Step 3: Station Autocomplete & Nearby Stations**
   - Build `StationAutocomplete.tsx` with debounced search, keyboard navigation, and code chips.
   - Build `NearbyStationsModal.tsx` utilizing browser geolocation and PostGIS nearby endpoint.
4. **Step 4: Interactive Journey Search Form**
   - Build `JourneySearchCard.tsx` with station inputs, swap trigger, date selector, quick-date pills, and URL sync.
5. **Step 5: Results Stream, Route Cards & Timeline**
   - Build `RouteCard.tsx` and `TransitTimeline.tsx` for direct and 1-transfer routes.
   - Build `SortingFilterBar.tsx` for sorting modes with deferred cheapest notice.
6. **Step 6: Diagnostic Empty States & Integrity Notices**
   - Add clear diagnostic panels for `NO_DIRECT_OR_CONNECTING_TRAINS`, `TRANSFER_BUFFER_VIOLATION`, etc.
   - Add `DataIntegrityBanner.tsx` explaining timetable confirmation vs live availability.
7. **Step 7: Verification & Build Check**
   - Verify frontend production build (`npm run build`).
   - Verify responsive behavior on desktop and mobile viewports.

---

## 7. Limitations & Dependencies

- **Real Data Scope**: The local database currently contains 8 compiled domain trains (`12001`, `12002`, `12301`, `12302`, `12951`, `12952`, `12953`, `12954`) across 8,697 stations. Search between Mumbai (BCT), Delhi (NDLS/NZM), Bhopal (BPL), and Kolkata (HWH) produces real direct and connecting routes; other routes will correctly display honest diagnostic empty states.
- **Seat Availability & Fares**: Live seat booking and commercial fare calculation are deferred and clearly disclosed to the user.
- **Bachelor Special**: Teased via navigation badge / banner; underlying algorithm and itinerary compilation remain deferred.

