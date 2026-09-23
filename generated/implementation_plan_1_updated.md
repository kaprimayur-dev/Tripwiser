# Implementation Plan - TripWiser Engineering Kickoff & V1 Architecture (Revised)

## Overview & Executive Summary

**TripWiser** is a travel intelligence and route discovery product designed to solve a core problem in Indian Railway travel: **A direct train being unavailable does NOT mean the journey is impossible.**

Capacity frequently exists across alternate train combinations, intermediate transfer stations, nearby/upstream boarding stations, and post-chart vacant berth segments. TripWiser discovers these multi-leg, alternate, and vacant-berth options and presents them to the traveler in a clear, minimal, and relatable visual format.

This document establishes the revised technical architecture, domain models, database persistence layer, data providers, routing algorithms, database schemas, API contracts, state management, and ticket breakdown for V1 engineering.

> [!IMPORTANT]
> **Booking is strictly OUT OF SCOPE for V1.** TripWiser is a decision-support & itinerary discovery tool. It does not process payments, handle IRCTC user authentication, or book tickets. Clear copy reinforces: *"Vacant berth segments discovered. Booking/allotment is handled through the applicable railway process."*

---

## Key Architectural Corrections Summary

1. **Domain vs Infrastructure Separation**: Pure domain models (`domain/models`) have zero SQLAlchemy or DB dependencies. Database ORM models and repository implementations strictly reside in `infrastructure/database/`.
2. **Final Design System Tokens**: Cream (`#F4EFE4`), Espresso (`#191612`), Terracotta (`#B9532D`), Olive (`#67664A`). Typography uses bold editorial grotesk/display for large headings and clean sans-serif for UI/body. Lime green and serif-heavy styles removed.
3. **Search / Bachelor Special Separation**: `POST /api/v1/search/routes` strictly handles route discovery and ranking. Bachelor Special chart-vacancy discovery is decoupled into its own explicit endpoint (`POST /api/v1/bachelor/search`) and executes **only when explicitly requested**.
4. **Structured Availability Model**: Replaced raw string statuses with typed `AvailabilityResult` containing status enum (`AVAILABLE`, `RAC`, `WAITLIST`, `NOT_AVAILABLE`, `CHARTING_PENDING`), counts, fare, quota, and timestamps.
5. **Chart Vacancy Provenance**: Added `source`, `observed_at`, `expires_at`, `chart_phase`, and `status` to `chart_vacancies` table while preserving a clean domain `BerthSegment`.
6. **Explicit Bachelor Special Interval Semantics**: Formally defined continuity rule ($S_{\text{to}_i} = S_{\text{from}_{i+1}}$). Gap scenarios are strictly invalid.
7. **Direct-First Routing Strategy**: Search pipeline prioritizes direct train checks before executing multi-leg transfer path generation or nearby station expansions to minimize unnecessary live API calls.
8. **Multi-Factor Nearby Station Ranking**: Nearby station alternatives are scored across distance from original origin/destination, train journey time, transfers, fare, and availability.
9. **Docker Service Networking**: Container-to-container DB/Redis hostnames use environment variables (`postgres`, `redis`) rather than hardcoded `localhost`.
10. **Data Import Quality Criteria**: Updated data import validation from simple record counts to structural data integrity checks (no duplicate stations, monotonic stop sequences, valid coordinates, clean validation report).

---

## 1. Current Repository Assessment

- **Location**: `c:\projects\tripwiser`
- **State**: Empty root directory (Fresh repository initialization required).
- **Tooling to establish**:
  - Frontend: React / Next.js (App Router, TypeScript, Tailwind CSS, Lucide Icons, TanStack Query).
  - Backend: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 / Alembic, Async HTTP (`httpx`).
  - Database & Cache: PostgreSQL with PostGIS extension & `pgcrypto`/`uuid-ossp`, Redis.
  - Development Environment: Docker Compose (`docker-compose.yml`) containing PostgreSQL/PostGIS, Redis, FastAPI dev server, and Next.js frontend server.
  - Testing: `pytest` (Backend unit/integration tests), `vitest` / `playwright` (Frontend unit & E2E tests).

---

## 2. Proposed Final Project Structure

A clean layer-separated architecture strictly isolating domain business logic from database ORM models and HTTP controllers:

