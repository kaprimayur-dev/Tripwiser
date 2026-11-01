# TW-103A — COMPLETION REPORT
## Verified Fixture Foundation & Domain Validation (Final Data Integrity Pass)

**Ticket**: TW-103A (Evidence, Provenance & Fixture Separation Pass)  
**Base Commit**: `0d3c3cea92b59a551feaf7e40735c3b3c87ced2b` (`feat(data): establish TripWiser domain and database foundation`)  
**Role**: Senior Backend Engineer  
**Status**: COMPLETED & READY FOR CTO REVIEW  
**Test Suite Status**: **86 passed**, 0 failed, 0 skipped (in 4.78s)  

---

## 1. Architectural Fixture Separation: Verified Schedules vs Reference Records

In accordance with strict railway data governance, TripWiser enforces architectural separation between fully verified, operational schedules and reference records:

1. **Active Usable Train Collection (`trains`)**:
   - Contains **exclusively** the **12 `ROUTE_TABLE_VERIFIED`** trains.
   - Every train contains complete, unbroken station progression, valid departure/arrival times, monotonic cumulative distances, and explicit day offsets verified directly from Ministry of Railways Railway Board TAG 2026 route tables.
   - **Zero** incomplete or synthetic schedules are permitted in this collection.
2. **Quarantined Reference Collection (`train_references`)**:
   - Contains the **8 reference records** (6 `INDEX_VERIFIED` and 2 `SOURCE_CONFLICT`).
   - Unverified intermediate stops, invented arrival/departure times, and estimated distances have been **completely excised**.
   - Preserves verified identity: train number, official name, table number reference, document name, source URL, and verified endpoint references.
   - For `SOURCE_CONFLICT` trains (`12615` / `12616`), retains structured candidate endpoints and full citations documenting conflicting official authorities.

### 1.1 Summary Metric Register
```text
Total Curated Railway Records:                     20
=====================================================
Active Verified Trains (in `trains`):              12 (100% ROUTE_TABLE_VERIFIED)
Active Incomplete / Synthetic Schedules:            0 (0.0% - strictly prohibited)
Quarantined References (in `train_references`):     8
  - INDEX_VERIFIED References:                      6
  - SOURCE_CONFLICT References:                     2

Station Coordinate Taxonomy (Total Stations: 50):
=====================================================
- COORDINATES_PRESENT:                             50 (100.0%)
- STRUCTURALLY_VALIDATED:                          50 (100.0%)
- INDEPENDENTLY_VERIFIED (Official Benchmarks):     5 (10.0% - NDLS, HWH, MMCT, CSMT, MAS)
- NOT_INDEPENDENTLY_VERIFIED:                      45 (90.0% - DataMeet coordinates)
```

---

## 2. Timetable Discrepancy Resolution & Official Evidence

Every disputed timetable value was inspected directly in the official Ministry of Railways Railway Board TAG 2026 publications:

### 2.1 Discrepancy Resolutions
1. **Train 12001 (Rani Kamlapati $\to$ New Delhi Shatabdi Express)**:
   - *Discrepancy*: Report noted 15:10 / 23:50; fixture previously had 15:15 / 23:55.
   - *Official Evidence*: `Shatabdi_Exp.pdf` (Page 1, Table 2A):
     - `Rani Kamalapati (Dep) 15.10`
     - `Gwalior (Dep) 19.45`
     - `Agra Cantt. (Dep) 21.25`
     - `New Delhi (Arr) 23.50`
   - *Resolution*: Fixture updated to exact official times: Origin departure `15:10:00`, Terminus arrival `23:50:00`.
2. **Train 20171 (Rani Kamlapati $\to$ Hazrat Nizamuddin Vande Bharat Express)**:
   - *Discrepancy*: Report noted arrival 13:16; fixture previously had 13:10.
   - *Official Evidence*: `VandeBharatTrains.pdf` (Page 1, Table 2A):
     - `Rani Kamlapati (Dep) 05.40`
     - `H. Nizamuddin (Arr) 13.16`
   - *Resolution*: Fixture updated to exact official arrival `13:16:00`.
