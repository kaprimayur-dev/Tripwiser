# Implementation Plan - TripWiser Engineering Kickoff & V1 Architecture

## Overview & Executive Summary

**TripWiser** is a travel intelligence and route discovery product designed to solve a core problem in Indian Railway travel: **A direct train being unavailable does NOT mean the journey is impossible.**

Capacity frequently exists across alternate train combinations, intermediate transfer stations, nearby/upstream boarding stations, and post-chart vacant berth segments. TripWiser discovers these multi-leg, alternate, and vacant-berth options and presents them to the traveler in a clear, minimal, and relatable visual format.

This document establishes the initial technical architecture, domain models, data providers, routing algorithms, database schemas, API contracts, state management, and ticket breakdown for V1 engineering.

> [!IMPORTANT]
> **Booking is strictly OUT OF SCOPE for V1.** TripWiser is a decision-support & itinerary discovery tool. It does not process payments, handle IRCTC user authentication, or book tickets.

---

## 1. Current Repository Assessment

- **Location**: `c:\projects\tripwiser`
- **State**: Empty root directory (Fresh repository initialization required).
- **Tooling to establish**:
  - Frontend: React / Next.js (App Router, TypeScript, Tailwind CSS, Lucide Icons, TanStack Query).
  - Backend: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 / Alembic, Async HTTP (`httpx`).
  - Database & Cache: PostgreSQL with PostGIS extension, Redis.
  - Development Environment: Docker Compose (`docker-compose.yml`) containing PostgreSQL/PostGIS, Redis, FastAPI dev server, and Next.js frontend server.
  - Testing: `pytest` (Backend unit/integration tests), `vitest` or `playwright` (Frontend unit & E2E tests).

---

## 2. Proposed Final Project Structure

A clean, monorepo-style structure separating frontend, backend, static scripts/data, and docker configuration:

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
│       └── lib/                # Design tokens, formatters, utilities
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
│   │   ├── domain/             # Pure Domain Models & Business Logic (No HTTP/DB coupling)
│   │   │   ├── models/         # Station, Train, Route, Itinerary, Vacancy, BerthSegment
│   │   │   ├── routing/        # Graph builder, candidate generator, temporal validator
│   │   │   ├── bachelor/       # Bachelor Special berth stitching engine
│   │   │   └── ranking/        # Multi-factor ranking algorithms
│   │   ├── providers/          # Provider Abstraction & Adapters
│   │   │   ├── base.py         # Interfaces (TrainDataProvider, AvailabilityProvider, etc.)
│   │   │   ├── mock/           # Mock providers for offline dev & test suites
│   │   │   ├── static_graph/   # DataMeet/Data.gov.in static graph loader
│   │   │   └── live/           # External live availability adapters
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
    └── scripts/                # Data import & graph pre-computation tools
```

---

## 3. Architecture Diagram

```mermaid
graph TD
    User([Traveler / Web Browser]) -->|HTTP / JSON| Frontend[Next.js Frontend\nTypeScript + Tailwind]
    
    subgraph Frontend Layer
        Frontend --> ReactQuery[TanStack Query State Management]
        ReactQuery --> UIComponents[UI Components\nSearch Form / Route Cards / Journey Details]
    end

    Frontend -->|REST API| APIGateway[FastAPI API Layer]

    subgraph Backend Application
        APIGateway --> Controllers[API Routers & DTO Validation]
        Controllers --> ServiceLayer[Application Service Layer]
        
        ServiceLayer --> RoutingEngine[Candidate Route Generator]
        ServiceLayer --> TemporalEngine[Temporal Validator]
        ServiceLayer --> BachelorEngine[Bachelor Special Stitching Engine]
        ServiceLayer --> RankingEngine[Itinerary Ranking Engine]
        ServiceLayer --> NearbyEngine[Geospatial Nearby Station Search]

        RoutingEngine --> DomainGraph[Static Railway Graph]
        BachelorEngine --> DomainVacancy[Berth Segment Coverage Engine]
    end

    subgraph Provider Layer (Interfaces & Adapters)
        ServiceLayer --> ProviderAbstraction[Internal Provider Adapters]
        ProviderAbstraction --> MockProvider[Dev/Mock Provider]
        ProviderAbstraction --> LiveAPIAdapter[Live Railway API Adapter]
        ProviderAbstraction --> StaticGraphAdapter[Static Timetable Provider]
    end

    subgraph Data & Storage Layer
        DomainGraph --> Postgres[(PostgreSQL + PostGIS\nStatic Stations/Trains/Schedules)]
        ServiceLayer --> RedisCache[(Redis Cache\nRoutes, Availability, Vacancy)]
    end
