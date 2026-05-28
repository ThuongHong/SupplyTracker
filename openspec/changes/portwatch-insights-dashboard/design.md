## Context

The original SupplyChainWatch (kvgkvg/SupplyChainWatch) had a polished frontend shell (hash router + collapsible sidebar + lazy pages + ChatbotWidget) but a sprawling backend: live AIS via aisstream, vessel-level tables, Comtrade trade flows, weather overlays, plus PortWatch, FRED, FBX, WCI, and bunker scrapers feeding parallel risk/insight/forecast pipelines. That breadth made it hard to deliver Hormuztracking-grade depth on any one slice (Hormuztracking nails one chokepoint with 50-day per-category breakdowns, live counts, and crisp narratives).

This rebuild keeps the SupplyChainWatch shell verbatim and rebuilds the data backbone around **PortWatch as the canonical entity-metric source** plus a thin macro/freight/bunker context layer. We retain the explainable risk/forecast/insight pipeline contracts so the UI can stay rich, but we delete vessel-level concerns. The repo is `SupplyTracker` (currently empty besides a LICENSE/README).

Stakeholders: the user (sole developer, course project context). No production users yet; correctness, reproducibility, and demo polish outrank scale.

## Goals / Non-Goals

**Goals:**
- Deliver a Hormuztracking-style dashboard experience (50-day strip charts, headline KPIs, decision brief) but generalized across all PortWatch ports and chokepoints.
- Reuse the SupplyChainWatch UI shell with minimal modification so design effort is spent on data depth, not chrome.
- Keep the entity-risk pipeline explainable: every score has a `RiskFeatureSnapshot`, every event has a deterministic key, every forecast has a sufficiency status.
- Keep the Qwen LLM integration with safety validation, fallback model, and token accounting.
- Ship a docker-compose dev stack that runs end-to-end with one `make up`.

**Non-Goals:**
- Live AIS ingestion or vessel-level tracking.
- Trade flow analytics (Comtrade) or weather overlays.
- Multi-tenant auth, user accounts, billing, mobile app.
- Real-time push (WebSocket fanout beyond the chatbot SSE stream).
- Production-grade SLOs; this is a demo/coursework deployment.

## Decisions

### D1. PortWatch is the single source of truth for entity metrics
`PortWatchMetric` is the only daily entity-level metric table. All risk features are derived from it (joined with chokepoint geography). Rationale: avoids parallel ingestion paths and reduces the schema drift that hurt SupplyChainWatch. Alternative considered: keep a generic `EntityMetric` table fed by multiple collectors — rejected because PortWatch's schema already generalizes via `entity_type`/`entity_id`/`metric_name`, and we don't have other entity-level providers in scope.

### D2. Drop the `Vessel`/`VesselPosition`/`Anomaly`/`TradeFlow` tables, keep the rest of the old schema
We carry over `Port`, `Chokepoint`, `PortWatchMetric`, `FreightIndex`, `BunkerPrice`, `PortCongestion`, `ChokepointStatus`, `PortRiskScore`, `ChokepointRiskScore`, `RiskFeatureSnapshot`, `RiskStoryEvent`, `EntityRiskForecast`, `Insight`, `DisruptionPropagation`, `DataCoverage`, `CollectionLog`, `LLMUsageLog`. We delete vessel-level and trade-flow tables. Rationale: the kept tables are the explainability spine; the dropped ones served a use case we're not building.

### D3. Hash routing + lazy pages (verbatim from SupplyChainWatch)
We keep the hash router and lazy-load `EntityMap` (deck.gl is heavy) and `Analytics` (chart libs). Alternative considered: React Router with file-based routing (TanStack Router / Next App Router) — rejected because the existing shell already works and there is no SSR need.

### D4. EntityMap replaces VesselMap, no per-vessel layer
The map renders ports + chokepoints as circles; size = 7-day mean throughput; color = current severity. Click opens a side panel. Alternative considered: keep a "live vessels" placeholder layer — rejected because there's no AIS source in scope and a fake layer would be misleading.