3. **Train 20172 (Hazrat Nizamuddin $\to$ Rani Kamlapati Vande Bharat Express)**:
   - *Discrepancy*: Report noted arrival 22:16; fixture previously had 22:10.
   - *Official Evidence*: `VandeBharatTrains.pdf` (Page 1, Table 2):
     - `H. Nizamuddin (Dep) 14.40`
     - `Rani Kamlapati (Arr) 22.16`
   - *Resolution*: Fixture updated to exact official arrival `22:16:00`.
4. **Trains 22435 and 22436 (Vande Bharat Express Varanasi $\leftrightarrow$ New Delhi)**:
   - *Discrepancy*: Previous report text claimed "Except Wednesday", but JSON had `[1, 2, 4, 5, 6, 0]`.
   - *Official Evidence*: `VandeBharatTrains.pdf` (Page 4):
     - `22435 Except Th Varanasi - New Delhi 1A`
     - `22436 Except Th New Delhi - Varanasi 1`
   - *Resolution*: Official timetable explicitly specifies **"Except Th" (Except Thursday)**. Under the 0-indexed ISO day convention (`0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday`), Thursday corresponds to index `3`. The correct active operating days list excluding Thursday is **`[0, 1, 2, 4, 5, 6]`** (Monday, Tuesday, Wednesday, Friday, Saturday, Sunday). The report text is reconciled to match the official table.

### 2.2 Table and Sub-Table Identifier Reconciliation
All table numbers and sub-table identifiers are aligned across both JSON and report:

| Train No | Official Train Name | Table No | Direction | Source Document | Page | Verified Schedule Halts |
| :---: | :--- | :---: | :---: | :--- | :---: | :--- |
| **12951** | Mumbai Central - New Delhi Tejas Rajdhani | **3A** | Up (`MMCT` $\to$ `NDLS`) | `Rajdhani_Exp.pdf` | 2 | MMCT (17:00) $\to$ BVI $\to$ ST $\to$ BRC $\to$ RTM $\to$ KOTA $\to$ NDLS (08:32) |
| **12952** | New Delhi - Mumbai Central Tejas Rajdhani | **3** | Dn (`NDLS` $\to$ `MMCT`) | `Rajdhani_Exp.pdf` | 2 | NDLS (16:55) $\to$ KOTA $\to$ RTM $\to$ BRC $\to$ ST $\to$ BVI $\to$ MMCT (08:35) |
| **12002** | New Delhi - Rani Kamlapati Shatabdi | **2** | Dn (`NDLS` $\to$ `RKMP`) | `Shatabdi_Exp.pdf` | 1 | NDLS (06:00) $\to$ MTJ $\to$ AGC $\to$ GWL $\to$ VGLJ $\to$ BPL $\to$ RKMP (14:40) |
| **12001** | Rani Kamlapati - New Delhi Shatabdi | **2A** | Up (`RKMP` $\to$ `NDLS`) | `Shatabdi_Exp.pdf` | 1 | RKMP (15:10) $\to$ BPL $\to$ VGLJ $\to$ GWL $\to$ AGC $\to$ MTJ $\to$ NDLS (23:50) |
| **12301** | Howrah - New Delhi Kolkata Rajdhani (via Gaya) | **1A** | Up (`HWH` $\to$ `NDLS`) | `Rajdhani_Exp.pdf` | 1 | HWH (16:50) $\to$ DDU $\to$ PRYJ $\to$ CNB $\to$ NDLS (10:05) |
| **12302** | New Delhi - Howrah Kolkata Rajdhani (via Gaya) | **1** | Dn (`NDLS` $\to$ `HWH`) | `Rajdhani_Exp.pdf` | 1 | NDLS (16:50) $\to$ CNB $\to$ PRYJ $\to$ DDU $\to$ HWH (09:55) |
| **20171** | Rani Kamlapati - H. Nizamuddin Vande Bharat | **2A** | Up (`RKMP` $\to$ `NZM`) | `VandeBharatTrains.pdf` | 1 | RKMP (05:40) $\to$ VGLJ $\to$ GWL $\to$ AGC $\to$ NZM (13:16) |
| **20172** | H. Nizamuddin - Rani Kamlapati Vande Bharat | **2** | Dn (`NZM` $\to$ `RKMP`) | `VandeBharatTrains.pdf` | 1 | NZM (14:40) $\to$ AGC $\to$ GWL $\to$ VGLJ $\to$ RKMP (22:16) |
| **22436** | New Delhi - Varanasi Vande Bharat Exp | **1** | Dn (`NDLS` $\to$ `BSB`) | `VandeBharatTrains.pdf` | 4 | NDLS (06:00) $\to$ CNB $\to$ PRYJ $\to$ BSB (14:00) |
| **22435** | Varanasi - New Delhi Vande Bharat Exp | **1A** | Up (`BSB` $\to$ `NDLS`) | `VandeBharatTrains.pdf` | 4 | BSB (15:00) $\to$ PRYJ $\to$ CNB $\to$ NDLS (23:00) |
| **12953** | Mumbai Central - H. Nizamuddin August Kranti | **3A** | Up (`MMCT` $\to$ `NZM`) | `Rajdhani_Exp.pdf` | 2 | MMCT (17:10) $\to$ BVI $\to$ ST $\to$ BRC $\to$ RTM $\to$ KOTA $\to$ MTJ $\to$ NZM (09:43) |
| **12954** | H. Nizamuddin - Mumbai Central August Kranti | **3** | Dn (`NZM` $\to$ `MMCT`) | `Rajdhani_Exp.pdf` | 2 | NZM (17:15) $\to$ MTJ $\to$ KOTA $\to$ RTM $\to$ BRC $\to$ ST $\to$ BVI $\to$ MMCT (10:05) |

