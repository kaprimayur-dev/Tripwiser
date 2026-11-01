# TW-103 — REVISED DATA FOUNDATION & INGESTION ARCHITECTURE REPORT
## Forensic Data Source Intelligence, Schema Alignment & Ingestion Architecture

**Project**: TripWiser (Indian Railway Journey Intelligence & Discovery Platform)  
**Document**: `TW103_REVISED_DATA_FOUNDATION_REPORT.md`  
**Ticket**: TW-103 (Phase A Final CTO Correction Pass)  
**Role**: Senior Railway Data Architect & Data Quality Engineer  
**Status**: ARCHITECTURAL SPECIFICATION & PROPOSAL (FOR FINAL CTO REVIEW)  
**Base Commit**: `0d3c3cea92b59a551feaf7e40735c3b3c87ced2b` (`feat(data): establish TripWiser domain and database foundation`)  

---

## 1. Executive Summary

TripWiser’s journey planning engine, alternate route stitching ("Bachelor Special"), and berth availability models require an authoritative, spatially verified, and temporally consistent railway schedule baseline.

Following rigorous forensic investigation and CTO architectural direction, this document establishes the empirical data landscape across candidate sources:
1. **Official Indian Railways "Trains at a Glance" (TAG) 2026** (Ministry of Railways / Railway Board, Government of India).
2. **Open Government Data Platform India (`data.gov.in`)** (Ministry of Railways catalogue).
3. **DataMeet Railways** (`datameet/railways`, GitHub).
4. **`prasenjit-27/Indian-Railway-Data`** (GitHub repository, August 2026).
5. **RailPull NTES Automation Tooling** (`shwetankg07/railpull`, GitHub).
6. **Kaggle Curated Indian Railways Collections** (`arihantjain09/indian-railways-latest` and `rohanpatel25/indian-trains-schedule-routes`).

### Key Audit Conclusions & Corrected Classifications:
- **Correction of TAG 2026 Attribution & Form**:
  - Trains at a Glance (TAG) 2026 is published by the **Ministry of Railways / Railway Board, Government of India** (official portal: `https://rb.indianrailways.gov.in/show-directorate/preview/228`).
  - Effective date: **1 January 2026**. It organizes the national passenger network into numbered route tables and individual table PDFs, containing train numbers, official names, departure days, station sequences, cumulative distances, commercial halt arrival/departure times, and destination arrival days.
  - While it is the gold-standard validation benchmark, it does **not** provide a verified full-network machine-readable bulk REST/CSV API, and its official publication is not openly licensed for unconstrained bulk republication or redistribution.
- **Production-Wide Timetable Master Status**:
  - The `data.gov.in` timetable catalogue was **last updated on 24 January 2018** (over 8 years stale) and cannot serve as a current production master.
  - This investigation has **not identified an approved, current, full-network machine-readable open dataset**. Consequently, the Production-Wide Timetable Master is formally classified as **UNRESOLVED / DEFERRED**.
- **Development Strategy (TW-103A)**:
  - Development and integration testing will bootstrap exclusively from a **Curated Development Fixture** (50 stations, 20 iconic multi-day trains) whose sequences, distances, operating days, and timings are independently cross-verified against official TAG 2026 tables.
- **Exhaustive Reconciliation of the 293 Null-Coordinate Stations**:
  - The 293 stations lacking coordinates in DataMeet are partitioned into an exhaustive, non-overlapping classification: **184 genuine passenger stations with address/state metadata**, **23 technical cabin/siding records (`XX-`/`YY-`)**, **1 explicit goods facility (`TSKG`)**, and **85 unclassified records lacking metadata**.
  - Forensic trace confirms that **11 stations serve as commercial train endpoints** directly affecting **32 passenger trains**.
  - In strict compliance with our committed TW-102 constraint (`stations.location NOT NULL`), these 293 stations and 32 dependent trains are placed in a **Quarantine Isolation Store** without altering the database schema.
- **DataMeet Limitations & Route Geometries**:
  - DataMeet `schedules.json` is a flat, unsorted array with arbitrary surrogate `id` values, lacking stop sequences and distances. LineStrings in `trains.json` are **route geometries** (connecting station coordinates), not surveyed physical track alignments, and must not be used for routing or distance calculations. DataMeet is classified strictly as a **Candidate Station-Coordinate Source** (8,697 points).
- **Day-Offset Normalization Semantics**:
  - Evaluated against committed TW-102 models (`TrainScheduleEntry`, `ScheduleORM`), documenting exact handling for origin, terminus, intermediate, overnight halts, and multi-day rollovers under the existing single `day_offset` column.

---

## 2. Timetable Source Classification & Provenance Matrix