```
tripwiser/
├── docker-compose.yml
├── README.md
├── frontend/                   # Next.js App Router Application
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── next.config.js
│   ├── public/                 # Static visual assets
│   └── src/
│       ├── app/                # Next.js Pages (Search, Results, Journey Details, Bachelor Special)
│       ├── components/         # UI Components (Cards, Timeline, StationSelector, FilterBar)
│       ├── hooks/              # Custom React Hooks & Query Hooks
│       ├── services/           # API Client Services
│       ├── types/              # TypeScript Types & Interfaces
│       └── lib/                # Design tokens (#F4EFE4, #191612, #B9532D, #67664A), utilities
├── backend/                    # FastAPI Backend Server
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/                # Database Migrations
│   ├── app/
│   │   ├── main.py             # FastAPI App Entrypoint
│   │   ├── core/               # Configuration, logging, redis, DB session
│   │   │   ├── config.py
│   │   │   ├── db.py
│   │   │   └── redis.py
│   │   ├── domain/             # Pure Domain Models & Business Logic (NO DB / SQLAlchemy imports!)
│   │   │   ├── models/         # Station, Train, Route, Itinerary, AvailabilityResult, BerthSegment
│   │   │   ├── routing/        # Candidate corridor generator, temporal validator, path matcher
│   │   │   ├── bachelor/       # Bachelor Special berth stitching & interval coverage engine
│   │   │   ├── ranking/        # Multi-factor route & nearby ranking policy engines
│   │   │   └── repositories/   # Abstract Repository Interfaces (StationRepository, TrainRepository)
│   │   ├── infrastructure/     # Database ORM, Repositories, External Clients
│   │   │   ├── database/
│   │   │   │   ├── models/     # SQLAlchemy ORM Models (StationORM, TrainORM, ScheduleORM, VacancyORM)
│   │   │   │   └── repositories/ # SQLAlchemy Repository Implementations
│   │   │   └── providers/      # Provider Adapters (TrainDataProvider, AvailabilityProvider, etc.)
│   │   │       ├── base.py
│   │   │       ├── mock/
│   │   │       ├── static_graph/
│   │   │       └── live/
│   │   ├── services/           # Application Use-Cases / Service Layer
│   │   │   ├── search_service.py
│   │   │   ├── nearby_service.py
│   │   │   └── bachelor_service.py
│   │   └── api/                # FastAPI Routers & HTTP Controllers
│   │       ├── v1/
│   │       │   ├── search.py
│   │       │   ├── stations.py
│   │       │   ├── bachelor.py
│   │       │   └── health.py
│   │       └── schemas/        # Request & Response Pydantic DTOs
│   └── tests/
│       ├── unit/               # Domain & algorithm unit tests
│       ├── integration/        # DB & provider integration tests
│       └── e2e/                # API end-to-end flow tests
└── data/                       # Static Railway Datasets & Scripts
    ├── raw/                    # DataMeet / data.gov.in raw CSV/JSON
    └── scripts/                # Data import & graph validation scripts
```

---

## 3. Architecture Diagram

```mermaid
graph TD
    User([Traveler / Web Browser]) -->|HTTP / JSON| Frontend[Next.js Frontend\nTypeScript + Tailwind]
    
    subgraph Frontend Layer
        Frontend --> ReactQuery[TanStack Query State Management]
        ReactQuery --> UIComponents[UI Components\nSearch Form / Route Cards / Bachelor Timeline]
    end

    Frontend -->|REST API| APIGateway[FastAPI API Layer]

    subgraph Backend Application Layer
        APIGateway --> Controllers[API Routers & DTO Validation\n/search, /stations, /bachelor, /health]
        Controllers --> ServiceLayer[Application Service Layer]
        
        subgraph Pure Domain Layer (No DB Dependencies)
            ServiceLayer --> DirectSearch[Direct-First Search Controller]
            DirectSearch --> RoutingEngine[Candidate Corridor & Train Matcher]
            RoutingEngine --> TemporalEngine[Temporal Validator]
            ServiceLayer --> BachelorEngine[Bachelor Special Interval Stitcher]
            ServiceLayer --> RankingEngine[Multi-Factor Ranking Engine]
            ServiceLayer --> NearbyEngine[Nearby Station Scorer]
        end

        subgraph Infrastructure Layer
            ServiceLayer --> Repositories[DB Repositories Implementations]
            ServiceLayer --> ProviderAbstraction[Internal Provider Adapters]
            ProviderAbstraction --> MockProvider[Dev/Mock Provider]
            ProviderAbstraction --> LiveAPIAdapter[Live Railway API Adapter]
        end
    end

    subgraph Storage & Infrastructure
        Repositories --> Postgres[(PostgreSQL + PostGIS\nStatic Stations/Trains/Schedules/Vacancies)]
        ServiceLayer --> RedisCache[(Redis Cache\nRoutes & Availability)]
    end
```