---

## 3. Quarantined Reference Records Register (`train_references`)

The following 8 records do not have verified route tables and are excluded from graph generation:

| Train No | Official Train Name | Source Table | Verification Status | Endpoint Reference / Conflicting Candidates | Reason for Reference-Only Status |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **12621** | Tamil Nadu Express | Table 8 | `INDEX_VERIFIED` | `MAS` $\to$ `NDLS` | Intermediate stops, distances, and running days pending extraction from main 91 MB TAG 2026 Table 8. |
| **12622** | Tamil Nadu Express | Table 8 | `INDEX_VERIFIED` | `NDLS` $\to$ `MAS` | Intermediate stops, distances, and running days pending extraction from main 91 MB TAG 2026 Table 8. |
| **12627** | Karnataka Express | Table 9 | `INDEX_VERIFIED` | `SBC` $\to$ `NDLS` | Intermediate stops, distances, and running days pending extraction from main 91 MB TAG 2026 Table 9. |
| **12628** | Karnataka Express | Table 9 | `INDEX_VERIFIED` | `NDLS` $\to$ `SBC` | Intermediate stops, distances, and running days pending extraction from main 91 MB TAG 2026 Table 9. |
| **12625** | Kerala Express | Table 8, 86 | `INDEX_VERIFIED` | `TVC` $\to$ `NDLS` | Intermediate stops, distances, and running days pending extraction from main 91 MB TAG 2026 Table 8/86. |
| **12626** | Kerala Express | Table 8, 86 | `INDEX_VERIFIED` | `NDLS` $\to$ `TVC` | Intermediate stops, distances, and running days pending extraction from main 91 MB TAG 2026 Table 8/86. |
| **12615** | Grand Trunk Express | Table 8 | `SOURCE_CONFLICT` | Conflicting: `MS`/`MAS` $\to$ `NDLS`/`DEE` | 4 conflicting official/operational sources. Quarantined with full conflict citations. |
| **12616** | Grand Trunk Express | Table 8 | `SOURCE_CONFLICT` | Conflicting: `NDLS`/`DEE` $\to$ `MS`/`MAS` | 4 conflicting official/operational sources. Quarantined with full conflict citations. |