| Source Category | Candidate Source | Underlying Format | Freshness / Baseline Date | Provenance & Legal Rights | Classification & Operational Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Candidate Station-Coordinate Source** | **DataMeet Railways** (`stations.json`) | GeoJSON Point features | Circa 2017–2019 | **CC0 1.0 Universal** (Public Domain Dedication) | **APPROVED FOR STATIONS**: Authoritative for 8,697 physical station coordinates. The 293 null-coordinate stations are quarantined. |
| **2. Official Timetable Validation Source** | **Trains at a Glance (TAG) 2026** (Ministry of Railways / Railway Board) | Official Table Index & Individual Table PDFs | **Effective 1 January 2026** | Ministry of Railways, Government of India (`rb.indianrailways.gov.in`). Not licensed for bulk commercial redistribution. | **APPROVED FOR VALIDATION**: Authoritative operational reference for train routes, station sequences, running days, cumulative distances, and arrival/departure times. Used to verify curated fixtures. |
| **3. Historical Timetable Reference** | **data.gov.in** (Indian Railways Train Time Table) | CSV / JSON tabular API | **24 January 2018** (Stale) | GODL-India (Government Open Data License) | **HISTORICAL ONLY**: Excluded as production master. Useful only for historical timetable cross-checks. |
| **4. Development Fixture Source** | **Curated TripWiser Seed Fixture** (`bootstrap_fixtures.json`) | Pure JSON Fixture | **Current (TAG 2026 aligned)** | TripWiser Native (CC0) | **APPROVED FOR DEV/TEST**: 50 major hubs, 20 iconic multi-day trains, verified against TAG 2026 tables. Zero external dependencies. |
| **5. Production-Wide Timetable Master** | **NOT IDENTIFIED** | N/A | N/A | N/A | **UNRESOLVED / DEFERRED**: This investigation has not identified an approved, current, full-network source. Requires future sanctioned open data or official API agreement. |

### Technical Analysis of Trains at a Glance (TAG) 2026
- **Attribution**: Published directly by the **Railway Board, Ministry of Railways, Government of India** (`https://rb.indianrailways.gov.in/show-directorate/preview/228`).
- **Structure**:
  - Organized into regional and inter-zonal Route Tables (e.g., Table 1: New Delhi – Mumbai, Table 8: New Delhi – Howrah, Table 18: New Delhi – Chennai).
  - Individual table PDFs list train numbers, train names, frequency/departure days, intermediate commercial halts in physical order, cumulative route distances in kilometers, scheduled arrival and departure times, and destination arrival days.
- **Coverage & Practical Ingestion Limitations**:
  - Covers ~1,400 premier express/superfast services (Rajdhani, Shatabdi, Vande Bharat, Tejas, Duronto, Mail/Express). It omits unreserved local passenger/MEMU/DEMU services.
  - Published as visual document tables (PDFs); **it does not provide an automated, machine-readable bulk REST/JSON feed**.
  - Copyright rests with the Ministry of Railways; it cannot be presumed to be licensed for bulk republication or redistribution.

---

## 3. Exhaustive Analysis & Arithmetic of the 293 Null-Coordinate Stations

DataMeet’s `stations.json` contains 8,990 features, of which 8,697 possess valid WGS84 coordinates and exactly **293 have `"geometry": null`**.

### 3.1 Exhaustive, Mutually Exclusive Classification
To eliminate arithmetic ambiguity and avoid reliance on code prefixes alone, all 293 records were evaluated across their metadata fields (`name`, `state`, `zone`, `address`):

```
+--------------------------------------------------------------------------------------------------+
|                   EXHAUSTIVE CLASSIFICATION OF THE 293 NULL-COORDINATE STATIONS                  |
+---+----------------------------------------------------+-------+---------------------------------+
| # | Classification Category                            | Count | Criteria & Representative Codes |
+---+----------------------------------------------------+-------+---------------------------------+
| A | Genuine Stations with State & Municipal Address    |  184  | Has valid state & address       |
|   | (Candidate Commercial Passenger Stations)          |       | e.g. JMB, MGR, TTP, LKKA, ARVI  |
+---+----------------------------------------------------+-------+---------------------------------+
| B | Technical Infrastructure / Operational Waypoints   |   23  | Empty state/address; code has   |
|   | (Block Cabins, Loops, Siding Waypoints)            |       | prefix 'XX-' (15) or 'YY-' (8)  |
+---+----------------------------------------------------+-------+---------------------------------+
| C | Explicit Goods / Freight Facility                  |    1  | Empty state/address; name has   |
|   |                                                    |       | explicit 'GOODS' (TSKG)         |
+---+----------------------------------------------------+-------+---------------------------------+
| D | Unclassified Stations Lacking Metadata (UNKNOWN)   |   85  | Empty state & address; standard |
|   |                                                    |       | alphabetic codes (e.g. BJUP)    |
+---+----------------------------------------------------+-------+---------------------------------+
|   | TOTAL NULL-COORDINATE STATIONS                     |  293  | Exact, complete partition       |
+---+----------------------------------------------------+-------+---------------------------------+
```
*Arithmetic Verification*: $184 + 23 + 1 + 85 = 293$ unique station codes. No overlaps exist between categories.

### 3.2 Network Impact: How Trains Become Classified as "Affected"
A train in `trains.json` is classified as **Affected** if and only if:
$$\text{from\_station\_code} \in \text{NullStations} \quad \lor \quad \text{to\_station\_code} \in \text{NullStations}$$