```

---

## 4. Domain Entities

The core domain relies on explicit, immutable Python models decoupled from database ORM and API schemas.

### 4.1 Station
```python
class Station:
    code: str                  # e.g., "GWL", "BPL", "JHS"
    name: str                  # e.g., "Gwalior Junction"
    latitude: float
    longitude: float
    city: str
    zone: str                  # e.g., "NCR", "WCR"
```

### 4.2 Train & Schedule
```python
class TrainScheduleEntry:
    station_code: str
    arrival_time: Optional[time]   # None for origin
    departure_time: Optional[time] # None for destination
    day_offset: int                # 0 for Day 1, 1 for Day 2
    distance_km: float

class Train:
    number: str                # e.g., "12616"
    name: str                  # e.g., "Grand Trunk Express"
    origin_code: str
    destination_code: str
    runs_on_days: list[int]    # [0, 1, 2, 3, 4, 5, 6] (Mon=0)
    schedule: list[TrainScheduleEntry]
```

### 4.3 Leg & Connection (Candidate Path)
```python
class JourneyLeg:
    train_number: str
    train_name: str
    origin_code: str
    destination_code: str
    departure_day: date
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    travel_class: str            # "SL", "3A", "2A", "1A"
    distance_km: float

class CandidateRoute:
    legs: list[JourneyLeg]
    total_duration_minutes: int
    total_distance_km: float
    transfer_count: int
    transfer_durations_minutes: list[int]
```

### 4.4 Bachelor Special (Berth Vacancy Segment)
```python
class BerthSegment:
    segment_id: str
    train_number: str
    coach: str                   # e.g., "B2"
    berth_number: int            # e.g., 43
    berth_type: str              # e.g., "SL", "SU", "LB", "MB", "UB"
    from_station_code: str
    to_station_code: str
    from_sequence: int
    to_sequence: int

class BachelorSpecialItinerary:
    train_number: str
    train_name: str
    from_station_code: str
    to_station_code: str
    date: date
    travel_class: str
    segments: list[BerthSegment] # Ordered list of segments covering origin -> destination
    total_segment_count: int
```

---

## 5. Database Schema Proposal (PostgreSQL + PostGIS)

```sql
-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

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
    runs_on_days INT[] NOT NULL, -- Array of days e.g. {0,1,2,3,4,5,6}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Schedules Table
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

-- Cached Chart Vacancy Segments (For Bachelor Special)
CREATE TABLE chart_vacancies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    train_number VARCHAR(10) REFERENCES trains(number),
    chart_date DATE NOT NULL,
    coach VARCHAR(10) NOT NULL,
    berth_number INT NOT NULL,
    travel_class VARCHAR(10) NOT NULL,
    from_station_code VARCHAR(10) REFERENCES stations(code),
    to_station_code VARCHAR(10) REFERENCES stations(code),
    from_sequence INT NOT NULL,
    to_sequence INT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_vacancies_search ON chart_vacancies (train_number, chart_date, from_sequence, to_sequence);