---

## 4. Domain Entities (Pure Python / Pydantic v2 Models)

Domain models contain zero SQLAlchemy attributes or database dependencies.

### 4.1 Station & Train
```python
from pydantic import BaseModel
from typing import Optional
from datetime import time, datetime, date
from enum import Enum

class Station(BaseModel):
    code: str                  # e.g., "GWL", "BPL", "JHS"
    name: str                  # e.g., "Gwalior Junction"
    latitude: float
    longitude: float
    city: Optional[str] = None
    zone: Optional[str] = None

class TrainScheduleEntry(BaseModel):
    station_code: str
    arrival_time: Optional[time]   # None for origin
    departure_time: Optional[time] # None for destination
    day_offset: int                # 0 for Day 1, 1 for Day 2
    distance_km: float
    stop_sequence: int

class Train(BaseModel):
    number: str                # e.g., "12616"
    name: str                  # e.g., "Grand Trunk Express"
    origin_code: str
    destination_code: str
    runs_on_days: list[int]    # [0, 1, 2, 3, 4, 5, 6] (Mon=0)
    schedule: list[TrainScheduleEntry]
```

### 4.2 Structured Availability Result
```python
class AvailabilityStatusCode(str, Enum):
    AVAILABLE = "AVAILABLE"
    RAC = "RAC"
    WAITLIST = "WAITLIST"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    CHARTING_PENDING = "CHARTING_PENDING"

class AvailabilityResult(BaseModel):
    status: AvailabilityStatusCode
    available_count: Optional[int] = None
    waitlist_count: Optional[int] = None
    quota: str = "GN"              # General Quota
    travel_class: str = "3A"       # e.g., "SL", "3A", "2A"
    fare: float
    checked_at: datetime
    source: str                    # Provider identifier
```

### 4.3 Journey Leg & Candidate Route
```python
class JourneyLeg(BaseModel):
    train_number: str
    train_name: str
    origin_code: str
    destination_code: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    travel_class: str
    distance_km: float
    availability: AvailabilityResult

class CandidateRoute(BaseModel):
    route_id: str
    legs: list[JourneyLeg]
    total_duration_minutes: int
    total_fare: float
    transfer_count: int
    transfer_durations_minutes: list[int]
    is_direct: bool
    score: float = 0.0
```

### 4.4 Bachelor Special Berth Segment & Itinerary
```python
class BerthSegment(BaseModel):
    segment_id: str
    train_number: str
    date: date
    coach: str                   # e.g., "B2"
    berth_number: int            # e.g., 43
    berth_type: str              # e.g., "UB", "MB", "LB", "SL", "SU"
    from_station_code: str
    to_station_code: str
    from_sequence: int
    to_sequence: int

class BachelorSpecialItinerary(BaseModel):
    train_number: str
    train_name: str
    origin_code: str
    destination_code: str
    travel_date: date
    travel_class: str
    segments: list[BerthSegment] # Consecutive, gapless coverage
    total_segment_count: int
    is_continuous: bool = True
```

---