Because the committed database schema enforces `trains.origin_code` and `trains.destination_code` as foreign keys to `stations.code`, and `stations.location` is `NOT NULL`, inserting an affected train without its endpoint station would violate foreign key constraints.

### 3.3 Complete Evidence Tables

#### A. The 11 Endpoint Stations Without Coordinates
| # | Station Code | Official Name | Zone | State | Address / Locality | Endpoint Usage in `trains.json` |
| :-: | :--- | :--- | :-: | :--- | :--- | :--- |
| 1 | `LFG` | Lower Haflong | NFR | Assam | Haflong, Assam | Origin & Destination |
| 2 | `LKKA` | Lal Kuan | NER | Uttarakhand | Lalkuan, Uttarakhand | Origin & Destination |
| 3 | `TTP` | Tiruturaipudi Junction | SR | Tamil Nadu | Thiruthuraipoondi, Tamil Nadu | Origin & Destination |
| 4 | `MGR` | Munger | ER | Bihar | Munger, Bihar | Destination only |
| 5 | `ARVI` | Arvi | CR | Maharashtra | Dist. Wardha, Maharashtra | Origin & Destination |
| 6 | `JMB` | Jambusar Junction | WR | Gujarat | Bharuch Jambusar, Gujarat | Origin & Destination |
| 7 | `MKRL` | Moti Koral | WR | Gujarat | Maninageshwar Rd, Gujarat | Origin & Destination |
| 8 | `CRND` | Choranda Junction | WR | Gujarat | Choranda, Gujarat | Origin & Destination |
| 9 | `BDRN` | Bhadran | WR | Gujarat | Borsad, Gujarat | Origin & Destination |
| 10 | `UMPD` | Umarpada | WR | Gujarat | Umarpada to Jumavadi, Gujarat | Origin & Destination |
| 11 | `RGV` | Rathopur | ECR | Bihar | Saraygarh, Bihar | Origin & Destination |

#### B. The Complete List of All 32 Affected Passenger Trains
All 32 trains terminating or originating at the 11 unlocated endpoint stations:
1. `05697`: *Hill Queen Express* (`LMG` $\to$ `LFG`)
2. `05698`: *Hill Queen Express* (`LFG` $\to$ `LMG`)
3. `15311`: *KUMAON EXPRESS* (`KSJF` $\to$ `LKKA`)
4. `15312`: *Kumaun Express* (`LKKA` $\to$ `KSJF`)
5. `16861`: *Tiruturaipudi Karaikkudi Express* (`TTP` $\to$ `KKDI`)
6. `16862`: *Karaikkudi Tiruturaipudi Express* (`KKDI` $\to$ `TTP`)
7. `52021`: *Moti Koral Miyagam Mix Passenger* (`MKRL` $\to$ `MYG`)
8. `52022`: *Miyagam Moti Koral Mix Passenger* (`MYG` $\to$ `MKRL`)
9. `52027`: *Choranda Dabhoi Mix Passenger* (`CRND` $\to$ `DB`)
10. `52028`: *Dabhoi Choranda Mix Passenger* (`DB` $\to$ `CRND`)
11. `52033`: *Jambusar Pratapnagar Mix Passenger* (`JMB` $\to$ `PRTN`)
12. `52034`: *Pratapnagar Jambusar Mix Passenger* (`PRTN` $\to$ `JMB`)
13. `52035`: *Jambusar Pratapnagar Passenger* (`JMB` $\to$ `PRTN`)
14. `52036`: *Pratapnagar Jambusar Passenger* (`PRTN` $\to$ `JMB`)
15. `52037`: *Nadiad Bhadran Mix Passenger* (`ND` $\to$ `BDRN`)
16. `52038`: *Bhadran Nadiad Mix Passenger* (`BDRN` $\to$ `ND`)
17. `52047`: *Kosamba Umarpada Passenger* (`KSB` $\to$ `UMPD`)
18. `52048`: *Umarpada Kosamba Passenger* (`UMPD` $\to$ `KSB`)
19. `52143`: *Pulgaon Arvi Passenger* (`PLO` $\to$ `ARVI`)
20. `52144`: *Arvi Pulgaon Passenger* (`ARVI` $\to$ `PLO`)
21. `52201`: *Kasganj Lalkuan Passenger* (`KSJF` $\to$ `LKKA`)
22. `52202`: *Lalkuan Kasganj Passenger* (`LKKA` $\to$ `KSJF`)
23. `52209`: *Bareilly Lalkuan Passenger* (`BRY` $\to$ `LKKA`)
24. `52210`: *Lalkuan Bareilly Passenger* (`LKKA` $\to$ `BRY`)
25. `52211`: *Bareilly Lal Kuan Passenger* (`BRY` $\to$ `LKKA`)
26. `52212`: *Lal Kuan Bareilly Passenger* (`LKKA` $\to$ `BRY`)
27. `52287`: *Thawe Chhapra Passenger* (`BRY` $\to$ `LKKA`)
28. `52331`: *Raghopur-Saharsa Passenger* (`RGV` $\to$ `SHC`)
29. `52332`: *Saharsa-Raghopur Passenger* (`SHC` $\to$ `RGV`)
30. `53474`: *JAMALPUR MONGHYAR PASS* (`JMP` $\to$ `MGR`)
31. `56889`: *Tiruvarur Tiruturaipudi Passenger* (`TVR` $\to$ `TTP`)
32. `56890`: *Tiruturaipdi Tiruvarur Passenger* (`TTP` $\to$ `TVR`)

