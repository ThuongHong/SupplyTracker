## 1. Repo & Tooling

- [x] 1.1 Add `.env.example` enumerating every env var referenced in design (DB URL, REDIS_URL, FRED_API_KEY, DASHSCOPE_API_KEY, QWEN_PRIMARY_MODEL, QWEN_FALLBACK_MODEL, SYNC_BEARER_TOKEN, CORS_ORIGINS, etc.)
- [x] 1.2 Add root `Makefile` with `up`, `down`, `logs`, `shell-be`, `shell-fe`, `test`, `lint`, `collect-all`, `forecast`, `migrate`, `bootstrap` targets
- [x] 1.3 Add `.gitignore` covering Python, Node, Docker volumes, `.env`, IDE files
- [x] 1.4 Add top-level `README.md` quick-start (one paragraph + service URL table)

## 2. Docker & Infra

- [x] 2.1 Write `docker/postgres/init.sql` enabling `timescaledb` and `postgis` extensions
- [x] 2.2 Write `docker/backend.Dockerfile` (python:3.12-slim, uv or pip, non-root user)
- [x] 2.3 Write `docker/frontend.Dockerfile` (node:20-alpine, vite dev server)
- [x] 2.4 Write `docker-compose.yml` with services: `postgres` (timescale+postgis image), `redis`, `backend`, `frontend`, `celery-worker`, `celery-beat`, `flower`, `mailhog` — wired to ports 5173/8000/5555/8025/5432/6379

## 3. Backend Scaffold

- [x] 3.1 `backend/pyproject.toml` with deps: fastapi, uvicorn[standard], sqlalchemy>=2, alembic, psycopg[binary], geoalchemy2, celery, redis, httpx, pandas, statsforecast, pydantic, pydantic-settings, openai, dashscope, sse-starlette, pytest, pytest-asyncio, respx, ruff, mypy
- [x] 3.2 `backend/app/config.py` using `pydantic-settings` for all env vars
- [x] 3.3 `backend/app/db/session.py` with sync + async engines and a `Base = declarative_base()`
- [x] 3.4 `backend/app/db/models.py` defining every kept table: Port, Chokepoint, PortWatchMetric, FreightIndex, BunkerPrice, PortCongestion, ChokepointStatus, PortRiskScore, ChokepointRiskScore, RiskFeatureSnapshot, RiskStoryEvent, EntityRiskForecast, Insight, DisruptionPropagation, DataCoverage, CollectionLog, LLMUsageLog
- [x] 3.5 `backend/alembic/` init + first migration `0001_initial.sql` that creates all tables + Timescale hypertables + PostGIS geometry columns + indices
- [x] 3.6 `backend/app/main.py` mounting CORS, exception handlers, error envelope, and the v1 router
- [x] 3.7 `backend/app/api/deps.py` (db session, auth bearer dep) and `backend/app/api/rate_limit.py` (redis-backed token bucket)

## 4. Collectors

- [x] 4.1 `collectors/base.py` defining a `BaseCollector` ABC with `run()`, retry/backoff helpers, and CollectionLog/CoverageRow update hooks
- [x] 4.2 `collectors/portwatch.py` for ports + chokepoints + reference bootstrap (upsert into PortWatchMetric, Port, Chokepoint)
- [x] 4.3 `collectors/fred.py` for configured FRED series → FreightIndex (source="fred")
- [x] 4.4 `collectors/fbx_scraper.py` for FBX index → FreightIndex
- [x] 4.5 `collectors/wci_scraper.py` for Drewry WCI → FreightIndex
- [x] 4.6 `collectors/bunker_scraper.py` for configured (port, fuel) tuples → BunkerPrice
- [x] 4.7 Tests for each collector with `respx`-mocked HTTP, covering success, 429 backoff, partial failure isolation

## 5. Risk Pipeline

