# SupplyTracker

SupplyTracker is a PortWatch-driven port and chokepoint analytics dashboard that surfaces real-time vessel-flow data alongside freight indices, bunker prices, and LLM-generated decision briefs. Inspired by hormuztracking.com and built on top of the SupplyChainWatch UI shell, it turns raw IMF PortWatch signals into actionable supply-chain intelligence.

## Quick start

**Prerequisites:** Docker Desktop (or Docker Engine + Compose v2), GNU Make.

```bash
git clone <repo-url> && cd SupplyTracker
cp .env.example .env
# Fill in FRED_API_KEY, DASHSCOPE_API_KEY, and any other blank keys
make up          # builds and starts all services (~2 min first run)
make bootstrap   # runs DB migrations + seeds 90 days of demo data
```

Open http://localhost:5173 — the dashboard should show seeded ports, chokepoints, and macro indices.

| Service     | URL                        |
|-------------|----------------------------|
| Frontend    | http://localhost:5173      |
| Backend API | http://localhost:8000      |
| API Docs    | http://localhost:8000/docs |
| Flower      | http://localhost:5555      |
| Mailpit     | http://localhost:8025      |
| Postgres    | localhost:5432             |
| Redis       | localhost:6379             |

## Common make targets

| Target         | What it does                                          |
|----------------|-------------------------------------------------------|
| `make up`      | Start all containers                                  |
| `make down`    | Stop all containers                                   |
| `make logs`    | Tail all container logs                               |
| `make migrate` | Apply Alembic migrations                              |
| `make bootstrap` | Migrate + seed 90 days of synthetic demo data       |
| `make collect-all` | Trigger a full data collection across all sources |
| `make forecast`    | Run the daily forecast pass                       |
| `make test`    | Run backend (pytest) + frontend (vitest) tests        |
| `make lint`    | Run ruff + mypy on the backend                        |
| `make shell-be` | Open a shell in the backend container               |
| `make shell-fe` | Open a shell in the frontend container              |

## Run tests

```bash
make test              # all tests inside Docker
# or locally:
cd backend && python -m pytest tests/
cd frontend && npm test
```

## Smoke checklist (after `make bootstrap`)

- [ ] Overview tab: KPI strip counts ports + chokepoints, freshness banner absent, macro indices strip shows FBX/WCI/Brent
- [ ] Click a macro index card → modal renders full timeseries
- [ ] Chokepoint Activity strip: selector populates, 50-day AreaChart renders
- [ ] Ports tab: 14 seeded ports listed; star icon persists across page reload
- [ ] Port detail: map centered on port, KPI strip, 50-day breakdown chart, forecast panel shows "Insufficient history" (expected for 90-day seed, scoring DAG not yet run)
- [ ] Chokepoints tab + detail: same as ports
- [ ] Chatbot widget: floating button opens SSE stream against `/api/v1/chat`
- [ ] `GET /api/v1/health` returns `{"status":"ok"}`
- [ ] Flower at :5555 shows registered tasks

## News feed

Port and chokepoint detail pages include a **News** tab in the Event Log card that surfaces Google News RSS articles fetched every 6 hours (no API key required).

| Env var | Default | Description |
|---------|---------|-------------|
| `NEWS_FETCH_ENABLED` | `true` | Set to `false` to disable all news collection |
| `NEWS_MAX_ITEMS_PER_ENTITY` | `30` | Cap on items stored per entity per collection run |

## Sync button

The **Sync** button on port/chokepoint detail pages triggers a force-fetch of all collectors (`POST /sync/all`). It is only visible when an admin bearer token is configured.

The frontend reads the token from `VITE_SYNC_BEARER_TOKEN` (set at build time in `.env`) or from `localStorage.getItem('sync_token')` at runtime. The token must match `SYNC_BEARER_TOKEN` in the backend `.env`.

```bash
# .env
SYNC_BEARER_TOKEN=my-strong-random-token

# frontend .env (or set at build time)
VITE_SYNC_BEARER_TOKEN=my-strong-random-token
```