### D5. Celery beat schedules driven by config, not hardcoded
Schedules live in `backend/app/tasks/schedule.py` reading from `config.py`/env so cadence can be tuned per source. Rationale: PortWatch may publish daily late; freight indices weekly; bunker daily.

### D6. Risk pipeline = features → snapshot → score → events → insights
A single nightly DAG: PortWatch ingestion → feature compute → `RiskFeatureSnapshot` write → score write → event detection → insight materialization → LLM narrative pass. Each stage is its own Celery task chained via `chain()` so partial failures don't restart the whole DAG. Alternative considered: Prefect / Airflow — rejected as overkill for a single DAG.

### D7. Score components are configurable, not hardcoded
Component definitions (which PortWatch metric, weight, baseline window, direction) live in a YAML at `backend/app/analysis/risk_components.yaml` loaded at startup. Rationale: lets us tune severity without redeploying business logic; also makes `feature_schema_version` meaningful (bump on YAML change).

### D8. Forecasts use a simple, explainable model (statsforecast AutoETS / AutoARIMA)
We use the `statsforecast` package for AutoETS on per-entity metrics with a 60-day minimum history. Quantile bands via residual bootstrap. Alternative considered: Prophet (heavy dep, slower), neural forecaster (overkill, opaque, hard to explain key drivers). `key_drivers` is filled by correlating the metric's recent residuals with other features and picking the top 3.

### D9. LLM via DashScope OpenAI-compatible endpoint
Use the `openai` Python SDK pointed at DashScope's compat URL. Primary: `qwen-plus`. Fallback: `qwen-turbo`. Reasoning models gated by env. Safety validator is a rules-based regex + denylist + simple instruction-injection heuristics (no second LLM call) — fast, deterministic, auditable. Alternative considered: Guardrails AI / NeMo Guardrails — rejected as too heavy for the demo footprint.

### D10. Chatbot uses SSE not WebSocket
SSE keeps backend simple (FastAPI `StreamingResponse`) and matches the request/response shape the ChatbotWidget already expects. WebSocket would force a separate connection lifecycle for no real gain at this scale.

### D11. Frontend chart library = recharts
We use `recharts` for strip/area/bar/sparkline charts. Alternative considered: visx (more flexible, more code), echarts (heavier, foreign API). recharts is the lowest friction for the chart shapes we need and matches the React idiom.

### D12. Decision Brief cached 1h in Redis
LLM cost control. Brief is regenerated on next request after TTL; on the cached path we still attach the freshness-of-underlying-data timestamp.

### D13. PostGIS + TimescaleDB stay
Timescale hypertables on `PortWatchMetric`, `FreightIndex`, `BunkerPrice`, `PortCongestion`, `ChokepointStatus`, `PortRiskScore`, `ChokepointRiskScore`, `RiskFeatureSnapshot`. PostGIS for `Port.geom` and `Chokepoint.geom` to support spatial queries (e.g., disruption propagation lane intersection). Both extensions already worked in the old project.

### D14. Tests = pytest (backend) + vitest (frontend), no e2e in MVP
Pytest covers collectors (with HTTP mocks), risk math, event detection, API contract tests. Vitest covers component logic. Playwright/e2e deferred.