## 5. Database Schema & Infrastructure ORM Proposal (PostgreSQL + PostGIS)

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Stations Table
CREATE TABLE stations (
    code VARCHAR(10) PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(100),
    zone VARCHAR(10),
    location GEOGRAPHY(POINT, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_stations_location ON stations USING GIST (location);

-- Trains Table
CREATE TABLE trains (
    number VARCHAR(10) PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    origin_code VARCHAR(10) REFERENCES stations(code),
    destination_code VARCHAR(10) REFERENCES stations(code),
    runs_on_days INT[] NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Train Schedules Table
CREATE TABLE train_schedules (
    id BIGSERIAL PRIMARY KEY,
    train_number VARCHAR(10) REFERENCES trains(number) ON DELETE CASCADE,
    station_code VARCHAR(10) REFERENCES stations(code),
    stop_sequence INT NOT NULL,
    arrival_time TIME,
    departure_time TIME,
    day_offset INT NOT NULL DEFAULT 0,
    distance_km NUMERIC(7, 2) NOT NULL DEFAULT 0.0,
    UNIQUE (train_number, stop_sequence)
);
CREATE INDEX idx_schedules_lookup ON train_schedules (station_code, train_number);
CREATE INDEX idx_schedules_sequence ON train_schedules (train_number, stop_sequence);

-- Cached Chart Vacancies Table (Includes freshness and provenance)
CREATE TABLE chart_vacancies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    train_number VARCHAR(10) REFERENCES trains(number),
    chart_date DATE NOT NULL,
    coach VARCHAR(10) NOT NULL,
    berth_number INT NOT NULL,
    berth_type VARCHAR(10) NOT NULL DEFAULT 'UB',
    travel_class VARCHAR(10) NOT NULL,
    from_station_code VARCHAR(10) REFERENCES stations(code),
    to_station_code VARCHAR(10) REFERENCES stations(code),
    from_sequence INT NOT NULL,
    to_sequence INT NOT NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'chart_feed',
    chart_phase VARCHAR(50) NOT NULL DEFAULT 'FIRST_CHART', -- 'FIRST_CHART' | 'SECOND_CHART'
    status VARCHAR(20) NOT NULL DEFAULT 'VACANT',         -- 'VACANT' | 'BOOKED' | 'EXPIRED'
    observed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX idx_vacancies_search ON chart_vacancies (train_number, chart_date, from_sequence, to_sequence, status);
```

---

## 6. API Surface & Endpoints

### 6.1 Health & Diagnostics
- `GET /api/v1/health`: Basic liveness check. Returns `{"status": "ok"}`.
- `GET /api/v1/health/ready`: Readiness check verifying database and Redis connectivity.

### 6.2 Station Selection / Autocomplete
- `GET /api/v1/stations/search?q=GWL`: Autocomplete endpoint returning station matching code or name.

### 6.3 Route Discovery (Direct-First)
- `POST /api/v1/search/routes`
  - **Payload**: `{ "origin_code": "GWL", "destination_code": "BPL", "travel_date": "2026-10-15", "preferred_class": "3A", "include_nearby": false }`
  - **Behavior**: Direct-first search strategy. Performs live availability check on direct trains first. Only fetches transfer/nearby paths if direct options are unavailable or requested.
  - **Note**: Does **NOT** execute Bachelor Special chart-vacancy checks.

### 6.4 Bachelor Special Search
- `POST /api/v1/bachelor/search`
  - **Payload**: `{ "train_number": "12616", "origin_code": "GWL", "destination_code": "BPL", "travel_date": "2026-10-15" }`
  - **Behavior**: Executes berth segment interval stitching algorithm over chart vacancy data for the specific train and date.

---

## 7. Routing Engine & Direct-First Search Pipeline

```mermaid
graph TD
    A[Search Request: Origin -> Destination] --> B[Phase 1: Fetch Direct Trains servicing Origin & Destination]
    B --> C{Direct Trains Exist?}
    
    C -- Yes --> D[Match Train Schedules & Day Offsets]
    D --> E[Check Live Availability for Direct Trains]
    E --> F{Direct Trains Available?}
    
    F -- Yes (Confirmed Available) --> G[Assemble Direct Itineraries]
    G --> H[Return Direct Routes Prominently\n(Optional Expand button for Transfers/Nearby)]
    
    F -- No (Sold Out / Waitlisted / None) --> I[Phase 2: Generate Candidate Corridors from Static Graph]
    C -- No --> I
    
    I --> J[Train/Service Matching for Transfer Legs]
    J --> K[Temporal Validation: Min 45m, Max 240m Layover]
    K --> L[Check Live Availability for Viable Candidates]
    L --> M[Assemble Multi-Leg Routes]
    
    M --> N{Any Alternate Routes Found?}
    N -- No --> O[Phase 3: Nearby Station Expansion (PostGIS)]
    O --> P[Score Nearby Routes (Distance + Travel Time + Fare)]
    P --> Q[Final Multi-Factor Ranking & Response]
    N -- Yes --> Q
```

### Routing Pipeline Steps:
1. **Static Connectivity & Candidate Corridors**: Graph traversal identifies valid station corridor sequences $S = [A, M_1, \dots, B]$ (max 2 transfers).
2. **Train & Service Matching**: Matches physical train schedules running on the exact day of travel for each leg.
3. **Temporal Validation**: Ensures layover constraints:
   $$\text{Arrival}(Leg_i) + 45\text{ mins} \le \text{Departure}(Leg_{i+1}) \le \text{Arrival}(Leg_i) + 240\text{ mins}$$
4. **Live Availability Check**: Invoked **only** for candidate legs passing temporal validation.
5. **Itinerary Assembly & Multi-Factor Ranking**: Ranks options according to total journey time, fare, number of transfers, and class consistency.

---

## 8. Bachelor Special Interval Semantics & Continuity Rules

The Bachelor Special engine solves a strict **berth segment interval coverage problem**.

### Continuity Rule (Gapless Coverage)
For a requested train journey with station sequence indices $1, 2, \dots, N$ (where $1 = \text{Origin}$ and $N = \text{Destination}$):
A set of berth vacancy segments $V = \{v_1, v_2, \dots, v_k\}$ forms a valid Bachelor Special itinerary **if and only if**:
1. $v_1.\text{from\_sequence} = 1$
2. $v_k.\text{to\_sequence} = N$
3. For all $i \in [1, k-1]$: $v_i.\text{to\_sequence} = v_{i+1}.\text{from\_sequence}$ (No gaps permitted between segments!).
4. For all $i$: $v_i.\text{status} = \text{'VACANT'}$ and $v_i.\text{expires\_at} > \text{now()}$.

### Examples:
- **Continuous (Valid)**: $[GWL \to JHS \text{ (Coach B2, Berth 43)}]$, $[JHS \to BHA \text{ (Coach B3, Berth 21)}]$, $[BHA \to BPL \text{ (Coach B1, Berth 18)}]$.
- **Gap (Invalid)**: $[GWL \to JHS]$, $[BHA \to BPL]$ (Gap between Jhansi and Vidisha where no berth is vacant).
- **Overlap (Resolved)**: $[GWL \to BHA]$, $[JHS \to BPL]$ (Stitching algorithm prunes redundant overlap to create optimal handoff at $JHS$).

---

## 9. Multi-Factor Nearby Station Ranking

Nearby station alternatives expand search bounds using PostGIS spatial radius queries (`ST_DWithin`).
However, proximity alone is **not** the sole ranking factor. Nearby options are scored using a weighted multi-factor utility function:

$$\text{Score} = w_1 \cdot \text{Duration} + w_2 \cdot \text{Fare} + w_3 \cdot \text{Transfers} + w_4 \cdot \text{OriginDistance} + w_5 \cdot \text{DestDistance}$$

Where:
- `OriginDistance` / `DestDistance`: Road/transit distance from the user's requested origin/destination to the nearby station.
- `Duration`: Total train journey duration.
- `Transfers`: Penalty for connection count.

---

## 10. Frontend Architecture & Design System Tokens

### Color Palette (Finalized Design Tokens)
- **Cream (Background)**: `#F4EFE4` (`bg-[#F4EFE4]`)
- **Espresso (Primary Text & Dark Surfaces)**: `#191612` (`text-[#191612]`)
- **Terracotta (Primary Accent & CTA)**: `#B9532D` (`bg-[#B9532D]`)
- **Olive (Secondary Accent & Badges)**: `#67664A` (`bg-[#67664A]`)
- **Supporting Neutral**: Soft Warm White (`#FFFFFF`), Stone Gray (`#E7E2D7`), Muted Border (`#D8D2C4`).
- **STRICT RULE**: No lime green, no generic bootstrap blue/red, no dark AI neon themes.

### Typography
- **Headings**: Bold editorial grotesk / display font (e.g. *Space Grotesk*, *Cabinet Grotesk*, or custom display sans).
- **UI & Body**: Clean modern sans-serif (*Inter* / system sans).
- **STRICT RULE**: No Playfair Display or Georgia as primary visual direction.

---

## 11. Configuration & Docker Networking Strategy

Docker containers interact over the internal Docker network using container service names rather than `localhost`:

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "TripWiser API"
    ENVIRONMENT: str = "development"
    
    # DB & Redis URLs (Use environment variables in Docker)
    DATABASE_URL: str = "postgresql+asyncpg://tripwiser:tripwiser@postgres:5432/tripwiser_db"
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Provider Flags
    AVAILABILITY_PROVIDER: str = "mock"
    CHART_VACANCY_PROVIDER: str = "mock"
    
    # Routing Constraints
    MIN_TRANSFER_MINUTES: int = 45
    MAX_LAYOVER_MINUTES: int = 240
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 12. Testing & Quality Assurance Strategy

### Unit Testing (`pytest`)
1. **Domain Models**: Validation of Pydantic models with zero DB coupling.
2. **Bachelor Special Stitching Suite**: Explicit testing of 8 required interval coverage test scenarios:
   - Scenario 1: One vacant berth covers entire journey.
   - Scenario 2: Two berth segments cover journey.
   - Scenario 3: Three berth segments cover journey.
   - Scenario 4: Gap exists between segments (Returns no valid coverage).
   - Scenario 5: Segment overlap exists (Pruned into valid sequence).
   - Scenario 6: Multiple valid stitching combinations exist (Ranks by minimal coach changes).
   - Scenario 7: No valid complete coverage exists.
   - Scenario 8: Vacancy record is expired (`expires_at < now()`).

### E2E Testing (`playwright`)
- Validates search and filtering UI using finalized product filter names: `Recommended`, `Cheapest`, `Fastest`, `Fewest Changes`.

---

## 13. Revised Engineering Tickets

### Ticket TW-101: Repository & Docker Infrastructure Setup
- **Goal**: Initialize monorepo directory layout, Docker Compose setup (`postgres`, `redis`, `backend`, `frontend`), Next.js application, FastAPI server, and Pydantic configuration.
- **Dependencies**: None.
- **Files/Modules**: `docker-compose.yml`, `frontend/`, `backend/`, `backend/app/core/config.py`.
- **Acceptance Criteria**: Running `docker compose up` spins up healthy DB, Redis, Backend (FastAPI `/api/v1/health` and `/api/v1/health/ready` return 200 OK), and Frontend. Container networking uses service names `postgres` and `redis`.
- **Tests Required**: Docker container health check test, `/health` and `/health/ready` endpoint unit test.
- **Risks**: Local port conflicts.

### Ticket TW-102: Data/Domain Layer Separation & Database Migrations
- **Goal**: Implement pure domain Pydantic models in `app/domain/models/` and SQLAlchemy ORM models/Alembic migrations in `app/infrastructure/database/`.
- **Dependencies**: TW-101.
- **Files/Modules**: `backend/app/domain/models/`, `backend/app/infrastructure/database/models/`, `backend/alembic/`.
- **Acceptance Criteria**: Domain models have zero database dependencies. Alembic migrations apply cleanly enabling PostGIS and `uuid-ossp` extensions; indexes created on station geography and schedule lookup.
- **Tests Required**: Migration upgrade/downgrade integration test, domain model instantiation unit test.
- **Risks**: None.

### Ticket TW-103: Static Data Import Pipeline & Structural Data Validation
- **Goal**: Build import CLI script for static station and timetable datasets with rigorous data quality validation.
- **Why it exists**: Populates static graph with validated station coordinates and train schedules.
- **Dependencies**: TW-102.
- **Files/Modules**: `data/scripts/import_railway_data.py`, `backend/app/infrastructure/database/repositories/`.
- **Acceptance Criteria**: Data import script validates source records, ensures zero duplicate stations, verifies valid coordinate bounds, enforces monotonic stop sequences on train schedules, and outputs a clean JSON validation report.
- **Tests Required**: Data import validation test script.
- **Risks**: Inconsistent stop sequence indexing in raw sources (handled by validation script).

### Ticket TW-104: Railway Graph Representation & Candidate Corridor Generator
- **Goal**: Build pure domain graph builder and candidate path generation algorithm for direct trains and 1-2 stop transfer corridors.
- **Dependencies**: TW-103.
- **Files/Modules**: `backend/app/domain/routing/graph.py`, `backend/app/domain/routing/candidate_generator.py`.
- **Acceptance Criteria**: Generates candidate corridors from static graph without external API calls.
- **Tests Required**: Graph traversal unit tests for direct and transfer path discovery.
- **Risks**: Combinatorial explosion (mitigated by transfer cap $k \le 2$ and filtering via junction hubs).

### Ticket TW-105: Temporal Connection Validation Engine
- **Goal**: Implement temporal validation algorithm verifying connection layover windows ($45\text{m} \le \Delta t \le 240\text{m}$) and day offset rollovers.
- **Dependencies**: TW-104.
- **Files/Modules**: `backend/app/domain/routing/temporal_validator.py`.
- **Acceptance Criteria**: Validates transfer leg departure against previous leg arrival time and day offsets; rejects layovers $<45\text{m}$ or $>240\text{m}$.
- **Tests Required**: Unit tests for min/max layover boundaries and overnight transfer rollovers.
- **Risks**: Incorrect day offset calculation.

### Ticket TW-106: Provider Abstraction Layer & Structured Availability Models
- **Goal**: Define Abstract Base Classes for providers and implement mock providers returning typed `AvailabilityResult` objects.
- **Dependencies**: TW-102.
- **Files/Modules**: `backend/app/infrastructure/providers/base.py`, `backend/app/infrastructure/providers/mock/`.
- **Acceptance Criteria**: Mock availability provider returns structured `AvailabilityResult` containing controlled status enum (`AVAILABLE`, `RAC`, `WAITLIST`, etc.), fare, and timestamps.
- **Tests Required**: Mock provider unit tests.
- **Risks**: None.

### Ticket TW-107: Direct-First Search Controller & Multi-Factor Route Ranking
- **Goal**: Build direct-first search service and FastAPI `/api/v1/search/routes` endpoint.
- **Dependencies**: TW-104, TW-105, TW-106.
- **Files/Modules**: `backend/app/services/search_service.py`, `backend/app/domain/ranking/`, `backend/app/api/v1/search.py`.
- **Acceptance Criteria**: Executes direct train availability check first; returns routes ranked by duration, fare, and transfers. Does NOT execute Bachelor Special logic.
- **Tests Required**: Search controller integration test, ranking strategy unit tests.
- **Risks**: Latency on multi-leg live checks (mitigated by direct-first strategy and Redis caching).

### Ticket TW-108: Multi-Factor Nearby Station Discovery Engine
- **Goal**: Implement PostGIS radius queries (`ST_DWithin`) and multi-factor ranking (distance + travel time + fare + availability) for nearby station alternatives.
- **Dependencies**: TW-102, TW-107.
- **Files/Modules**: `backend/app/services/nearby_service.py`, `backend/app/domain/ranking/nearby_scorer.py`.
- **Acceptance Criteria**: Discovers nearby origin/destination stations within radius and scores alternatives using multi-factor utility function.
- **Tests Required**: Spatial query integration test, multi-factor scoring unit test.
- **Risks**: Coordinate order in PostGIS queries.

### Ticket TW-109: Bachelor Special Interval Stitching Engine
- **Goal**: Implement interval coverage algorithm for post-chart vacancy segments adhering to strict gapless continuity rules. Expose via `POST /api/v1/bachelor/search`.
- **Dependencies**: TW-102, TW-106.
- **Files/Modules**: `backend/app/domain/bachelor/stitcher.py`, `backend/app/api/v1/bachelor.py`.
- **Acceptance Criteria**: Implements gapless interval coverage algorithm and passes all 8 required test scenarios (1 segment, 2 segments, 3 segments, gap, overlap, multiple chains, no coverage, expired).
- **Tests Required**: 8 explicit unit test cases for interval coverage.
- **Risks**: None.

### Ticket TW-110: Station Autocomplete API & Domain Repositories
- **Goal**: Implement `GET /api/v1/stations/search` endpoint for frontend station selection.
- **Dependencies**: TW-102, TW-103.
- **Files/Modules**: `backend/app/api/v1/stations.py`, `backend/app/infrastructure/database/repositories/station_repository.py`.
- **Acceptance Criteria**: Returns matching stations by code or name within $<50\text{ms}$.
- **Tests Required**: Autocomplete integration test.
- **Risks**: None.

### Ticket TW-111: Frontend Design Tokens & UI Component Foundation
- **Goal**: Build Next.js visual foundation using finalized design tokens (`#F4EFE4`, `#191612`, `#B9532D`, `#67664A`), editorial grotesk headings, and clean UI sans-serif.
- **Dependencies**: TW-101.
- **Files/Modules**: `frontend/src/lib/theme.ts`, `frontend/tailwind.config.js`, `frontend/src/components/ui/`.
- **Acceptance Criteria**: Visual styling strictly matches finalized TripWiser color palette and typography rules.
- **Tests Required**: UI component rendering tests.
- **Risks**: None.

### Ticket TW-112: Frontend Search, Results, & Bachelor Special Experience
- **Goal**: Build Search Form, Direct-First Route Result List with sorting (`Recommended`, `Cheapest`, `Fastest`, `Fewest Changes`), Journey Details modal, and Bachelor Special visual timeline.
- **Dependencies**: TW-107, TW-109, TW-110, TW-111.
- **Files/Modules**: `frontend/src/app/search/`, `frontend/src/app/bachelor/`, `frontend/src/components/bachelor/BerthTimeline.tsx`.
- **Acceptance Criteria**: Minimal-on-first-look cards, responsive design, explicit booking disclaimers (*"Vacant berth segments discovered. Booking/allotment is handled through the applicable railway process."*), and zero technical/AI jargon in UI.
- **Tests Required**: Playwright E2E search and filter test.
- **Risks**: None.

---

## Summary of Architectural Changes Made

| # | Topic | Description of Correction |
| :--- | :--- | :--- |
| **1** | **Domain / Persistence** | Moved SQLAlchemy ORM models to `infrastructure/database/models/`. Kept `domain/models/` 100% pure Pydantic models with zero DB coupling. |
| **2** | **Design Tokens** | Set tokens to Cream (`#F4EFE4`), Espresso (`#191612`), Terracotta (`#B9532D`), Olive (`#67664A`). Heading font set to bold editorial grotesk/display; UI body set to modern sans. Removed lime green & Playfair Display. |
| **3** | **Search / Bachelor Separation**| Removed automatic chart vacancy search from `POST /api/v1/search/routes`. Decoupled Bachelor Special to `POST /api/v1/bachelor/search` (runs on demand only). |
| **4** | **Structured Availability** | Replaced `"AVAILABLE-0024"` string with `AvailabilityResult` Pydantic model featuring controlled status enum (`AVAILABLE`, `RAC`, `WAITLIST`, etc.), counts, fare, and timestamp. |
| **5** | **Chart Vacancy Provenance** | Added `source`, `observed_at`, `expires_at`, `chart_phase`, and `status` to `chart_vacancies` table while keeping domain `BerthSegment` clean. |
| **6** | **Bachelor Continuity Rules** | Formally defined gapless continuity rule ($S_{\text{to}_i} = S_{\text{from}_{i+1}}$). Gap scenarios return no coverage. Detailed 8 unit test cases. |
| **7** | **Direct-First Search** | Implemented 3-phase search strategy: Direct check first $\to$ Multi-leg candidate corridors $\to$ Nearby station expansion. Avoids unnecessary live API calls. |
| **8** | **Multi-Factor Nearby Ranking**| Nearby station scoring factors in origin/destination transit distance, journey time, transfers, fare, and availability. |
| **9** | **Docker Container Networking**| Internal service URLs use Docker container names (`postgres`, `redis`) via Pydantic settings. |
| **10** | **Data Import Criteria** | Replaced static station count threshold with structural integrity checks (no duplicates, monotonic stop sequences, valid coords, JSON validation report). |
| **11** | **Endpoints & Health** | Defined `/api/v1/health`, `/api/v1/health/ready`, and `/api/v1/stations/search` autocomplete endpoints. Enabled `uuid-ossp` extension for Postgres UUIDs. |
| **12** | **UI Terminology & Copy** | Explicit booking copy added (*"Vacant berth segments discovered. Booking/allotment is handled through the applicable railway process."*). Enforced strict exclusion of internal jargon. |