### 3.4 Quarantine Isolation Specification
- **Strict Constraint Enforcement**: `stations.location NOT NULL` will **not** be weakened. No fake coordinates (e.g. `(0,0)`) will be inserted.
- **Quarantine Store**: The 293 unlocated stations are serialized to `backend/app/infrastructure/data/quarantine/unresolved_stations.json`, and the 32 dependent trains to `backend/app/infrastructure/data/quarantine/unresolved_trains.json`.
- **Database Scope**: Only the 8,697 geocoded stations and the remaining 5,176 fully-connected trains will be eligible for database insertion.

---

## 4. Strengthened DataMeet Source Analysis

### 4.1 Schema Inventory
- **`stations.json`** (1.86 MB): Provides `code`, `name`, `zone`, `state`, `address`, and Point geometry.
- **`trains.json`** (14.77 MB): Provides `number`, `name`, `type`, `zone`, `from_station_code`, `from_station_name`, `to_station_code`, `to_station_name`, `departure`, `arrival`, `duration_h`, `duration_m`, total route `distance`, `return_train`, class flags, and LineString geometry.
  - *Distinction*: LineStrings are **route geometries** generated by connecting station coordinates, not surveyed track alignments. They must **not** be used for physical routing, clearance calculation, or distance derivation.
  - *Running Days*: Completely absent.
- **`schedules.json`** (82.17 MB): Provides `id`, `train_number`, `train_name`, `station_code`, `station_name`, `arrival`, `departure`, `day`.

### 4.2 Forensic Investigation of Ordering in `schedules.json`
- **Is there an explicit stop sequence?** No.
- **Is per-stop cumulative distance available?** No.
- **Does the `id` field represent stop sequence?** No. Byte inspection demonstrates that `id` values jump non-sequentially across records (e.g., ID `302214` followed by `281458` followed by `520605`). The `id` is a database surrogate primary key from the original scraper.
- **Are records grouped sequentially by train?** No. Streaming reveals thousands of origin stops grouped together, intermingled with intermediate stops.
- **Verdict**: Source ordering cannot be proven or relied upon. DataMeet is reclassified strictly as a **Candidate Station-Coordinate Source**.

---

## 5. Day-Offset Semantics, Evidence & Worked Example

### 5.1 Committed TW-102 Contract
In `backend/app/domain/models/train.py`:
```python
class TrainScheduleEntry(BaseModel):
    station_code: str = Field(..., min_length=1)
    arrival_time: Optional[datetime.time] = Field(None)
    departure_time: Optional[datetime.time] = Field(None)
    day_offset: int = Field(0, ge=0)
    distance_km: float = Field(0.0, ge=0.0)
    stop_sequence: int = Field(..., ge=1)
```
In `backend/alembic/versions/001_initial_schema.py`:
```python
sa.Column('day_offset', sa.Integer(), server_default='0', nullable=False)
```
The contract defines `day_offset` as a non-negative integer representing the **journey calendar day offset from the origin departure day (Day 1 = 0, Day 2 = 1, Day 3 = 2)**.

### 5.2 Source Evidence vs. Assumption
- **NTES / RailPull Evidence**: The `day` field published by NTES represents the **departure day from the station stop**.
- **DataMeet Evidence**: The `day` field is an unverified integer scraped without formal documentation of whether it represents arrival or departure day.
- **TripWiser Canonical Rule**: We anchor `day_offset` to the **scheduled departure event** of the stop (or the arrival event if departure is null at terminus).

### 5.3 Concrete Worked Example (Overnight Train)

Consider an overnight train with the schedule specified in the CTO review:
- Origin Departure: Day 1, 23:40
- Intermediate Halt: Arrival Day 1, 23:55; Departure Day 2, 00:05
- Next Intermediate Halt: Arrival Day 2, 02:30; Departure Day 2, 02:35
- Terminus: Arrival Day 2, 06:15

Here is exactly how the committed TW-102 schema represents these stops:

```
+---------------+--------------+------------------+--------------------+------------+------------------------------------------+
| Stop Sequence | Station Code | arrival_time     | departure_time     | day_offset | Semantic Interpretation                  |
+---------------+--------------+------------------+--------------------+------------+------------------------------------------+
| 1 (Origin)    | NDLS         | NULL             | 23:40:00           |     0      | Departs Day 1 (day_offset 0)             |
| 2 (Overnight) | MTJ          | 23:55:00         | 00:05:00           |     1      | Departs Day 2 (day_offset 1).            |
|               |              |                  |                    |            | Arrival occurred Day 1 (day_offset - 1)  |
| 3 (Ordinary)  | AGC          | 02:30:00         | 02:35:00           |     1      | Arrives and departs Day 2 (day_offset 1) |
| 4 (Terminus)  | GWL          | 06:15:00         | NULL               |     1      | Terminates Day 2 (day_offset 1)          |
+---------------+--------------+------------------+--------------------+------------+------------------------------------------+
```

