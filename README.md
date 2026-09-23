# TripWiser — Travel Intelligence & Railway Discovery Platform

TripWiser helps travelers find practical railway journeys in India when a direct A→B train is unavailable.

## Project Structure

```
tripwiser/
├── docker-compose.yml          # Local container orchestration
├── README.md                   # Setup & development guide
├── frontend/                   # Next.js App Router (TypeScript, Tailwind CSS)
├── backend/                    # FastAPI Backend Server (Python 3.11)
└── data/                       # Railway static datasets & scripts
```

## Quickstart & Local Development

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### 2. Running via Docker Compose
To spin up all services (Postgres with PostGIS, Redis, FastAPI Backend, Next.js Frontend):

```bash
docker compose up --build
```

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Endpoint**: http://localhost:8000/api/v1/health
- **Readiness Endpoint**: http://localhost:8000/api/v1/health/ready

### 3. Backend Local Setup (Without Docker)
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 4. Running Backend Tests
```bash
cd backend
pytest tests/
```

### 5. Frontend Local Setup (Without Docker)
```bash
cd frontend
npm install
npm run dev
```