```

---

## 6. API Boundary Proposal

### `POST /api/v1/search/routes`
**Request Body**:
```json
{
  "origin_code": "GWL",
  "destination_code": "BPL",
  "travel_date": "2026-10-15",
  "preferred_class": "3A",
  "max_transfers": 2,
  "min_transfer_minutes": 45,
  "max_layover_minutes": 240,
  "include_nearby": true,
  "nearby_radius_km": 50
}
```

**Response Body**:
```json
{
  "search_id": "req_8923f0a1",
  "query": {
    "origin": { "code": "GWL", "name": "Gwalior" },
    "destination": { "code": "BPL", "name": "Bhopal Junction" },
    "travel_date": "2026-10-15"
  },
  "routes": [
    {
      "route_id": "rt_101",
      "type": "DIRECT",
      "total_duration": "4h 30m",
      "total_duration_minutes": 270,
      "total_fare": 750,
      "transfer_count": 0,
      "availability_status": "AVAILABLE",
      "legs": [
        {
          "train_number": "12616",
          "train_name": "Grand Trunk Express",
          "origin": { "code": "GWL", "name": "Gwalior" },
          "destination": { "code": "BPL", "name": "Bhopal" },
          "departure_time": "2026-10-15T06:15:00+05:30",
          "arrival_time": "2026-10-15T10:45:00+05:30",
          "travel_class": "3A",
          "availability": "AVAILABLE-0024",
          "fare": 750
        }
      ]
    },
    {
      "route_id": "rt_102",
      "type": "TRANSFER",
      "total_duration": "5h 50m",
      "total_duration_minutes": 350,
      "total_fare": 920,
      "transfer_count": 1,
      "transfer_details": [{ "station": "Jhansi Junction", "layover_minutes": 65 }],
      "availability_status": "AVAILABLE",
      "legs": [
        {
          "train_number": "12002",
          "train_name": "Shatabdi Express",
          "origin": { "code": "GWL", "name": "Gwalior" },
          "destination": { "code": "JHS", "name": "Jhansi" },
          "departure_time": "2026-10-15T07:00:00+05:30",
          "arrival_time": "2026-10-15T08:00:00+05:30",
          "travel_class": "3A",
          "availability": "AVAILABLE-0012",
          "fare": 350
        },
        {
          "train_number": "12628",
          "train_name": "Karnataka Express",
          "origin": { "code": "JHS", "name": "Jhansi" },
          "destination": { "code": "BPL", "name": "Bhopal" },
          "departure_time": "2026-10-15T09:05:00+05:30",
          "arrival_time": "2026-10-15T12:50:00+05:30",
          "travel_class": "3A",
          "availability": "AVAILABLE-0008",
          "fare": 570
        }
      ]
    }
  ],
  "bachelor_special": {
    "available": true,
    "options_count": 1,
    "summary": "1 Multi-berth vacant option found on 12616 GT Express"
  }
}
```

### `GET /api/v1/bachelor/search?train_number=12616&origin=GWL&destination=BPL&date=2026-10-15`
**Response Body**:
```json
{
  "train_number": "12616",
  "train_name": "Grand Trunk Express",
  "journey": { "origin": "GWL", "destination": "BPL", "date": "2026-10-15" },
  "is_complete_coverage": true,
  "segment_count": 3,
  "segments": [
    {
      "leg_index": 1,
      "from_station": { "code": "GWL", "name": "Gwalior" },
      "to_station": { "code": "JHS", "name": "Jhansi Junction" },
      "coach": "B2",
      "berth_number": 43,
      "berth_type": "UB"
    },
    {
      "leg_index": 2,
      "from_station": { "code": "JHS", "name": "Jhansi Junction" },
      "to_station": { "code": "BHA", "name": "Vidisha" },
      "coach": "B3",
      "berth_number": 21,
      "berth_type": "MB"
    },
    {
      "leg_index": 3,
      "from_station": { "code": "BHA", "name": "Vidisha" },
      "to_station": { "code": "BPL", "name": "Bhopal Junction" },
      "coach": "B1",
      "berth_number": 18,
      "berth_type": "LB"
    }
  ]
}
```

---

## 7. Data Provider Abstraction Design

To prevent lock-in to external railway APIs, all data access passes through clean abstract interfaces defined in `backend/app/providers/base.py`:

```python
from abc import ABC, abstractmethod
from typing import Optional
from datetime import date
from app.domain.models import Station, Train, AvailabilityStatus, BerthSegment

class StationProvider(ABC):
    @abstractmethod
    async def get_station_by_code(self, code: str) -> Optional[Station]: ...
    @abstractmethod
    async def search_stations(self, query: str) -> list[Station]: ...
    @abstractmethod
    async def get_nearby_stations(self, lat: float, lon: float, radius_km: float) -> list[Station]: ...