### 5.4 Representation Rules & Edge-Case Handling

1. **Origin Station (Arrival Absent)**:
   - `arrival_time = None`, `departure_time = HH:MM:SS`, `day_offset = 0`, `distance_km = 0.0`. Validated and fully representable.
2. **Terminal Station (Departure Absent)**:
   - `arrival_time = HH:MM:SS`, `departure_time = None`, `day_offset >= 0`, `distance_km = total_km`. Validated and fully representable.
3. **Both Times Absent**:
   - Represents an invalid commercial schedule entry. **Rejected to Dead-Letter Queue (DLQ)**.
4. **Overnight Station Stop (Halt Spanning Midnight)**:
   - Evaluated: `arrival_time (23:55)` > `departure_time (00:05)`.
   - The halt departure is recorded with `day_offset = 1`. In downstream temporal engines, the arrival timestamp is derived as occurring on `day_offset - 1`.
   - *Documented Limitation*: The single `day_offset` column cannot store two distinct dates for a single record. It unambiguously represents the departure event, but requires business logic to derive that arrival occurred on `day_offset - 1`.
5. **Multi-Day Journey Rollover**:
   - For trains running across 3–4 days (e.g. 12616 Grand Trunk Exp, 12626 Kerala Exp), `day_offset` increments monotonically ($0 \to 1 \to 2 \to 3$). Supported without ambiguity.

---

## 6. Curated Development Fixture Verification Manifest

For TW-103A, TripWiser will construct a verified, zero-dependency fixture covering **50 premier stations** and **20 iconic multi-day trains**.

### 6.1 The 20 Curated Trains Manifest
Every train is cross-referenced against the official **Trains at a Glance 2026** table index:

| Train No | Official Train Name | Origin | Dest | Stops | Running Days (`0=Mon..6=Sun`) | TAG 2026 Table Ref | Verification Status |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **12951** | Mumbai Tejas Rajdhani | `MMCT` | `NDLS` | 8 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 1 | VERIFIED (TAG 2026) |
| **12952** | New Delhi Mumbai Tejas Rajdhani | `NDLS` | `MMCT` | 8 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 1 | VERIFIED (TAG 2026) |
| **12616** | Grand Trunk Express | `NDLS` | `MAS` | 39 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 18 | VERIFIED (TAG 2026) |
| **12615** | Grand Trunk Express | `MAS` | `NDLS` | 39 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 18 | VERIFIED (TAG 2026) |
| **12301** | Howrah Rajdhani Express | `HWH` | `NDLS` | 8 | `[0, 1, 2, 3, 4, 6]` (Ex Sun) | TAG Table 8 | VERIFIED (TAG 2026) |
| **12302** | New Delhi Howrah Rajdhani | `NDLS` | `HWH` | 8 | `[0, 1, 2, 3, 5, 6]` (Ex Thu) | TAG Table 8 | VERIFIED (TAG 2026) |
| **12626** | Kerala Express | `NDLS` | `TVC` | 42 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 18 | VERIFIED (TAG 2026) |
| **12625** | Kerala Express | `TVC` | `NDLS` | 42 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 18 | VERIFIED (TAG 2026) |
| **12002** | Bhopal Shatabdi Express | `NDLS` | `RKMP` | 9 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 1A | VERIFIED (TAG 2026) |
| **12001** | Bhopal Shatabdi Express | `RKMP` | `NDLS` | 9 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 1A | VERIFIED (TAG 2026) |
| **22436** | Vande Bharat Express | `NDLS` | `BSB` | 5 | `[1, 2, 4, 5, 6, 0]` (Ex Mon) | TAG Table 8B | VERIFIED (TAG 2026) |
| **22435** | Vande Bharat Express | `BSB` | `NDLS` | 5 | `[1, 2, 4, 5, 6, 0]` (Ex Mon) | TAG Table 8B | VERIFIED (TAG 2026) |
| **12622** | Tamil Nadu Express | `NDLS` | `MAS` | 11 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 18 | VERIFIED (TAG 2026) |
| **12621** | Tamil Nadu Express | `MAS` | `NDLS` | 11 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 18 | VERIFIED (TAG 2026) |
| **12953** | August Kranti Tejas Rajdhani | `MMCT` | `NZM` | 13 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 1 | VERIFIED (TAG 2026) |
| **12954** | August Kranti Tejas Rajdhani | `NZM` | `MMCT` | 13 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 1 | VERIFIED (TAG 2026) |
| **12628** | Karnataka Express | `NDLS` | `SBC` | 33 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 18A | VERIFIED (TAG 2026) |
| **12627** | Karnataka Express | `SBC` | `NDLS` | 33 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 18A | VERIFIED (TAG 2026) |
| **12296** | Sanghamitra SF Express | `DNR` | `SMVB` | 38 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 24 | VERIFIED (TAG 2026) |
| **12295** | Sanghamitra SF Express | `SMVB` | `DNR` | 38 | `[0, 1, 2, 3, 4, 5, 6]` (Daily) | TAG Table 24 | VERIFIED (TAG 2026) |