- [x] 5.1 `analysis/risk_components.yaml` defining metric→component mapping, weights, baseline windows, direction
- [x] 5.2 `analysis/baselines.py` computing 30d/90d rolling mean+stdev per (entity, metric)
- [x] 5.3 `analysis/scoring.py` producing `RiskFeatureSnapshot` + `PortRiskScore`/`ChokepointRiskScore` rows with severity bucketing and missing-component handling
- [x] 5.4 `analysis/events.py` detecting z-spikes, severity transitions, streaks → `RiskStoryEvent` upserts via deterministic `event_key`
- [x] 5.5 `analysis/forecasting.py` running AutoETS via statsforecast, gating on 60-day minimum, computing bands, writing `EntityRiskForecast`
- [x] 5.6 `services/disruption.py` writing `DisruptionPropagation` rows from chokepoint events using PostGIS lane geometry
- [x] 5.7 `services/insights.py` materializing `Insight` rows from notable events (top severity, top z-score, sustained streaks)
- [x] 5.8 Tests for scoring math (z-scores, severity buckets, missing-component gate) and event detection idempotency

## 6. LLM Layer

- [x] 6.1 `llm/client.py` wrapping OpenAI SDK pointed at DashScope, primary+fallback model selection, retry, token-count capture
- [x] 6.2 `llm/safety.py` rules-based validator (regex + denylist + injection heuristics) returning `(ok, reason)`
- [x] 6.3 `llm/prompts.py` system prompts for narrative, decision-brief, chatbot — each with guardrail block
- [x] 6.4 `llm/brief.py` Decision Brief generation with Redis 1h cache keyed on `(date, top-events-hash)`
- [x] 6.5 `llm/chat.py` chat orchestration: pulls grounded context for `entity_context`, runs safety, streams SSE chunks, logs LLMUsageLog
- [x] 6.6 `tasks/narrate.py` Celery task that fills `Insight.narrative_llm` for unnarrated insights in batches
- [x] 6.7 Tests for safety validator (positive + injection cases) and chat grounding (no missing-number invention)

## 7. API Routes

- [x] 7.1 `api/routes/health.py` — DB+Redis probes
- [x] 7.2 `api/routes/ports.py` — list (paginated, filterable by severity), detail
- [x] 7.3 `api/routes/chokepoints.py` — list, detail, `/breakdown` (50-day per-category counts)
- [x] 7.4 `api/routes/indices.py` — list with `latest_value`, `change_pct_7d/30d`, single-series timeseries
- [x] 7.5 `api/routes/risk.py` — scores list, score+snapshot detail, forecast detail w/ staleness gate
- [x] 7.6 `api/routes/story.py` — `since` cursor, ordered desc, capped 200
- [x] 7.7 `api/routes/insights.py` — list filtered by `attention_level`
- [x] 7.8 `api/routes/stats.py` — `/coverage` filtered by source/entity_type
- [x] 7.9 `api/routes/sync.py` — bearer-protected POST per source, returns Celery task id
- [x] 7.10 `api/routes/chat.py` — SSE stream wired to llm/chat.py
- [x] 7.11 Pydantic response schemas in `backend/app/schemas/` for every endpoint
- [x] 7.12 Contract tests for each route (happy path + one error case)

## 8. Celery Wiring

- [x] 8.1 `tasks/schedule.py` celery-beat schedule reading cadences from config
- [x] 8.2 `tasks/collect.py` task per collector + `collect_all` chord
- [x] 8.3 `tasks/score.py` chained DAG: PortWatch → features → score → events → insights → narrate
- [x] 8.4 `tasks/forecast.py` daily forecast pass
- [x] 8.5 Verify Flower shows tasks and that `make collect-all` / `make forecast` enqueue correctly

## 9. Frontend Scaffold

