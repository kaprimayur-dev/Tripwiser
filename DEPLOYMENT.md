# TripWiser Production Deployment Guide

## 1. Architecture Overview

TripWiser is an Indian Railway journey discovery platform consisting of:
- **Frontend**: Next.js 14 App Router, deployed globally on **Vercel** with edge caching and server-side `/api/v1` proxy rewrites.
- **Backend API**: FastAPI running with Uvicorn in a Python 3.11 Docker container on **Railway**, exposing REST endpoints, route discovery algorithms, timetable search, and train comparison services.
- **Database**: PostgreSQL 15 with **PostGIS 3.3** extension (`postgis/postgis:15-3.3-alpine`) running on Railway with a persistent disk volume.
- **Cache/Broker**: Redis 7 Alpine (`redis:7-alpine`) on Railway's internal network for auxiliary caching and readiness verification.

```
                           [ Passenger Browser ]
                                     │
                                     │ HTTPS
                                     ▼
                      [ Vercel Global Edge CDN ]
                         (tripwiser.vercel.app)
                                     │
                                     │ Internal Proxy Rewrite (/api/v1/*)
                                     ▼
                      [ Railway Web Service ]
                       (FastAPI / Uvicorn API)
                          │               │
        asyncpg / Port 5432               │ TCP / Port 6379
                          ▼               ▼
     [ Railway PostGIS Database ]    [ Railway Redis ]
      (8,697 Stations, 164 Trains,      (Cache Store)
       23,602 Compiled Schedules)
```

---

## 2. External Accounts & Services Checklist

To deploy TripWiser to production, configure the following accounts and services:

1. **GitHub Account**: Hosts the TripWiser repository used for continuous deployment.
2. **Vercel Account** (Free Hobby Tier):
   - Used for hosting `tripwiser-frontend`.
   - Connected to the GitHub repository.
3. **Railway Account** (Hobby or Pro Tier):
   - Project: `tripwiser-production`.
   - Service 1: `postgis-db` (Docker image: `postgis/postgis:15-3.3-alpine`).
   - Service 2: `redis-cache` (Docker image: `redis:7-alpine`).
   - Service 3: `backend-api` (Deployed from GitHub repo `/backend` subdirectory).
4. **Domain & DNS** (Optional): Custom domain names (e.g. `tripwiser.in`) configured via Vercel and Railway DNS CNAME/A records.

---

## 3. Required Environment Variables

> **Security Rule**: Never commit `.env` files, production passwords, or database credentials to version control. Use `.env.production.example` as a template.

### A. Frontend (Vercel Project Settings > Environment Variables)

| Variable Name | Required | Default / Example Value | Description |
| :--- | :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | **Yes** | `https://tripwiser-backend.up.railway.app` | Public HTTPS URL of the deployed FastAPI backend. Used by Next.js server-side proxy rewrites. |

### B. Backend (Railway Web Service > Variables)

| Variable Name | Required | Default / Example Value | Description |
| :--- | :--- | :--- | :--- |
| `PROJECT_NAME` | No | `TripWiser API` | Application title reported in metadata. |
| `VERSION` | No | `0.1.0` | API version string. |
| `ENVIRONMENT` | **Yes** | `production` | Deployment environment mode. |
| `PORT` | Auto | (Injected by Railway) | Port on which Uvicorn binds (`0.0.0.0:${PORT}`). Defaults to `8000`. |
| `DATABASE_URL` | **Yes** | `postgresql+asyncpg://tripwiser:<pass>@postgis-db.railway.internal:5432/tripwiser_db?ssl=require` | Database connection string. Automatically normalizes `postgres://` to `postgresql+asyncpg://` and maps `sslmode` safely without weakening SSL. |
| `REDIS_URL` | **Yes** | `redis://redis-cache.railway.internal:6379/0` | Internal Redis connection string. |
| `BACKEND_CORS_ORIGINS` | **Yes** | `["https://tripwiser.vercel.app","http://localhost:3000"]` | JSON array or comma-separated list of allowed web origins. |
| `AVAILABILITY_PROVIDER`| No | `mock` | Vacancy provider selector. |
| `CHART_VACANCY_PROVIDER`| No | `mock` | Chart reservation vacancy provider selector. |
| `MIN_TRANSFER_MINUTES` | No | `30` | Minimum transfer buffer threshold. |
| `MAX_LAYOVER_MINUTES` | No | `360` | Maximum transfer layover window threshold. |