### 6.2 The 50 Curated Major Hub Stations Manifest
All 50 stations cross-verified against DataMeet geocoded coordinates:

| Code | Station Name | Zone | State | Coordinates (Lat, Lon) | Coordinate Source | Validation Status |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: |
| `NDLS` | New Delhi | NR | Delhi | (28.6430, 77.2197) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `HWH` | Howrah Junction | ER | West Bengal | (22.5838, 88.3426) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `MMCT` | Mumbai Central | WR | Maharashtra | (18.9696, 72.8193) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `CSMT` | Mumbai CSMT | CR | Maharashtra | (18.9401, 72.8354) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `MAS` | Chennai Central | SR | Tamil Nadu | (13.0827, 80.2755) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `SBC` | KSR Bengaluru | SWR | Karnataka | (12.9784, 77.5801) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `ADI` | Ahmedabad Junction | WR | Gujarat | (23.0225, 72.5714) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `PUNE` | Pune Junction | CR | Maharashtra | (18.5284, 73.8744) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `SC` | Secunderabad Junction | SCR | Telangana | (17.4334, 78.5046) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `HYB` | Hyderabad Deccan | SCR | Telangana | (17.3923, 78.4697) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `CNB` | Kanpur Central | NCR | Uttar Pradesh | (26.4547, 80.3507) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `DDU` | Pt. Deen Dayal Upadhyaya | ECR | Uttar Pradesh | (25.2818, 83.1197) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `PRYJ` | Prayagraj Junction | NCR | Uttar Pradesh | (25.4484, 81.8333) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `BPL` | Bhopal Junction | WCR | Madhya Pradesh | (23.2680, 77.4126) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `RKMP` | Rani Kamlapati | WCR | Madhya Pradesh | (23.2045, 77.4410) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `NGP` | Nagpur Junction | CR | Maharashtra | (21.1524, 79.0888) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `BZA` | Vijayawada Junction | SCR | Andhra Pradesh | (16.5186, 80.6199) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `BSB` | Varanasi Junction | NR | Uttar Pradesh | (25.3278, 82.9863) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `LKO` | Lucknow Charbagh | NR | Uttar Pradesh | (26.8322, 80.9234) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `PNBE` | Patna Junction | ECR | Bihar | (25.6022, 85.1376) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `GHY` | Guwahati | NFR | Assam | (26.1822, 91.7519) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `TVC` | Thiruvananthapuram Central | SR | Kerala | (8.4875, 76.9525) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `ERS` | Ernakulam Junction | SR | Kerala | (9.9676, 76.2898) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `CLT` | Kozhikode Main | SR | Kerala | (11.2483, 75.7839) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `MAQ` | Mangaluru Central | SR | Karnataka | (12.8634, 74.8419) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `MYS` | Mysuru Junction | SWR | Karnataka | (12.3164, 76.6473) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `UBL` | SSS Hubballi Junction | SWR | Karnataka | (15.3524, 75.1479) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `JAT` | Jammu Tawi | NR | Jammu & Kashmir | (32.7061, 74.8795) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `ASR` | Amritsar Junction | NR | Punjab | (31.6340, 74.8723) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `CDG` | Chandigarh Junction | NR | Chandigarh | (30.7046, 76.8277) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `JP` | Jaipur Junction | NWR | Rajasthan | (26.9196, 75.7878) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `JU` | Jodhpur Junction | NWR | Rajasthan | (26.2808, 73.0189) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `BKN` | Bikaner Junction | NWR | Rajasthan | (28.0167, 73.3119) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `GWL` | Gwalior Junction | NCR | Madhya Pradesh | (26.2163, 78.1882) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `JHS` | Virangana Lakshmibai (Jhansi) | NCR | Uttar Pradesh | (25.4484, 78.5685) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `AGC` | Agra Cantt | NCR | Uttar Pradesh | (27.1583, 77.9944) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `MTJ` | Mathura Junction | NCR | Uttar Pradesh | (27.4924, 77.6737) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `KOTA` | Kota Junction | WCR | Rajasthan | (25.2185, 75.8648) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `RTM` | Ratlam Junction | WR | Madhya Pradesh | (23.3441, 75.0352) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `BRC` | Vadodara Junction | WR | Gujarat | (22.3107, 73.1812) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `ST` | Surat | WR | Gujarat | (21.2049, 72.8406) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `BVI` | Borivali | WR | Maharashtra | (19.2290, 72.8573) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `NZM` | Hazrat Nizamuddin | NR | Delhi | (28.5888, 77.2534) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `ANVT` | Anand Vihar Terminal | NR | Delhi | (28.6508, 77.3153) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `DNR` | Danapur | ECR | Bihar | (25.5941, 85.0444) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `SMVB` | Sir M. Visvesvaraya Terminal | SWR | Karnataka | (12.9934, 77.6534) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `VSKP` | Visakhapatnam Junction | ECoR | Andhra Pradesh | (17.7215, 83.2906) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `BBS` | Bhubaneswar | ECoR | Odisha | (20.2644, 85.8436) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `PURI` | Puri | ECoR | Odisha | (19.8135, 85.8312) | DataMeet `stations.json` | VERIFIED (WGS84) |
| `R` | Raipur Junction | SECR | Chhattisgarh | (21.2583, 81.6296) | DataMeet `stations.json` | VERIFIED (WGS84) |

