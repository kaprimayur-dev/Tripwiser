# TripWiser Railway Data Quality & Trust Audit (TW-115)

**Report ID**: `quality_audit_20261101_231849`  
**Generated At**: `2026-11-01T23:18:49.240824`  
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

## 2. Schedule Record Count Reconciliation & Processing Pipeline

A focused reconciliation demonstrates how schedule records map across TripWiser's ingestion and compilation pipeline:

| Pipeline Stage | Record Scope | Count | Status / Architectural Purpose |
|---|---|---|---|
| **Raw Upstream Source** | Individual stop entries in `schedules.json` | **417,080** | Complete unedited DataMeet JSON array of stops. |
| **Adapter Ingestion: Accepted** | Validated individual stop records | **407,444** | Resolves to valid stations/trains; normalized into 5,140 train schedules. |
| **Adapter Ingestion: Quarantined** | Quarantined individual stop records | **9,636** | Rejections: 2,660 unresolved station codes, 411 unresolved train numbers. |
| **Audited Entities (TW-115)** | High-level schedule entities evaluated | **14,776** | **5,140** sequenced train schedules + **9,636** quarantined stop entries. |
| **Compiled Domain Database** | Operational passenger schedule stops | **23,602** | Stops for the **164 trains** verified against official TAG running calendars. |

### Reconciliation Findings:
1. **Zero Data Loss**: All **23,602 compiled schedule stops** and **164 trains** reported in TW-109 remain 100% intact and present in the PostgreSQL database (`SELECT COUNT(*) FROM train_schedules = 23602`).
2. **Entity Granularity**: The 14,776 inspected entities in the TW-115 audit represent **5,140 route-level train schedules** (encompassing 407,444 stops) plus **9,636 quarantined individual stop entries** ($5,140 + 9,636 = 14,776$).
3. **Compilation Boundary**: Exactly **5,044 trains** (and their associated stops) in the upstream dataset are excluded from compiled database storage because they lack verified operating calendars in official Indian Railways Trains at a Glance (TAG 2024-2026) publication tables. TripWiser compiles only verified operating services to prevent passenger-facing journey hallucination.

---

## 3. Findings by Severity Level & Metric Clarification

> [!NOTE]
> **Severity Metrics Count Findings, Not Unique Records**:  
> Severity totals represent the aggregate count of validation rules triggered across all inspected records. Because a single record or schedule stop may trigger multiple checks (or none), finding totals naturally exceed high-level entity counts.

- **CRITICAL**: **293** (Unusable / null geometry / missing identifier)
- **ERROR**: **13** (Logical integrity / unresolved foreign references / out-of-bounds coords)
- **WARNING**: **32,487** (Suspicious anomaly / awaiting running calendar / missing state)
- **INFO**: **305,825** (Timetable informational characteristics across stops)

### Why Are There 305,825 INFO Findings?
The DataQualityEngine inspects every individual stop entry across all 5,140 train schedules (407,444 stops):
- **`SCH_ZERO_DWELL_WAYPOINT` (283,066 occurrences)**: Stops where scheduled arrival time equals departure time. These denote technical waypoints, operational crossings, or pass-through timing waypoints rather than commercial passenger boarding halts.
- **`SCH_INCOMPLETE_TIMING` (22,759 occurrences)**: Terminal origin/destination stops where arrival or departure is intentionally omitted in timetables, or non-commercial timing points.
- Aggregate: $283,066 + 22,759 = 305,825$ INFO findings.

---

## 4. Top Validation Failure Rules

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

## 5. Source Data Provenance & Freshness Statement

> [!IMPORTANT]
> **Data Freshness Policy**:  
> Dataset compiled from public DataMeet Railways repository snapshots and official Indian Railways Trains at a Glance (TAG 2024-2026) publication tables. Source files do not provide per-record HTTP last-modified timestamps; freshness cannot be dynamically verified beyond the documented publication release dates.

### Audited Source Artifacts:
- **`stations.json`**: `app/infrastructure/data/sources/datameet/stations.json`
- **`trains.json`**: `app/infrastructure/data/sources/datameet/trains.json`
- **`schedules.json`**: `app/infrastructure/data/sources/datameet/schedules.json`
- **`railway_running_calendars.json`**: `app/infrastructure/data/sources/official/railway_running_calendars.json`

---

## 6. Route Engine Protection Guarantee

- **Compiled Domain Models Only**: The Route Discovery Engine queries exclusively compiled domain trains with verified operating calendars (`runs_on_days`) and monotonic stop sequences.
- **Fail-Safe Integrity**: Any schedule stop with unverified station references, invalid times, or missing day offsets is automatically quarantined and excluded from passenger itinerary construction.
- **Honest Disclaimers**: Disclaimers and timetable badges are rendered on the passenger frontend, making it explicit that results represent scheduled timetables rather than real-time tracking or seat availability feeds.