### 3.1 Detail of `SOURCE_CONFLICT` Citations for 12615/12616:
- **Citation 1**: TAG 2026 Table Number Index (Railway Board) lists `"12615/12616 Chennai Egmore New Delhi Grand Trunk 8"`.
- **Citation 2**: Southern Railway circular (June 2025) announced temporary terminal relocation from Chennai Egmore (`MS`) to MGR Chennai Central (`MAS`) due to major station redevelopment.
- **Citation 3**: Lok Sabha unstarred answer (4 Feb 2026) designates the service as `"New Delhi–MGR Chennai Central Grand Trunk Express"`.
- **Citation 4**: Live CRIS NTES train enquiry system lists operational service between `MAS` and Delhi Sarai Rohilla (`DEE`).

---

## 4. Station Coordinate Taxonomy & Verification Evidence

TripWiser classifies station coordinates into four distinct tiers:

1. **`COORDINATES_PRESENT`**: Station has latitude and longitude values populated (50 stations = 100%).
2. **`STRUCTURALLY_VALIDATED`**: Coordinates pass boundary checks (`-90 <= lat <= 90`, `-180 <= lon <= 180`, non-zero, non-null) (50 stations = 100%).
3. **`INDEPENDENTLY_VERIFIED`**: Station coordinates have been independently reconciled against official Survey of India / Municipal GIS geodetic benchmarks (5 stations = 10%).
4. **`NOT_INDEPENDENTLY_VERIFIED`**: Station coordinates originate solely from DataMeet crowd-sourced GIS without independent surveyor cross-verification (45 stations = 90%).

### 4.1 The 5 Independently Verified Benchmark Stations

