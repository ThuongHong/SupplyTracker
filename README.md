# SupplyTracker

SupplyTracker is a Docker Compose based analytics dashboard for monitoring ports,
chokepoints, freight indices, bunker prices, macro signals, and AI-generated
supply-chain briefs.

The current deployment model is intentionally simple: run the full stack with
Docker Compose. Compose starts the React frontend, FastAPI backend, Postgres,
Redis, Celery workers, scheduled jobs, Flower, and Mailpit from one repository.

![SupplyTracker overview](docs/images/supplytracker-overview.png)

## Screenshots

| Ports | Port detail |
| --- | --- |
| ![Tracked ports table](docs/images/supplytracker-ports.png) | ![Port detail view](docs/images/supplytracker-port-detail.png) |

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, Vite, TypeScript, Tailwind, Recharts, deck.gl, MapLibre |
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic, Server-Sent Events |
| Data store | Timescale/Postgres with PostGIS extensions |
| Queue/cache | Redis, Celery worker, Celery beat |
| Data sources | IMF PortWatch, FRED, FBX/WCI scrapers, bunker price scraper, GNews |
| AI features | DashScope Qwen via OpenAI-compatible client |
| Local tools | Flower for Celery monitoring, Mailpit for local SMTP capture |

## Docker Compose Quick Start

Prerequisites:

- Docker Engine or Docker Desktop with Compose v2
- GNU Make
- API keys for the optional collectors and AI features you want to enable

```bash
git clone <repo-url>
cd SupplyTracker
cp .env.example .env
```

Fill in the required values in `.env`:

```bash
FRED_API_KEY=...
GNEWS_API_KEY=...
DASHSCOPE_API_KEY=...
SYNC_BEARER_TOKEN=<strong-random-token>
VITE_SYNC_BEARER_TOKEN=<same-token-if-you-want-the-sync-button>
```

Start the stack:

```bash
make up
```

Apply migrations and seed local demo data:

```bash
make bootstrap
```

Open the app:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Flower: http://localhost:5555
- Mailpit: http://localhost:8025

## Services

`docker-compose.yml` starts these containers:

| Service | Port | Purpose |
| --- | --- | --- |
| `frontend` | `5173` | Vite dev server for the React app |
| `backend` | `8000` | FastAPI API and SSE endpoints |
| `postgres` | `5432` | Timescale/Postgres database with PostGIS |
| `redis` | `6379` | Celery broker/result backend and cache |
| `celery-worker` | internal | Background collection, scoring, forecasting, and narrative tasks |
| `celery-beat` | internal | Scheduled collector/scoring/forecast jobs |
| `flower` | `5555` | Celery task monitor |
| `mailpit` | `1025`, `8025` | Local SMTP sink and web inbox |

## Make Targets

```bash
make help
make up          # build and start the Compose stack
make down        # stop and remove containers
make logs        # follow container logs
make migrate     # run Alembic migrations
make bootstrap   # migrate, then seed development data
make test        # run backend pytest suite inside Docker
make lint        # run backend ruff + mypy inside Docker
make shell-be    # open a backend container shell
make shell-fe    # open a frontend container shell
```

Frontend tests run from the frontend container:

```bash
docker compose exec frontend npm test
docker compose exec frontend npm run lint
```

## Data and Jobs

After `make bootstrap`, the app has demo ports, chokepoints, metrics, and risk
signals. Live data collection runs through Celery tasks:

- PortWatch tracked-entity refresh
- FRED macro indicators
- FBX and WCI freight indices
- Bunker fuel prices
- GNews articles for tracked entities
- Hourly risk scoring
- Daily forecast pass
- Daily AI narrative fill

Celery beat owns the schedule in `backend/app/tasks/schedule.py`. Flower at
http://localhost:5555 is the fastest way to confirm that workers and scheduled
tasks are registered.

## Sync Button

The UI can expose a protected Sync button on port and chokepoint detail pages.
It triggers backend sync endpoints such as `POST /api/v1/sync/all`.

Set the same token in backend and frontend env:

```bash
SYNC_BEARER_TOKEN=<strong-random-token>
VITE_SYNC_BEARER_TOKEN=<same-token>
```

The frontend also supports setting `sync_token` in `localStorage` at runtime.

## Environment Notes

Required for a useful local run:

- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `PORTWATCH_BASE_URL`
- `VITE_API_BASE_URL`

Required for specific features:

- `FRED_API_KEY`: FRED collector
- `GNEWS_API_KEY`: news collection
- `DASHSCOPE_API_KEY`: AI chat, decision briefs, and narrative generation
- `SYNC_BEARER_TOKEN`: protected manual sync endpoints
- `FBX_SOURCE_URL`, `WCI_SOURCE_URL`: freight index scrapers when external source URLs are configured

See `.env.example` for the full list.

## Smoke Check

After `make bootstrap`, check:

- `GET http://localhost:8000/api/v1/health` reports `status`, `db`, and `redis` as `ok`
- The Overview page loads market indices, tracked ports, and chokepoints
- Ports page lists tracked ports and track/untrack controls
- Chokepoints page lists tracked chokepoints
- API docs load at http://localhost:8000/docs
- Flower lists registered Celery tasks at http://localhost:5555
- Mailpit opens at http://localhost:8025

## Vercel Frontend + ngrok Backend (Split Deploy)

You can host the frontend on Vercel while the backend stack keeps running on your
own machine via Docker Compose, exposed publicly through an ngrok tunnel.

### 1. Run the backend locally

```bash
make up
make bootstrap
```

The backend listens on `http://localhost:8000`.

### 2. Tunnel the backend with ngrok

A reserved ngrok domain keeps the URL stable, so you only configure Vercel once:

```bash
ngrok config add-authtoken <your-token>      # one-time
ngrok http --url=<your-domain>.ngrok-free.dev 8000
```

ngrok-free serves a browser interstitial on requests with a browser User-Agent.
The frontend API client sends the `ngrok-skip-browser-warning: true` header on
every request (`frontend/src/api/client.ts`) so `fetch()` receives JSON instead
of the warning HTML.

### 3. Allow the Vercel origin in CORS

Add your Vercel URL to `CORS_ORIGINS` in `.env` (comma-separated, no trailing
path):

```bash
CORS_ORIGINS=http://localhost:5173,https://<your-app>.vercel.app
```

Recreate the backend container so the new env is loaded. `docker compose
restart` does **not** re-read `.env` — use:

```bash
docker compose up -d backend
```

Verify the preflight returns the origin:

```bash
curl -s -i -X OPTIONS http://localhost:8000/api/v1/ \
  -H "Origin: https://<your-app>.vercel.app" \
  -H "Access-Control-Request-Method: GET" | grep -i access-control-allow-origin
```

### 4. Point Vercel at the tunnel

In the Vercel project: Settings → Environment Variables:

```
VITE_API_BASE_URL = https://<your-domain>.ngrok-free.dev
```

`VITE_` vars are injected at build time, so redeploy after changing it. With a
reserved ngrok domain you set this once and never redeploy for tunnel changes.

The frontend stays up on Vercel even while your machine is off; API-backed views
only work while the backend and ngrok tunnel are running.

## Current Deployment Posture

The project is currently optimized for one-host Docker Compose deployment. For a
VPS, copy the repository, provide a production `.env`, run `make up`, run
`make migrate`, and place a reverse proxy such as Caddy, Nginx, or Traefik in
front of the frontend and backend ports.

The split free-tier cloud path can be explored later, but it is not equivalent
to the Compose stack because this app depends on a database, Redis, background
workers, and scheduled Celery jobs.