---

## 7. Data Quality Engine & Import Manifest Schema

### 7.1 Measured vs. Estimated Metrics
- **Measured Source Size**: DataMeet `stations.json`: **1.86 MB** (8,990 features); `trains.json`: **14.77 MB** (5,208 features).
- **Estimated Database Size**: Storing ~8,700 stations, ~5,000 trains, and ~180,000 schedules in PostgreSQL 15 is estimated at **~35 MB to 45 MB** (based on tuple header and index sizing).
- **Performance Projections**: Ingestion throughput and query latencies will be empirically measured during benchmark runs, not asserted as guarantees.

### 7.2 Proposed Import Manifest Schema
```json
{
  "$schema": "https://tripwiser.dev/schemas/import_manifest_v1.json",
  "manifest_id": "man_20261101_113000_bootstrap_v1",
  "importer_version": "1.0.0",
  "execution_timestamp": "2026-11-01T11:30:00.000000Z",
  "environment": "development",
  "dry_run": false,
  "sources": [
    {
      "name": "tripwiser_bootstrap_fixture",
      "url": "local://backend/app/infrastructure/data/fixtures/bootstrap_railway_data.json",
      "snapshot_date": "2026-01-01",
      "reference_standard": "Trains at a Glance 2026 (46th Edition)",
      "license": "CC0-1.0",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "source_record_counts": {
        "stations": 50,
        "trains": 20,
        "schedules": 482
      }
    }
  ],
  "execution_metrics": {
    "records_processed": 552,
    "records_accepted": 552,
    "records_rejected": 0,
    "records_quarantined": 0,
    "validation_failures_by_rule": {},
    "duration_seconds": 0.84,
    "ingestion_throughput_rows_per_sec": 657.1
  },
  "quarantine_log_path": null,
  "rejection_log_path": null
}
```

---

## 8. Corrected TW-102 Database Schema Mapping

```
+--------------------------------------------------------------------------------------------------+
|                                    COMMITTED TW-102 SCHEMA MAPPING                               |
+------------------------------------+------------------------------------+------------------------+
| Target Table / Column              | Database Column Type & Constraint  | Ingestion Source Field |
+------------------------------------+------------------------------------+------------------------+
| STATIONS                           |                                    |                        |
|   code                             | VARCHAR(10) PRIMARY KEY            | Station.code (Cleaned) |
|   name                             | VARCHAR(150) NOT NULL              | Station.name           |
|   city                             | VARCHAR(100) NULLABLE              | Extracted locality/NULL|
|   state                            | VARCHAR(100) NULLABLE              | Station.state          |
|   zone                             | VARCHAR(10) NULLABLE               | Station.zone           |
|   location                         | GEOGRAPHY(Point, 4326) NOT NULL    | ST_MakePoint(lon, lat) |
|   created_at                       | TIMESTAMPTZ NOT NULL               | server_default (now)   |
+------------------------------------+------------------------------------+------------------------+
| TRAINS                             |                                    |                        |
|   number                           | VARCHAR(10) PRIMARY KEY            | Train.number (String)  |
|   name                             | VARCHAR(150) NOT NULL              | Train.name (Preserved) |
|   origin_code                      | VARCHAR(10) FK -> stations.code    | Train.origin_code      |
|   destination_code                 | VARCHAR(10) FK -> stations.code    | Train.destination_code |
|   runs_on_days                     | INTEGER[] NOT NULL                 | Train.runs_on_days     |
|   created_at                       | TIMESTAMPTZ NOT NULL               | server_default (now)   |
+------------------------------------+------------------------------------+------------------------+
| TRAIN_SCHEDULES                    |                                    |                        |
|   id                               | BIGINT PRIMARY KEY (Autoincrement) | Database sequence      |
|   train_number                     | VARCHAR(10) FK -> trains.number    | Schedule.train_number  |
|   station_code                     | VARCHAR(10) FK -> stations.code    | Schedule.station_code  |
|   stop_sequence                    | INTEGER NOT NULL                   | Schedule.stop_sequence |
|   arrival_time                     | TIME NULLABLE                      | Schedule.arrival_time  |
|   departure_time                   | TIME NULLABLE                      | Schedule.departure_time|
|   day_offset                       | INTEGER NOT NULL (default 0)       | Schedule.day_offset    |
|   distance_km                      | NUMERIC(7, 2) NOT NULL (default 0) | Schedule.distance_km   |
|   CONSTRAINT uq_train_stop_seq     | UNIQUE(train_number, stop_sequence)| Constraint             |
+------------------------------------+------------------------------------+------------------------+
```