### D15. Repo layout mirrors SupplyChainWatch
```
SupplyTracker/
├── backend/
│   ├── app/
│   │   ├── api/{deps.py,rate_limit.py,routes/{health,ports,chokepoints,indices,risk,story,insights,stats,sync,chat}.py}
│   │   ├── collectors/{base,portwatch,fred,fbx_scraper,wci_scraper,bunker_scraper}.py
│   │   ├── analysis/{risk_components.yaml,scoring.py,events.py,forecasting.py,baselines.py}
│   │   ├── llm/{client.py,safety.py,prompts.py,brief.py,chat.py}
│   │   ├── db/{models.py,session.py}
│   │   ├── schemas/  # pydantic
│   │   ├── services/  # query helpers, coverage, insights materialization
│   │   ├── tasks/{schedule.py,collect.py,score.py,forecast.py,narrate.py}
│   │   ├── fixtures/  # seed data for dev
│   │   ├── scripts/
│   │   ├── config.py
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/  # typed client
│   │   ├── components/{Card,Badge,AreaChart,Sparkline,StatusDot,DataState,InsightRow,MiniMap,ChatbotWidget,icons.tsx,layout/{Sidebar,Header}.tsx}
│   │   ├── pages/{Dashboard,MacroIndices,EntityMap,Ports,Chokepoints,Analytics,InsightsHub}.tsx
│   │   ├── data/  # static maps (chokepoint lane mappings, etc.)
│   │   ├── styles/
│   │   ├── App.tsx, main.tsx, vite-env.d.ts
│   └── package.json, vite.config.ts, tailwind.config.ts, tsconfig.json
├── docker/{backend.Dockerfile,frontend.Dockerfile,postgres/init.sql}
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Risks / Trade-offs

- **PortWatch schema drift** → Mitigation: collector validates response with pydantic models; failure surfaces in `CollectionLog`; weekly reference refresh diff is logged.
- **LLM cost / latency** → Mitigation: Decision Brief cached 1h; narratives written once per insight; chat rate-limited; token usage tracked in `LLMUsageLog` for quotas.
- **Prompt injection from chatbot users** → Mitigation: rules-based safety validator + scoped system prompt + no server-state tools exposed; refusals logged with `status="blocked_input"`.
- **Forecast misuse for low-data entities** → Mitigation: hard `data_sufficiency` gate; API hides stale rows; UI shows "insufficient history" badge instead of a fake line.
- **PostGIS/TimescaleDB lock-in** → Trade-off accepted: ergonomic wins outweigh portability; both ship in postgres docker image variants.
- **Hash routing + lazy chunks + SSR** → Non-issue: no SSR needed; we accept the SEO trade-off.
- **`recharts` performance on 50-day stacked charts** → Acceptable for ≤20 chokepoints × ≤6 categories; if it degrades we swap the chart components only.
- **Single-developer scope creep** → Mitigation: this proposal explicitly cuts vessels, AIS, trade flows; `tasks.md` enforces phasing (ingest → score → API → UI → LLM).

## Migration Plan

Greenfield repo — no migration. Bring-up order:

1. Scaffold `backend/` (FastAPI hello + Alembic init + first migration with all tables).
2. Scaffold `frontend/` (Vite + React + Tailwind + router + Sidebar/Header), placeholder pages.
3. `docker-compose.yml` w/ Postgres+Timescale+PostGIS, Redis, backend, frontend, celery-worker, celery-beat, flower, mailhog.
4. PortWatch + macro collectors with `pytest` HTTP mocks.
5. Risk DAG (scoring → events → forecasts) wired to Celery beat.
6. API routes consumed by typed frontend client.
7. LLM service + chatbot SSE + Decision Brief.
8. UI fit & finish; vitest coverage.

Rollback: drop the `SupplyTracker/backend` and `SupplyTracker/frontend` directories and the docker stack — repo state returns to its initial commit.

## Open Questions

- Q1: Which exact PortWatch endpoints expose category-level breakdowns for chokepoint transits? (Hormuztracking uses 4 categories — verify PortWatch parity at implementation time.)
- Q2: Do we want any pre-seeded chokepoint→ports lane mapping or derive from geography only? (Defaulting to geography in the spec; revisit if quality is poor.)
- Q3: Which FRED series ship in the default config? (Initial: `DCOILBRENTEU`, `DCOILWTICO`, `DGS10`, `PPIACO` — to be tuned.)
- Q4: Authentication for `POST /api/v1/sync/*` — env-derived bearer token sufficient, or do we want a tiny admin login? (Spec assumes bearer token.)