class TrainDataProvider(ABC):
    @abstractmethod
    async def get_train(self, train_number: str) -> Optional[Train]: ...
    @abstractmethod
    async def find_direct_trains(self, origin: str, destination: str, travel_date: date) -> list[Train]: ...

class AvailabilityProvider(ABC):
    @abstractmethod
    async def get_availability(
        self, train_number: str, origin: str, destination: str, travel_date: date, travel_class: str
    ) -> AvailabilityStatus: ...

class ChartVacancyProvider(ABC):
    @abstractmethod
    async def get_chart_vacancies(
        self, train_number: str, travel_date: date
    ) -> list[BerthSegment]: ...
```

---

## 8. Routing Engine Design

The routing engine operates in 5 clear stages:

1. **Static Graph Traversal**: Finds candidate station sequences $S = [A, M_1, \dots, B]$ using Dijkstra / k-shortest paths on static station connections (limiting max transfers $k \le 2$).
2. **Train Matching**: Identifies physical trains servicing each leg $(S_i \to S_{i+1})$.
3. **Temporal Validation**: Validates connection timing:
   $$\text{Arrival}(Leg_i) + \text{MinTransfer} \le \text{Departure}(Leg_{i+1}) \le \text{Arrival}(Leg_i) + \text{MaxLayover}$$
4. **Live Availability Check**: Calls `AvailabilityProvider` **only** for candidate routes passing temporal validation.
5. **Itinerary Assembly & Ranking**: Converts valid candidates into final `RouteResult` objects sorted by selected ranking policy.

---

## 9. Availability Flow

```mermaid
sequenceDiagram
    participant Client as Frontend
    participant API as FastAPI Search API
    participant Routing as Graph Routing Engine
    participant Cache as Redis Cache
    participant Provider as Availability Provider Adapter

    Client->>API: POST /api/v1/search/routes (GWL -> BPL)
    API->>Routing: Generate Candidate Paths (GWL -> BPL)
    Routing-->>API: Return Candidate Paths (e.g. GWL->BPL Direct, GWL->JHS->BPL 1-Stop)
    
    loop For Each Viable Candidate Leg
        API->>Cache: Check Cached Availability (train, date, class, src, dst)
        alt Cache Hit
            Cache-->>API: Return Availability
        else Cache Miss
            API->>Provider: Fetch Live Availability
            Provider-->>API: Availability Result (e.g. AVAILABLE-0012)
            API->>Cache: Save to Redis (TTL 15 mins)
        end
    end

    API->>API: Assemble & Rank Itineraries
    API-->>Client: Return Route List + Bachelor Special Summary
```

---

## 10. Nearby-Station Architecture

When direct routes from $A \to B$ are tight or unavailable:
1. Query PostGIS for nearby origin stations within $R$ km of $A$: $\{A_1, A_2, \dots, A_n\} = \text{ST\_DWithin}(A, R)$.
2. Query PostGIS for nearby destination stations within $R$ km of $B$: $\{B_1, B_2, \dots, B_m\} = \text{ST\_DWithin}(B, R)$.
3. Execute candidate route search for tuples $(A_i, B_j)$.
4. Annotate resulting routes with visual badges: `Nearby Origin: Morena (35 km)` or `Nearby Boarding`.

---

## 11. Bachelor Special Architecture

### Problem Definition
Given a train journey with station sequence $S_1, S_2, \dots, S_N$, chart vacancy data provides available berth intervals $[S_i, S_j]$ for specific coaches/berths.

### Stitching Algorithm (Interval / Segment Coverage)
1. Represent the train route sequence as indices $1 \dots N$.
2. Filter chart vacancies for the requested date and train into valid interval edges: $(u, v, \text{coach}, \text{berth})$.
3. Find exact coverage paths from index $1$ (Origin) to index $N$ (Destination) using Dynamic Programming / Breadth-First Search over interval coverage graph.
4. Minimize coach switches (e.g. prefer switching berths within the same coach over switching coaches).
5. If continuous coverage exists, assemble a `BachelorSpecialItinerary`. If gaps exist, discard or report partial coverage.

> [!NOTE]
> In V1 development, if live post-chart feeds are unavailable, `MockChartVacancyProvider` will generate deterministic, realistic vacancy interval scenarios for testing.

---

## 12. Frontend Architecture & Design Language

### Visual Language & Design Tokens
- **Background**: Warm Cream (`#FDFBF7` / `bg-stone-50`)
- **Primary Text & Headers**: Deep Espresso (`#1C1917` / `text-stone-900`)
- **Primary Accent**: Burnt Terracotta (`#C2410C` / `bg-orange-700`)
- **Secondary Accent**: Muted Olive (`#65A30D` / `bg-lime-700` or `#4D7C0F`)
- **Cards & Surfaces**: Warm Pure White (`#FFFFFF`), Soft Borders (`border-stone-200`), Soft Shadows (`shadow-sm`)
- **Typography**: Editorial serif for headers (e.g., *Playfair Display* or *Georgia*), clean modern sans-serif for UI numbers/times (*Inter* or system sans).

