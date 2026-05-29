## Why

Port and chokepoint detail views currently show only one chart family each — a single `AreaChart` of one PortWatch metric and (for chokepoints) a 50-day vessel-category breakdown. Operators want richer at-a-glance signals: dwell time, vessel mix, throughput vs. forecast, congestion trend over multiple windows, and the macro context (freight indices, bunker price) that matters for that entity. Separately, the chatbot already accepts `entity_context`, but the frontend sends a single object while the backend expects `list[dict]`, and the context only includes the latest risk score + 3 events — not the actual chart data the user is staring at. So when a user on the Hormuz tab asks "why is risk elevated?", the LLM cannot see the spike it shows on screen.

## What Changes

- Add 3 new charts per port detail: (1) vessel-status stacked area (anchored / moored / underway from `port_congestion`), (2) average dwell-hours trend, (3) risk-score trend with the 7-day forecast overlay.
- Add 3 new charts per chokepoint detail: (1) vessel count trend, (2) median transit speed trend, (3) risk + forecast overlay (same pattern as ports). Keep existing breakdown chart.
- Add an "Indices" panel showing the relevant freight index (FBX/WCI) and bunker price for the region as a small multi-line chart.
- Allow user to toggle chart window: 7d / 30d / 90d. Default 30d.
- **BREAKING (internal)**: change `ChatRequest.entity_context` in the frontend from a single object to an array (matches backend contract).
- Extend `_fetch_entity_context` in `app/llm/chat.py` to also pull (a) latest forecast points, (b) latest 30d trend stats (mean / min / max / latest) for the entity's key metrics, (c) relevant freight index value + 7d change, and (d) any active disruption propagation rows.
- Add a hover-tooltip "Ask AI about this" affordance on each chart that pre-fills the chatbot with a question referencing the active entity and metric window.

## Capabilities

### New Capabilities
- `entity-charts`: Multi-chart visualization panel on port/chokepoint detail views with selectable time window.
- `chat-entity-context`: Enriched chatbot grounding that ingests the entity, its current chart data, forecast, indices, and active disruptions into the LLM prompt.

### Modified Capabilities
<!-- No existing specs to modify; `openspec/specs/` is empty. The two new capabilities above stand alone. -->

## Impact

- **Backend**: small extensions to `app/api/routes/ports.py` and `app/api/routes/chokepoints.py` (or new `entity_charts.py` route module) to return aggregated chart bundles in one call; rewrite `app/llm/chat.py::_fetch_entity_context` to assemble a richer grounding payload.
- **Backend**: optional new endpoint `GET /entities/{type}/{id}/dashboard?window=30d` that returns the full chart bundle in one request to keep frontend chatty-ness down.
- **Frontend**: `PortDetailView.tsx`, `ChokepointDetailView.tsx`, and `ChatbotWidget.tsx` modified; new chart components (`VesselMixChart`, `DwellTrendChart`, `RiskForecastChart`, `IndicesPanel`); new shared `WindowPicker` (7d/30d/90d).
- **Frontend contract fix**: `frontend/src/api/types.ts::ChatRequest.entity_context` becomes `Array<{ entity_type, entity_id, entity_name? }>`; `deriveEntityContext` in `ChatbotWidget.tsx` returns an array.
- **Tests**: backend unit tests for context builder; frontend vitest for chart bundle parsing + chatbot context shape; e2e smoke that the LLM sees the chart data (assert prompt-build output).
- **No DB migration** — all data already exists.