### C. PostGIS Database (Railway PostGIS Service > Variables)

| Variable Name | Required | Default / Example Value | Description |
| :--- | :--- | :--- | :--- |
| `POSTGRES_DB` | **Yes** | `tripwiser_db` | PostgreSQL database name. |
| `POSTGRES_USER` | **Yes** | `tripwiser` | Database master user. |
| `POSTGRES_PASSWORD` | **Yes** | `<strong_random_password>` | Master user password. |

---

## 4. Step-by-Step Deployment Runbook

### Step 1: Provision Railway Database & Redis
1. In the Railway dashboard, create a new project: `tripwiser-production`.
2. **Deploy PostGIS**:
   - Click **+ New** > **Docker Image**.
   - Image: `postgis/postgis:15-3.3-alpine`.
   - Name service: `postgis-db`.
   - Under **Variables**, add:
     - `POSTGRES_DB=tripwiser_db`
     - `POSTGRES_USER=tripwiser`
     - `POSTGRES_PASSWORD=<generate_secure_password>`
   - Under **Settings** > **Volumes**, add a persistent volume:
     - Mount path: `/var/lib/postgresql/data`
     - Size: `5 GB` or `10 GB`.
3. **Deploy Redis**:
   - Click **+ New** > **Docker Image**.
   - Image: `redis:7-alpine`.
   - Name service: `redis-cache`.

### Step 2: Deploy Backend API on Railway
1. In `tripwiser-production`, click **+ New** > **GitHub Repo**.
2. Select your `tripwiser` repository.
3. Under **Settings**:
   - Root Directory: `/backend`
   - Builder: `Dockerfile` (automatically uses `backend/Dockerfile` with `entrypoint.sh`).
4. Under **Variables**, add:
   - `ENVIRONMENT=production`
   - `DATABASE_URL=postgresql+asyncpg://tripwiser:<password>@postgis-db.railway.internal:5432/tripwiser_db`
   - `REDIS_URL=redis://redis-cache.railway.internal:6379/0`
   - `BACKEND_CORS_ORIGINS=["https://<your-project>.vercel.app","http://localhost:3000"]`
5. Generate a public domain under **Settings** > **Networking** (e.g. `https://tripwiser-backend.up.railway.app`).
6. Notice: On container boot, `entrypoint.sh` automatically runs `alembic upgrade head` before Uvicorn starts listening on `0.0.0.0:${PORT}`.

### Step 3: Seed Production Railway Timetable Data
Connect to the running backend service (via Railway CLI or one-off task) and run the verified idempotent ingestion command:

```bash
# Ingest full verified DataMeet network dataset with official running calendars
python -m app.cli.import_railway_data --source datameet --persist-all
```

> **Data Integrity Constraint**: Do NOT run `import_chart_vacancies` in production. Live vacancy feeds are not connected; Bachelor Special segments disclose timetable berth discovery transparently.

### Step 4: Deploy Frontend on Vercel
1. Log in to Vercel and click **Add New** > **Project**.
2. Import the `tripwiser` GitHub repository.
3. In Project Configuration:
   - Framework Preset: **Next.js**
   - Root Directory: `frontend`
4. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL` = `https://<your-backend-service>.up.railway.app`
5. Click **Deploy**. Vercel will build and publish the application globally.

---

## 5. Production Verification & Smoke-Test Checklist