### UX Principle: Minimal on First Look, Detailed on Demand
- **Route Cards**: Minimal view displaying Origin, Destination, Departure, Arrival, Duration, Transfer Count, Class, Availability, Fare, and CTA.
- **Journey Modal/Drawer**: In-depth breakdown showing exact train schedules, layover times at transfer stations, berth numbers for Bachelor Special, and platform info.

---

## 13. State & Data-Fetching Strategy

- **TanStack Query (React Query v5)** handles server state, caching, background refetching, and query deduplication on the frontend.
- **Client Search State**: React URL Search Params (`useSearchParams`) for shareable search links (`/search?from=GWL&to=BPL&date=2026-10-15`).
- **Backend Redis Caching**:
  - Station lists / static graph: 24-hour TTL
  - Train schedules: 12-hour TTL
  - Seat availability checks: 15-minute TTL
  - Chart vacancy data: 5-minute TTL

---

## 14. Configuration & Environment Strategy

Pydantic `BaseSettings` manages environment variable loading in Python:

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "TripWiser API"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://tripwiser:tripwiser@localhost:5432/tripwiser_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Provider Selection
    AVAILABILITY_PROVIDER: str = "mock" # "mock" | "live"
    CHART_VACANCY_PROVIDER: str = "mock"
    
    # Search Constraints
    MIN_TRANSFER_MINUTES: int = 45
    MAX_LAYOVER_MINUTES: int = 240
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 15. Testing Strategy

### Unit Testing (`pytest`)
- Routing candidate path generation logic.
- Temporal validation constraints (rejecting transfers under 45 mins or over 240 mins).
- Bachelor Special interval coverage / stitching algorithm (covering all 8 required test cases).
- PostGIS station distance & radius calculations.

### Integration Testing
- FastAPI route handlers with `httpx.AsyncClient` against test database.
- Data import pipeline (loading sample CSV/JSON timetable datasets into PostgreSQL).
- Redis caching layer fallback behavior.

### End-to-End Testing (`playwright`)
- Full user flow: Home Page Search Form $\to$ Results Page $\to$ Filter by Direct / 1-Stop $\to$ View Journey Details modal $\to$ Bachelor Special view.

---

## 16. Development Phases & Roadmap

```mermaid
gantt
    title TripWiser V1 Development Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 0: Setup
    Repo & Docker Setup           :p0, 2026-09-24, 2d
    section Phase 1: Data & Models
    Database & Static Graph Load   :p1, 2026-09-26, 3d
    section Phase 2: Engine Core
    Graph Router & Candidate Gen   :p2, 2026-09-29, 3d
    Temporal Validator             :p2b, 2026-10-02, 2d
    section Phase 3: Providers & Search
    Provider Abstraction & Mock    :p3, 2026-10-04, 3d
    Search API & Itinerary Assembly:p3b, 2026-10-07, 3d
    section Phase 4: Special Features
    Nearby Station Engine          :p4, 2026-10-10, 3d
    Bachelor Special Stitcher      :p4b, 2026-10-13, 4d
    section Phase 5: Frontend
    UI Component Library & Setup   :p5, 2026-10-17, 3d
    Search & Results Experience    :p5b, 2026-10-20, 4d
    Bachelor Special Visuals       :p5c, 2026-10-24, 3d
    section Phase 6: E2E & Polish
    Testing, Verification & Launch :p6, 2026-10-27, 4d
```