- [x] 9.1 `frontend/package.json` deps: react, react-dom, typescript, vite, @vitejs/plugin-react, tailwindcss, postcss, autoprefixer, maplibre-gl, deck.gl, @deck.gl/layers, @deck.gl/react, recharts, vitest, @testing-library/react
- [x] 9.2 `vite.config.ts`, `tailwind.config.ts`, `tsconfig.json`, `index.html`
- [x] 9.3 `src/main.tsx`, `src/App.tsx` with hash router, three top-level tabs (Overview/Ports/Chokepoints) + nested detail routes `#/ports/{id}` and `#/chokepoints/{id}`, lazy import of detail views, Suspense fallback, default→`#/overview`, legacy redirects (`#/dashboard|#/indices|#/map|#/analytics|#/insights|#/vessels`→`#/overview`)
- [x] 9.4 `src/components/layout/Sidebar.tsx` (collapsible, auto-collapse <760px, exactly 3 nav items) and `Header.tsx` (theme toggle persisting to `documentElement`)
- [x] 9.5 Base UI primitives: `Card`, `Badge`, `StatusDot`, `DataState`, `Sparkline`, `AreaChart`, `InsightRow`, `MiniMap`, `icons.tsx`
- [x] 9.6 `src/api/` typed fetch client per route, with error-envelope handling and 401/429 surfacing
- [x] 9.7 Dark/light Tailwind tokens with WCAG AA contrast checked for both

## 10. Frontend Tabs & Detail Views

- [x] 10.1 `pages/Overview.tsx` — freshness banner, KPI strip, chokepoint selector + 50-day stacked strip chart, Decision Brief panel, macro indices strip (FBX/WCI/Brent sparklines + 7d/30d delta badges + click → modal with full timeseries), top-5 ports by severity (preferring tracked ports on ties), Insights feed (last 20, `attention_level` filter)
- [x] 10.2 `pages/Ports.tsx` — list of every PortWatch port; star icon per row toggling localStorage-persisted tracked set (pinned to top); text search (name/locode/country), region filter, severity filter; row click navigates to `#/ports/{id}`
- [x] 10.3 `pages/PortDetail.tsx` (lazy) — header (name/country/locode/severity badge/latest score/last-observed/track button) + MapLibre map centered on port `geom` (single circle sized by 7d mean throughput, colored by severity) + KPI strip (today/7d/30d/z-score) + 50-day stacked breakdown chart by PortWatch category + metric drill-down section (metric picker → timeseries with 30/90d baseline bands + z-score strip + drivers bar chart) + 14-day forecast panel (bands or "Insufficient history" badge) + LLM narrative + chronological event log from `RiskStoryEvent`
- [x] 10.4 `pages/Chokepoints.tsx` — same UX as Ports (list, star, search, severity filter); row click → `#/chokepoints/{id}`
- [x] 10.5 `pages/ChokepointDetail.tsx` (lazy) — same section layout as PortDetail, substituting `transit_calls`/`median_speed`/`vessel_count` as primary metrics and chokepoint `geom` for the map
- [x] 10.6 `src/data/tracked.ts` — localStorage helper for tracked ports + chokepoints (get/add/remove/subscribe) shared across Overview, Ports, Chokepoints
- [x] 10.7 `components/ChatbotWidget.tsx` — floating button, SSE consumer rendering streaming tokens, `entity_context` derived from active tab/detail route
- [x] 10.8 Vitest unit tests for Overview decision-brief panel, ChatbotWidget SSE handling, tracked-entities localStorage helper, PortDetail drivers math helper, route redirect logic for legacy hashes

## 11. Fixtures & Seed

- [x] 11.1 `backend/app/fixtures/ports_seed.json` and `chokepoints_seed.json` mirroring PortWatch reference (fallback when API unreachable)
- [x] 11.2 `backend/app/scripts/seed_dev.py` loading fixtures + 90 days of synthetic PortWatch metrics for local demo
- [x] 11.3 `make bootstrap` target running migrate + seed_dev

## 12. Quality Gates

- [x] 12.1 Ruff + mypy clean on `backend/`
- [x] 12.2 `pytest` green: collectors, scoring, events, forecasts, safety, route contracts
- [x] 12.3 `vitest` green: components + page logic helpers
- [x] 12.4 `make up` brings stack up; manual smoke checklist: dashboard renders w/ seeded data, chokepoint breakdown loads, chatbot streams, decision brief generates, coverage banner correct, forecast endpoint returns either data or `insufficient` status
- [x] 12.5 Update root `README.md` with full run instructions and a screenshot of the seeded dashboard