Verify each of the following 12 items against the public deployment:

- [ ] **1. Frontend Loads**: Open `https://<frontend>.vercel.app`. Homepage renders with title, search forms, and navigation tabs with zero console errors.
- [ ] **2. Backend Health**: `GET https://<backend>/api/v1/health` returns HTTP 200:
  ```json
  {"status":"ok","version":"0.1.0","environment":"production"}
  ```
- [ ] **3. Readiness Probe**: `GET https://<backend>/api/v1/health/ready` returns HTTP 200:
  ```json
  {"status":"ready","services":{"database":true,"redis":true}}
  ```
- [ ] **4. Database Entity Counts**: Verify exact record counts in production PostgreSQL:
  - Stations: **8,697** (`SELECT count(*) FROM stations;`)
  - Spatial Point Geometries: **8,697** (`SELECT count(*) FROM stations WHERE location IS NOT NULL;`)
  - Compiled Trains: **164** (`SELECT count(*) FROM trains;`)
  - Schedule Stops: **23,602** (`SELECT count(*) FROM train_schedules;`)
  - PostGIS Extension: Active (`SELECT postgis_version();`)
  - Alembic Revision: `003_expand_train_number_length` (`SELECT version_num FROM alembic_version;`)
- [ ] **5. Station Search**: Autocomplete for `"BCT"` returns Mumbai Central; `"NDLS"` returns New Delhi.
- [ ] **6. Train Search**: Search for `"12951"` returns Mumbai Rajdhani Express with schedule details.
- [ ] **7. Direct Journey Search**: Route search for `BCT` ➔ `NDLS` on a valid operating day returns direct train routes.
- [ ] **8. Multi-Transfer Journey Search**: Route search for `BCT` ➔ `HWH` with 1–2 transfers returns verified itineraries with layovers $\ge 30$ mins.
- [ ] **9. Train Comparison**: Compare two trains on a shared corridor (e.g. `12951` and `12953`); verifies forward-segment speed and duration metrics.
- [ ] **10. Journey Planning Workspace**: Add candidate routes to plan, designate Preferred option, and switch between sorting priorities (`Fastest`, `Fewest Changes`, `Comfortable Transfers`).
- [ ] **11. Bachelor Special & Disclosures**: Stoppage inspection displays berth segment discovery with clear "no live vacancy provider connected" disclosure.
- [ ] **12. Zero CORS or API Errors**: Browser network inspector displays HTTP 200 responses for all `/api/v1/*` proxy calls with no CORS policy rejections.

---

## 6. Rollback Procedure

If a critical issue occurs during or after deployment:

### Frontend Rollback (Vercel)
1. Go to the Vercel Project Dashboard > **Deployments**.
2. Locate the previous stable deployment.
3. Click the three dots `...` > **Instant Rollback**.
4. Traffic is immediately redirected to the previous build in under 5 seconds.

### Backend Rollback (Railway)
1. Go to the Railway Service Dashboard > **Deployments**.
2. Select the previous stable commit or deployment.
3. Click **Redeploy**.
4. Railway restarts the container with the previous image.

### Database Migration Downgrade (If Required)
If a newly deployed migration must be reverted:
```bash
# Downgrade one revision
alembic downgrade -1

# Or downgrade to a specific revision
alembic downgrade 002_chart_vacancies_unique
```

---

## 7. Known Operational Limitations

1. **No Live Delay Prediction**: TripWiser operates strictly on verified timetables and official running calendars. It does not synthesize or predict live GPS train delays.
2. **Bachelor Special Berth Vacancy Feed**: Live chart reservation vacancies require an official IRCTC partner API integration. The platform currently discloses berth segment availability as a structural timetable prototype without fabricating real-time vacant berths.
3. **Browser-Local Storage**: Journey plans and preferences are stored locally in the passenger's browser (`localStorage`). Clearing browser cache will reset locally saved plans.