---

## 17. Engineering Tickets

Below are the 12 primary engineering tickets covering V1 execution:

### Ticket TW-101: Repository & Development Infrastructure Setup
- **Goal**: Initialize monorepo directory layout, Docker Compose setup, Next.js application, FastAPI server, and CI linting configs.
- **Why it exists**: Establishes local dev environment for frontend, backend, PostgreSQL/PostGIS, and Redis.
- **Dependencies**: None.
- **Files/Modules**: `docker-compose.yml`, `frontend/`, `backend/`, `.env.example`.
- **Acceptance Criteria**: Running `docker compose up` spins up healthy DB, Redis, Backend (FastAPI `/health` returns 200 OK), and Frontend (Next.js renders home page).
- **Tests Required**: Docker container health checks, FastAPI health endpoint unit test.
- **Risks**: Port collisions on developer machine.

### Ticket TW-102: Static Railway Domain Models & Database Migration
- **Goal**: Implement SQLAlchemy ORM models, Pydantic schemas, and Alembic database migration scripts for Stations, Trains, Schedules, and Chart Vacancies.
- **Why it exists**: Provides persistence layer with PostGIS geospatial support.
- **Dependencies**: TW-101.
- **Files/Modules**: `backend/app/core/db.py`, `backend/app/domain/models/`, `backend/alembic/`.
- **Acceptance Criteria**: Migration applies cleanly to PostGIS database; indexes created on station code, location GIST, and schedule sequences.
- **Tests Required**: DB migration upgrade/downgrade test, ORM CRUD unit tests.
- **Risks**: PostGIS extension availability in dev environment.

### Ticket TW-103: Static Data Import Pipeline (DataMeet / Timetable Dataset)
- **Goal**: Build a CLI script to import raw station and train schedule JSON/CSV data into PostgreSQL.
- **Why it exists**: Populates static graph required for candidate route generation.
- **Dependencies**: TW-102.
- **Files/Modules**: `data/scripts/import_railway_data.py`, `backend/app/providers/static_graph/`.
- **Acceptance Criteria**: Script successfully parses raw station/train datasets and populates database with >3,000 stations and major train schedules.
- **Tests Required**: Import validation test verifying expected station counts and schedule order.
- **Risks**: Data corruption or inconsistent station code format in raw datasets.

### Ticket TW-104: Railway Graph Representation & Candidate Path Generator
- **Goal**: Build pure domain graph builder and candidate path generation algorithm (Direct trains and 1-2 stop transfer routes).
- **Why it exists**: Core routing component to discover alternate journey paths.
- **Dependencies**: TW-103.
- **Files/Modules**: `backend/app/domain/routing/graph.py`, `backend/app/domain/routing/candidate_generator.py`.
- **Acceptance Criteria**: Given GWL and BPL, algorithm returns valid direct paths and candidate 1-stop transfer paths (e.g. GWL $\to$ JHS $\to$ BPL).
- **Tests Required**: Unit tests for direct path discovery, transfer path discovery, and cycle prevention.
- **Risks**: Combinatorial explosion on dense railway networks (mitigated by limiting transfers $k \le 2$ and filtering via major junctions).

### Ticket TW-105: Temporal Connection Validation Engine
- **Goal**: Build pure domain function to validate layover windows and day offsets for multi-leg journeys.
- **Why it exists**: Ensures proposed transfer routes are physically viable for travelers.
- **Dependencies**: TW-104.
- **Files/Modules**: `backend/app/domain/routing/temporal_validator.py`.
- **Acceptance Criteria**: Validates transfers using configurable min layover (default 45 mins) and max layover (default 240 mins); accounts for midnight day rollovers.
- **Tests Required**: Unit tests for edge cases: 44-min transfer (rejected), 45-min transfer (accepted), overnight transfer (day offset checked).
- **Risks**: Misinterpreting day offset in multi-day train runs.