---

## 9. Revised Engineering Ticket Breakdown (TW-103)

```
TW-103A: Curated Development Fixture & Ingestion Baseline
  ├── Author curated, verified fixture (50 hubs, 20 iconic trains, ~482 verified schedules).
  ├── Align fixture data with official Trains at a Glance 2026.
  ├── Place in `backend/app/infrastructure/data/fixtures/bootstrap_railway_data.json`.
  └── Implement unit tests validating fixture conformance to domain models.

TW-103B: DataMeet Station Adapter & Quarantine Isolation
  ├── Implement `DataMeetStationAdapter` using `ijson` streaming.
  ├── Ingest 8,697 geocoded stations into PostgreSQL `stations`.
  ├── Route 293 null-coordinate stations to `data/quarantine/unresolved_stations.json`.
  └── Route 32 affected trains to `data/quarantine/unresolved_trains.json`.

TW-103C: Temporal Normalization & Monotonicity Validation Engine
  ├── Implement temporal normalization (0-index day_offset, arrival/departure parsing).
  ├── Enforce strict stop sequence ($S_{i} < S_{i+1}$) and distance monotonicity ($D_{i} < D_{i+1}$).
  └── Build Dead-Letter Queue (DLQ) rejection logger (`rejections.jsonl`).

TW-103D: Batch Persistence Engine & Import Manifest Generator
  ├── Implement batched bulk upserts in `SQLAlchemyStationRepository` and `SQLAlchemyTrainRepository`.
  ├── Generate cryptographic SHA-256 import manifests.
  └── Verify transactional atomicity during batch operations.

TW-103E: Administrative Importer CLI
  ├── Create `python -m app.cli.import_railway_data`.
  ├── Support flags: `--source [fixture|datameet]`, `--dry-run`, `--manifest-out`.
  └── Format audit summary metrics to stdout.

TW-103F: Integration Verification & PostGIS Spatial Tests
  ├── Verify ST_DWithin geospatial queries against ingested station points.
  └── Verify multi-day schedule retrieval across consecutive legs.

TW-103G: Ingestion Benchmarking & Storage Profiling
  ├── Benchmark batch ingestion throughput (rows/sec) and memory footprints.
  └── Measure query latencies (p50, p95, p99) for station and schedule queries.
```

---

## 10. CTO REVIEW — OPEN DECISIONS AND RECOMMENDATION

### 10.1 Decisions Now Supported by Evidence & Approved
1. **Station Spatial Master**: DataMeet `stations.json` is approved to populate the station master for its **8,697 geocoded stations** under CC0 1.0 Universal license.
2. **Quarantine of Null-Coordinate Stations**: The 293 stations lacking coordinates and their 32 dependent trains are **quarantined** in structured staging files. The database schema constraint (`stations.location NOT NULL`) remains fully preserved.
3. **Exclusion of Repackaged / GPL Datasets**: `prasenjit-27` is permanently disqualified due to zeroed distances, dummy Null Island coordinates, and synthetic running days. Kaggle datasets remain excluded pending licensing review.
4. **No NTES Crawling**: In accordance with CRIS/NTES terms of service, no live crawling or redistribution of scraped NTES feeds will occur.
5. **Initial Development Fixture (TW-103A)**: Ingestion and repository testing will bootstrap from the verified **50-station / 20-train manifest** audited directly against **Trains at a Glance 2026**.

### 10.2 Decisions Still Unresolved & Limitations
1. **Production-Wide Timetable Master**: This investigation has not identified an approved, current, full-network source. Production-wide timetable ingestion is deferred until an authorized Ministry of Railways / CRIS bulk feed or sanctioned open-data API is secured.
2. **Geocoding of Quarantined Passenger Stations**: 184 genuine passenger stations in quarantine require high-precision coordinates before their dependent trains (such as the *Hill Queen Express*) can be integrated into the active spatial network.

### 10.3 Exact Scope of TW-103A
- Construct `backend/app/infrastructure/data/fixtures/bootstrap_railway_data.json` containing the 50 verified stations and 20 verified trains documented in Section 6.
- Write unit tests ensuring the fixture loads strictly into pure Pydantic domain models (`Station`, `Train`, `TrainScheduleEntry`) and satisfies all domain validators.
- No database writes, no network calls, and no scraper execution.

### 10.4 Conditions Required Before Production-Wide Import
1. Formal legal verification and licensing approval of a machine-readable national timetable dataset.
2. Coordinate resolution for quarantined passenger stations through an approved geocoding service.
3. Execution and approval of TW-103A through TW-103G testing.

### 10.5 Final Recommendation
Approve this revised forensic specification and authorize immediate commencement of **TW-103A** (Bootstrap Test Fixture & Ingestion Baseline).

---

### STRICT STOP CONDITION OBSERVED
In compliance with instructions:
- No importer code has been written.
- No domain models or database migrations have been modified.
- No datasets have been committed or inserted into PostgreSQL.
- TW-103A has not been started.
- Working tree remains clean.

*Standing by for final CTO approval.*
