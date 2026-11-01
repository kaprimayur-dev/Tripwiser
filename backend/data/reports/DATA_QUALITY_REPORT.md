# TripWiser Railway Data Quality & Trust Audit (TW-115)

**Report ID**: `quality_audit_20261101_230624`  
**Generated At**: `2026-11-01T23:06:24.713354`  
**Total Records Inspected**: **34,182**  
**Reproducibility SHA-256**: `bd76cfaf219516dd40310729c172a2d34b5dfbdd8a797c54b8fd5ad53c8732e9`  

---

## 1. Executive Summary & Quality Classification

| Category | Inspected | Valid | Retained Incomplete | Review Required | Rejected / Quarantined |
|---|---|---|---|---|---|
| **Stations** | 8,990 | 4,213 | 0 | 4,484 | 293 |
| **Trains (Headers)** | 5,208 | 5,207 | 0 | 0 | 1 |
| **Train Schedules** | 14,776 | 4,378 | 26 | 731 | 9,641 |
| **Running Calendars** | 5,208 | 192 | 0 | 5,016 | 0 |

---

## 2. Findings by Severity Level

- **CRITICAL**: **293** (Unusable / null geometry / missing identifier)
- **ERROR**: **13** (Logical integrity / unresolved foreign references / out-of-bounds coords)
- **WARNING**: **32,487** (Suspicious anomaly / awaiting running calendar / missing state)
- **INFO**: **305,825** (Incomplete timing / technical waypoint / zero dwell)

---

## 3. Top Validation Failure Rules

| Validation Rule Code | Occurrences |
|---|---|
| `SCH_ZERO_DWELL_WAYPOINT` | **283,066** |
| `SCH_INCOMPLETE_TIMING` | **22,759** |
| `SCH_MISSING_DAY_OFFSET` | **22,561** |
| `CAL_AWAITING_CALENDAR` | **5,016** |
| `STN_MISSING_STATE` | **4,777** |
| `STN_NULL_GEOMETRY` | **293** |
| `SCH_NEGATIVE_STATION_DWELL` | **112** |
| `SCH_DEST_ENDPOINT_MISMATCH` | **16** |
| `SCH_ANOMALOUS_DAY_OFFSET` | **6** |
| `SCH_ORIGIN_ENDPOINT_MISMATCH` | **5** |
| `SCH_DECREASING_DAY_OFFSET` | **2** |
| `STN_MISSING_NAME` | **1** |
| `TRN_MISSING_NAME` | **1** |
| `TRN_UNRESOLVED_ORIGIN` | **1** |
| `TRN_UNRESOLVED_DESTINATION` | **1** |

---

## 4. Source Data Provenance & Freshness Statement

> [!IMPORTANT]
> **Data Freshness Policy**:  
> Dataset compiled from public DataMeet Railways repository snapshots and official Indian Railways Trains at a Glance (TAG 2024-2026) publication tables. Source files do not provide per-record HTTP last-modified timestamps; freshness cannot be dynamically verified beyond the documented publication release dates.

### Audited Source Artifacts:
- **`stations.json`**: `app/infrastructure/data/sources/datameet/stations.json`
- **`trains.json`**: `app/infrastructure/data/sources/datameet/trains.json`
- **`schedules.json`**: `app/infrastructure/data/sources/datameet/schedules.json`
- **`railway_running_calendars.json`**: `app/infrastructure/data/sources/official/railway_running_calendars.json`

---

## 5. Route Engine Protection Guarantee

- **Compiled Domain Models Only**: The Route Discovery Engine queries exclusively compiled domain trains with verified operating calendars (`runs_on_days`) and monotonic stop sequences.
- **Fail-Safe Integrity**: Any schedule stop with unverified station references, invalid times, or missing day offsets is automatically quarantined and excluded from passenger itinerary construction.
- **Honest Disclaimers**: Disclaimers and timetable badges are rendered on the passenger frontend, making it explicit that results represent scheduled timetables rather than real-time tracking or seat availability feeds.