### Ticket TW-106: Provider Abstraction Layer & Mock Providers
- **Goal**: Define Abstract Base Classes for data providers and implement deterministic mock providers for Availability and Vacancies.
- **Why it exists**: Decouples application domain from external API vendors and enables offline development.
- **Dependencies**: TW-102.
- **Files/Modules**: `backend/app/providers/base.py`, `backend/app/providers/mock/`.
- **Acceptance Criteria**: Mock availability provider returns structured `AVAILABLE` / `WAITLIST` statuses without external network calls.
- **Tests Required**: Mock provider unit tests.
- **Risks**: Mock behavior straying from real-world API schema.

### Ticket TW-107: Route Ranking Engine & Search API Controller
- **Goal**: Implement multi-criteria ranking engine (duration, fare, transfers) and assemble FastAPI `/api/v1/search/routes` endpoint.
- **Why it exists**: Exposes search capabilities to frontend with clean, normalized JSON responses.
- **Dependencies**: TW-104, TW-105, TW-106.
- **Files/Modules**: `backend/app/domain/ranking/`, `backend/app/services/search_service.py`, `backend/app/api/v1/search.py`.
- **Acceptance Criteria**: Search API accepts POST query and returns sorted route candidates matching API contract.
- **Tests Required**: Endpoint integration tests, ranking order unit tests.
- **Risks**: Latency spike when checking multiple candidate legs (mitigated by parallel async calls & Redis caching).

### Ticket TW-108: Nearby Station Geospatial Discovery Engine
- **Goal**: Implement PostGIS radius queries to find alternate boarding/alighting stations near origin and destination.
- **Why it exists**: Discovers capacity from nearby stations when primary station is sold out.
- **Dependencies**: TW-102, TW-107.
- **Files/Modules**: `backend/app/services/nearby_service.py`, `backend/app/domain/routing/nearby_expander.py`.
- **Acceptance Criteria**: Given origin $A$, returns stations within $R$ km (e.g. Morena for Gwalior) and generates alternate routes.
- **Tests Required**: Spatial radius unit test, integration test with PostGIS `ST_DWithin`.
- **Risks**: PostGIS coordinate order (lon/lat vs lat/lon).

### Ticket TW-109: Bachelor Special Berth Stitching Engine
- **Goal**: Implement interval coverage algorithm to assemble continuous journey itineraries from post-chart vacancy segments.
- **Why it exists**: Core backend engine for the "Bachelor Special" feature.
- **Dependencies**: TW-102, TW-106.
- **Files/Modules**: `backend/app/domain/bachelor/stitcher.py`, `backend/app/api/v1/bachelor.py`.
- **Acceptance Criteria**: Correctly solves all 8 required vacancy test scenarios (1 segment full coverage, 2 segments, 3 segments, gap, overlap, multiple choices, no coverage, expired).
- **Tests Required**: 8 explicit domain unit test cases.
- **Risks**: Performance with dense vacancy segment lists (mitigated by sorting by sequence index and greedy/DP interval coverage).

### Ticket TW-110: Frontend Design System & UI Component Foundation
- **Goal**: Build Next.js visual foundation using established design tokens (warm cream, deep espresso, terracotta, olive), typography, and base card components.
- **Why it exists**: Guarantees established visual style without generic UI components.
- **Dependencies**: TW-101.
- **Files/Modules**: `frontend/src/lib/theme.ts`, `frontend/src/components/ui/`, `frontend/tailwind.config.js`.
- **Acceptance Criteria**: Clean UI library conforming to editorial aesthetic, responsive design, and proper typography.
- **Tests Required**: Frontend component snapshot / rendering unit tests.
- **Risks**: Visual inconsistency with design references.