| Station Code | Station Name | Verified Coordinates | Independent Geodetic Benchmark Authority | Benchmark Source URL |
| :---: | :--- | :---: | :--- | :--- |
| **NDLS** | New Delhi | `(28.6423, 77.2200)` | Open Government Data (OGD) Platform India / Delhi Municipal GIS / Survey of India benchmark (28°38'32" N, 77°13'12" E) | `https://data.gov.in/` |
| **HWH** | Howrah Junction | `(22.5841, 88.3410)` | West Bengal Spatial Data Infrastructure (WBSDI) GIS / SPM Port Trust benchmark (22°35'03" N, 88°20'28" E) | `https://wbsdi.gov.in/` |
| **MMCT** | Mumbai Central | `(18.9696, 72.8193)` | Municipal Corporation of Greater Mumbai (MCGM) OneGIS benchmark (18°58'11" N, 72°49'09" E) | `https://onegis.mcgm.gov.in/` |
| **CSMT** | Mumbai CSMT | `(18.9401, 72.8354)` | UNESCO World Heritage Centre Boundary Map (Ref: 945rev) / MCGM OneGIS (18°56'24" N, 72°50'07" E) | `https://whc.unesco.org/en/list/945/` |
| **MAS** | MGR Chennai Central | `(13.0827, 80.2755)` | Chennai Metropolitan Development Authority (CMDA) GIS benchmark (13°04'58" N, 80°16'32" E) | `https://www.cmdachennai.gov.in/` |

### 4.2 Correction of Baiyyappanahalli (`BYPL`) Identity
- **Error in Previous Report**: The previous draft mapped `BYPL` to `SMVB`, characterizing it as a station rename.
- **Architectural Correction**: Baiyyappanahalli (`BYPL`) and Sir M. Visvesvaraya Terminal (`SMVB`) are **distinct physical stations**. `BYPL` is an established passenger station and metro interchange on the Bangalore suburban corridor. `SMVB` is a newly constructed coaching terminal commissioned adjacent to Baiyyappanahalli yard in 2022 with its own independent station code assigned by Indian Railways.
- In [`bootstrap_railway_data.json`](file:///c:/projects/tripwiser/backend/app/infrastructure/data/fixtures/bootstrap_railway_data.json), station #46 is correctly recorded as:
  ```json
  {
    "code": "BYPL",
    "name": "Baiyyappanahalli",
    "latitude": 12.9902,
    "longitude": 77.6509,
    "state": "Karnataka",
    "zone": "SWR",
    "coordinate_source": "DataMeet Railways (stations.json)",
    "coordinates_present": true,
    "structurally_validated": true,
    "coordinate_validation_status": "NOT_INDEPENDENTLY_VERIFIED"
  }
  ```

---

## 5. Domain Test Suite & Test Integrity Improvements

In [`backend/tests/unit/domain/test_bootstrap_fixture_domain.py`](file:///c:/projects/tripwiser/backend/tests/unit/domain/test_bootstrap_fixture_domain.py), the test suite was updated to enforce data discipline:
1. **Eliminated Fallback Defaults**: `day_offset=entry["day_offset"]` and `distance_km=entry["distance_km"]` are now looked up directly. Missing fields fail with `KeyError` rather than silently injecting synthetic default values.
2. **Separated Usable Trains vs References**: Active trains (`trains`, count 12) are validated as full `Train` domain entities; reference records (`train_references`, count 8) are verified in a dedicated test asserting they do not contain unverified intermediate schedules or enter route search.
3. **Distance Monotonicity Assertions**: Added `test_schedule_cumulative_distance_monotonicity` verifying $D_i \le D_{i+1}$ across all active schedules.
4. **Clarified Ingestion Quarantine Rule**: The test was updated to `test_schedule_missing_arrival_and_departure_ingestion_filter_rule`, explicitly testing the pure validation rule specification (`not (arr is None and dep is None)`) and documented as a future ingestion requirement for TW-103B rather than claiming an existing quarantine engine.

### 5.1 Full Test Inventory (20 Unit Tests in `test_bootstrap_fixture_domain.py`)
| Test Name | Focus Area | Key Assertions |
| :--- | :--- | :--- |
| `test_fixture_stations_valid_domain` | Station domain validity | All 50 stations deserialize into `Station` models; valid coordinates; no dummy (0,0). |
| `test_station_latitude_boundaries` | Coordinate bounds | Rejection of latitudes > 90.0 or < -90.0 via Pydantic `ValidationError`. |
| `test_station_longitude_boundaries` | Coordinate bounds | Rejection of longitudes > 180.0 or < -180.0 via Pydantic `ValidationError`. |
| `test_station_duplicate_detection` | Referential uniqueness | No duplicate station codes among the 50 stations. |
| `test_station_coordinate_taxonomy` | Coordinate auditing | 50 present, 50 structurally valid, exactly 5 `INDEPENDENTLY_VERIFIED`, 45 `NOT_INDEPENDENTLY_VERIFIED`. |
| `test_fixture_active_trains_valid_domain` | Active train domain models | Exactly 12 trains; all status `ROUTE_TABLE_VERIFIED`; no default fallbacks used. |
| `test_fixture_active_trains_provenance` | Audit provenance | Official URL, document name (.pdf), table identifier, page number (>=1), verified fields. |
| `test_train_references_collection_integrity` | Reference quarantine | Exactly 8 references (6 `INDEX_VERIFIED`, 2 `SOURCE_CONFLICT`); no schedules; disjoint from active. |
| `test_train_number_preserved_as_string_with_leading_zero` | Pydantic string validation | Train number "04601" preserved as string; leading zero not dropped. |
| `test_train_running_days_validation` | Operating days domain | Rejection of days > 6, empty lists, or duplicate days. |
| `test_schedule_stop_sequence_monotonicity` | Stop ordering | Rejection of non-monotonic stop sequences. |
| `test_schedule_cumulative_distance_monotonicity` | Distance progression | $D_i \le D_{i+1}$ monotonically verified across all 12 active trains. |
| `test_schedule_origin_destination_agreement` | Schedule boundaries | First halt station matches `origin_code`; last halt matches `destination_code`. |
| `test_concrete_overnight_journey_scenario` | Midnight temporal transit | Correct day offset increment and midnight arrival/departure handling. |
| `test_schedule_missing_origin_arrival` | Boundary halt semantics | Origin station arrival is `None`; departure is valid time; `day_offset == 0`. |
| `test_schedule_missing_terminal_departure` | Boundary halt semantics | Terminus station departure is `None`; arrival is valid time; `day_offset >= 0`. |
| `test_schedule_missing_arrival_and_departure_ingestion_filter_rule` | Ingestion filter specification | Pure rule specification flags halt with both times `None` as invalid for ingestion. |
| `test_schedule_negative_day_offset_rejected` | Day offset validation | Rejection of negative day offsets via Pydantic `ge=0` constraint. |
| `test_multi_day_journey` | Multi-day progression | Monotonically increasing day offsets across multi-day journey. |
| `test_cross_fixture_referential_integrity` | Cross-collection integrity | 50 stations, 12 active trains, 8 references; all active schedule stations exist in fixture. |

---

## 6. Full Test Suite Verification

### 6.1 Exact Docker Execution Command
```bash
docker exec -e PYTHONPATH=/app tripwiser-backend pytest
```

### 6.2 Raw Test Output
```text
============================= test session starts ==============================
platform linux -- Python 3.11.18, pytest-9.2.0, pluggy-1.7.0
rootdir: /app
plugins: asyncio-1.4.1, anyio-4.15.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 86 items

tests/integration/database/test_orm_models.py ....                       [  4%]
tests/integration/database/test_station_repository.py .                  [  5%]
tests/integration/database/test_train_repository.py .                    [  6%]
tests/test_health.py ...                                                 [ 10%]
tests/unit/domain/test_availability_domain.py .......                    [ 18%]
tests/unit/domain/test_bachelor_domain.py ...............                [ 36%]
tests/unit/domain/test_bootstrap_fixture_domain.py ....................  [ 59%]
tests/unit/domain/test_route_domain.py ..............                    [ 75%]
tests/unit/domain/test_station_domain.py .......                         [ 83%]
tests/unit/domain/test_train_domain.py ..............                    [100%]

============================== 86 passed in 4.78s ==============================
```

---

## 7. Remaining Limitations

1. **8 Reference Trains Pending Route-Table Extraction**:
   - Trains `12621`, `12622`, `12625`, `12626`, `12627`, `12628` require parsing from the full 91 MB TAG 2026 Table 8, Table 9, and Table 86 PDFs to extract verified intermediate stop distances and dwell times before promotion to active `trains`.
   - Trains `12615` and `12616` require an authoritative operational policy decision (or dynamic API verification) to resolve the terminal conflict between `MS`, `MAS`, `NDLS`, and `DEE`.
2. **45 Station Coordinates Pending Independent Survey Reconciliation**:
   - 45 stations retain DataMeet crowd-sourced coordinates. They are structurally validated within Indian bounds but have not yet undergone geodetic benchmark matching against Survey of India or municipal GIS layers.
3. **Future Ingestion Pipeline Scope (TW-103B)**:
   - Quarantine mechanisms, database loaders, and Alembic data migrations will be implemented in TW-103B under separate ticket authorization.

---

## 8. Working Tree Status

```text
$ git status --short
?? TW103A_COMPLETION_REPORT.md
?? TW103_REVISED_DATA_FOUNDATION_REPORT.md
?? backend/app/infrastructure/data/
?? backend/tests/unit/domain/test_bootstrap_fixture_domain.py
```

### Strict Rules Observed:
- No changes to database schemas or migrations.
- No changes to TW-102 domain contracts.
- No database data inserted.
- No production importer or scraper code written.
- No files committed or staged.
- TW-103B has not been started.

*TW-103A Final Data Integrity Correction Pass complete. Awaiting CTO approval.*
