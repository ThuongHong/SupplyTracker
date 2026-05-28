## Why

The prior SupplyChainWatch project sprawled across vessels, AIS streams, ports, chokepoints, freight, bunkers, trade flows, and risk pipelines — too broad to deliver deep, polished insight on any one slice. This rebuild (SupplyTracker) keeps the same UI shell but narrows the data backbone to IMF PortWatch + FRED macro/freight/bunker series, so we can ship Hormuztracking-grade analytics depth (daily breakdowns, multi-day historical strips, severity scoring, LLM narratives) on the entities PortWatch actually covers well: ports and maritime chokepoints.

## What Changes

- **BREAKING**: Drop live AIS ingestion, vessel-level tracking, and per-vessel watchlist/enrichment. No `Vessel`, `VesselPosition`, `VesselWatchlist`, `VesselEnrichmentCache` tables. No `aisstream` collector.
- **BREAKING**: Drop `TradeFlow`/Comtrade collector, `Anomaly` legacy table, and weather/openmeteo collector. Out of scope for the focused build.
- Keep IMF PortWatch as the primary entity-metric source (ports + chokepoints, daily granularity).
- Keep FRED, FBX, WCI, and bunker scrapers as the macro/freight/bunker context layer feeding `FreightIndex` and `BunkerPrice`.
- Reuse the existing risk/insight pipeline contracts (`PortRiskScore`, `ChokepointRiskScore`, `RiskFeatureSnapshot`, `RiskStoryEvent`, `EntityRiskForecast`, `Insight`, `DisruptionPropagation`, `DataCoverage`) but rescope feature schemas to PortWatch-derived metrics only.
- Reuse the SupplyChainWatch frontend shell: hash router, collapsible sidebar, dark/light toggle, lazy-loaded detail views, Suspense fallbacks, ChatbotWidget overlay. Same Tailwind/MapLibre/deck.gl stack.
- **BREAKING (vs. old SupplyChainWatch nav)**: Collapse the sidebar to exactly three top-level tabs — **Overview**, **Ports**, **Chokepoints**. Drop standalone `Dashboard` / `MacroIndices` / `VesselMap` / `Analytics` / `InsightsHub` tabs; their content is folded into Overview panels or into the entity detail views.
- Overview tab = Hormuztracking-style landing: freshness banner, KPI strip (today's chokepoint transits, count of high+critical entities, top mover by z-score), 50-day stacked strip chart with chokepoint selector, LLM Decision Brief panel, compact macro indices strip (FBX/WCI/Brent sparklines), top-5 ports by severity, last-20 Insights feed.
- Ports tab = full PortWatch port list with text/region/severity filters and a per-port "track" star (localStorage-persisted, pinned to top, also influences Overview). Click → nested detail view at `#/ports/{id}` (Hormuztracking-style): header + map centered on the port + KPI strip + 50-day stacked breakdown chart + metric drill-down (timeseries, 30/90d baselines, z-scores, drivers) + 14-day forecast + LLM narrative + event log.
- Chokepoints tab mirrors the Ports tab (same list/star/filter UX, same detail layout, chokepoint-appropriate metrics).
- Keep Qwen/DashScope LLM integration with safety validation, fallback model, narrative + chatbot + decision-brief features, and `LLMUsageLog` accounting.
- Keep docker-compose stack: FastAPI, Postgres 15 + TimescaleDB + PostGIS, Redis, Celery, Flower, Mailhog. Same ports.

## Capabilities

### New Capabilities
- `portwatch-ingestion`: Scheduled collection from IMF PortWatch for ports + chokepoints, normalized into `PortWatchMetric`, with collection logging, coverage tracking, and idempotent upserts.
- `macro-context-ingestion`: Scheduled collection of freight indices (FBX, WCI), FRED macro series, and bunker prices, populating `FreightIndex` and `BunkerPrice`.
- `entity-risk-scoring`: Daily computation of port and chokepoint risk scores from PortWatch metrics, with component breakdowns, z-scores vs rolling baselines, severity buckets, missing-component handling, and `RiskFeatureSnapshot` persistence.
- `risk-story-events`: Detection of notable changes (anomalies, regime shifts, sustained streaks) emitted to `RiskStoryEvent` for the Insights feed.
- `entity-forecasting`: Short-horizon forecasts of key per-entity metrics persisted to `EntityRiskForecast` with confidence and data-sufficiency status.
- `llm-narratives`: Qwen-backed narrative generation for insights, decision briefs, and risk stories, with prompt safety validation, model fallback, and `LLMUsageLog` accounting.
- `chatbot-assistant`: ChatbotWidget endpoint that grounds Qwen replies in the current dashboard state via a tool/context layer.
- `insights-api`: HTTP API surface (FastAPI routes for ports, chokepoints, indices, risk, story, insights, chat, stats, sync, health) that the React frontend consumes.
- `dashboard-ui`: React + Vite + Tailwind frontend reusing the SupplyChainWatch shell, rescoped to three top-level tabs (Overview, Ports, Chokepoints) with nested per-entity detail routes (`#/ports/{id}`, `#/chokepoints/{id}`) and a tracked-entities feature (localStorage).
- `data-coverage-tracking`: `DataCoverage` rows per (source, entity_type, entity_id) recording observed/expected/missing days and freshness, surfaced in UI freshness banners.

### Modified Capabilities
<!-- none — this is a fresh repo, no existing specs in openspec/specs/ -->

## Impact

- **Code**: Greenfield. Bootstraps `backend/` (FastAPI app, alembic, celery, collectors, services, llm, api/routes) and `frontend/` (Vite React TS app) under the existing `SupplyTracker` repo root. Adds `docker/`, `docker-compose.yml`, `Makefile`.
- **APIs**: New REST surface under `/api/v1/*`; new chatbot WebSocket/SSE endpoint.
- **Dependencies**: Python — FastAPI, SQLAlchemy 2, Alembic, Celery, Redis, httpx, pandas, GeoAlchemy2, dashscope SDK, openai SDK (compat). JS — React 18, Vite, TypeScript, Tailwind, MapLibre GL, deck.gl, recharts (or visx) for strip charts, Vitest for tests.
- **External services**: IMF PortWatch (public), FRED (API key), FBX/WCI scraping targets, DashScope Qwen API (API key). No AIS provider, no Comtrade.
- **Infra**: Postgres 15 + TimescaleDB + PostGIS, Redis 7, Celery worker + beat, Flower, Mailhog. All via docker-compose.
- **Out of scope**: Real-time vessel-level tracking, weather overlays, trade-flow analytics, mobile app, multi-tenant auth.