### Ticket TW-111: Frontend Route Search & Journey Details Experience
- **Goal**: Build Search Form, Route Card List with sorting (Recommended, Fastest, Fewest Changes), and Journey Details modal/drawer.
- **Why it exists**: Primary user-facing discovery interface.
- **Dependencies**: TW-107, TW-110.
- **Files/Modules**: `frontend/src/app/search/`, `frontend/src/components/search/`, `frontend/src/services/api.ts`.
- **Acceptance Criteria**: Users can search origin/destination/date, view route cards matching minimal-on-first-look principle, and expand journey details on demand.
- **Tests Required**: Playwright E2E search flow test.
- **Risks**: Overloading route cards with technical data (strictly avoided per prompt guidelines).

### Ticket TW-112: Bachelor Special Frontend Visual Experience
- **Goal**: Build Bachelor Special visual timeline component illustrating multi-berth seat handoffs across stations.
- **Why it exists**: Delivers the visual experience for post-chart vacant seat handoffs.
- **Dependencies**: TW-109, TW-110.
- **Files/Modules**: `frontend/src/components/bachelor/BerthTimeline.tsx`, `frontend/src/app/bachelor/`.
- **Acceptance Criteria**: Displays clear step-by-step visual node graph showing berth changes (e.g. Gwalior B2-43 $\to$ Jhansi B3-21 $\to$ Bhopal B1-18) without AI/system jargon.
- **Tests Required**: UI visual timeline component unit test.
- **Risks**: Confusing users about booking capability (clear disclaimers included).

---

## 18. Dependency & Risk Analysis

| Risk ID | Risk Description | Severity | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **R-01** | External live availability API instability or rate limits | High | High | Strict internal `AvailabilityProvider` interface with Redis caching (15-min TTL) and fallback mock/sample provider. |
| **R-02** | Combinatorial explosion during multi-leg route generation | Medium | Medium | Cap transfers to $k \le 2$; pre-filter transfer stations to major junctions; enforce max layover window (240 mins). |
| **R-03** | Inconsistent station codes or coordinates in raw static data | Medium | High | Data import sanitization script with validation rules and fallback coordinate lookup. |
| **R-04** | User confusion regarding Bachelor Special booking | High | High | Use clear UI copy: *"Vacant berth segments discovered — requires separate booking per segment on IRCTC"*. |
| **R-05** | Complex user-facing terminology leaking into UI | Low | High | Maintain strict dictionary check on frontend text (No "Berth Stitching Engine", "Dynamic Allocation", or "AI Radar"). |

---

## 19. Definition of Done (DoD)

### Phase 0 Definition of Done (Setup & Architecture Review)
1. Repository structure initialized with `frontend/`, `backend/`, and `data/` directories.
2. `docker-compose.yml` configured and tested with PostgreSQL (PostGIS) and Redis.
3. Architecture plan (`implementation_plan.md`) reviewed and approved by human reviewer.

### Phase 1 Definition of Done (Data Foundation & Domain Models)
1. Static station and train schedule database schema migrated via Alembic.
2. Railway static import script populates DB with test station network (including GWL, JHS, BHA, BPL, etc.).
3. Pure domain models (`Station`, `Train`, `CandidateRoute`, `BerthSegment`) implemented and covered by unit tests.
4. Abstract provider interfaces established in `app/providers/base.py`.

---

## User Review Required

> [!IMPORTANT]
> **Key Architecture Decisions for Approval:**
> 1. **Data Provider Abstraction**: Live APIs are hidden behind abstract `AvailabilityProvider` and `ChartVacancyProvider` interfaces, ensuring no direct coupling to single external vendors.
> 2. **Bachelor Special Naming & UX**: User-facing feature retains the exact name **Bachelor Special**; internal logic is modeled as segment/interval coverage without exposing internal engineering jargon to travelers.
> 3. **Search Constraints**: Configurable transfer limits set to minimum 45 minutes, maximum 240 minutes layover window, and maximum 2 transfers.
> 4. **V1 Scope Boundaries**: Payments, automated booking, IRCTC authentication, and ML predictions remain strictly out of scope for V1.

---

## Next Steps

Upon review and approval of this plan by the reviewer:
1. Initialize Phase 0 (Ticket TW-101) setup (Docker Compose, Next.js, FastAPI).
2. Execute Phase 1 (Tickets TW-102 & TW-103) for static railway database and domain models.
