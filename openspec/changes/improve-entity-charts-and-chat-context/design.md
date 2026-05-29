## Context

Current detail-view charting:
- `PortDetailView.tsx` builds one `AreaChart` from `/ports/{id}/metrics` plus a small forecast `AreaChart`.
- `ChokepointDetailView.tsx` adds a 50-day stacked breakdown `AreaChart` and the same forecast chart.
- The shared component is `frontend/src/components/ui/AreaChart.tsx`.

Available source data already in the DB:
- `port_congestion` — `anchored_count`, `moored_count`, `underway_count`, `total_in_area`, `avg_dwell_hours`, `median_speed`.
- `chokepoint_status` — `vessel_count`, `median_speed`, `risk_score`.
- `port_watch_metric` — arbitrary `(metric_name, observed_at, value)` per entity (used by current chart).
- `port_risk_score`, `chokepoint_risk_score`, `entity_risk_forecast` — risk + forecast trend.
- `freight_index` (FBX/WCI), `bunker_price` — macro context.
- `disruption_propagation` — chokepoint → downstream port impact rows.

Chatbot backend in `app/llm/chat.py`:
- `_fetch_entity_context` reads only the latest `PortRiskScore`/`ChokepointRiskScore` + last 3 `RiskStoryEvent` rows.
- `ChatRequest.entity_context` typed as `list[dict[str, Any]]`. The frontend (`ChatbotWidget.tsx::deriveEntityContext`) returns a single object — type-mismatch hidden by `Any`.

## Goals / Non-Goals

**Goals:**
- Give operators a fuller picture: vessel mix, dwell, throughput, risk-vs-forecast, macro indices.
- Configurable time window (7d / 30d / 90d) shared across charts on the page.
- Make the chatbot grounded in what the user can see — when on a port/chokepoint tab, the LLM gets a structured snapshot of that entity's recent stats and active disruptions.
- One-shot data fetch for the page; charts share a single response payload.
- Fix the frontend/backend type mismatch on `entity_context`.

**Non-Goals:**
- Map-based or 3D visualisations.
- Custom user-saved chart layouts.
- Per-chart streaming updates (next page load is fine).
- Multi-entity comparison view (separate change).
- Pushing chart data into the LLM as raw arrays — only summary stats, to keep token cost low.

## Decisions

### 1. New endpoint: `GET /entities/{type}/{id}/dashboard?window=7d|30d|90d`

One endpoint that returns the full chart bundle:

```jsonc
{
  "entity": { "type": "port", "id": "SGSIN", "name": "Singapore" },
  "window": "30d",
  "charts": {
    "vessel_mix":   [ { "time": "...", "anchored": 12, "moored": 30, "underway": 5 }, ... ],
    "dwell_hours":  [ { "time": "...", "value": 28.4 }, ... ],
    "throughput":   [ { "time": "...", "value": 1234 }, ... ],         // from port_watch_metric (e.g., portcalls)
    "risk_trend":   [ { "time": "...", "value": 0.71 }, ... ],
    "forecast":     [ { "time": "...", "value": 0.74, "lo": 0.65, "hi": 0.80 }, ... ],
    "indices":      [ { "time": "...", "fbx": 1234, "wci": 2345 }, ... ],
    "bunker":       [ { "time": "...", "value": 612.5 }, ... ]
  },
  "stats": {
    "risk_latest":     0.71,
    "risk_30d_mean":   0.62,
    "risk_30d_max":    0.83,
    "dwell_latest":    28.4,
    "vessel_count_latest": 47,
    "fbx_pct_7d":     -3.4
  },
  "disruptions": [ /* DisruptionPropagation rows where target_entity_id = id */ ]
}
```

**Why bundled:** charts on one page share a window. Five endpoints means five network round-trips and harder cache invalidation. One bundle is simpler and the payload is small (≤ ~30KB for 90d).

**Alternative considered:** Continue with per-chart endpoints (`/metrics`, `/breakdown`, `/forecast`). Rejected — would require 4+ parallel fetches per page render.

### 2. Window picker

Single `<WindowPicker value="30d" onChange=…/>` component drives the bundle fetch. Window options: `7d | 30d | 90d`. Caller passes the choice to the endpoint as a query string. Default 30d.

### 3. Chart components

- `VesselMixChart` — stacked area of anchored / moored / underway counts (uses existing `AreaChart` stacked mode or a thin wrapper if needed).
- `DwellTrendChart` — line/area of `avg_dwell_hours`.
- `RiskForecastChart` — risk history line + forecast line + lo/hi band. Vertical separator at "now".
- `IndicesPanel` — two-line chart of FBX & WCI (rebased to 100 at window start) + a small bunker sparkline.
- Ports get: VesselMix, Dwell, Throughput (from `port_watch_metric` filtered by sensible defaults), RiskForecast, IndicesPanel.
- Chokepoints get: VesselCount, MedianSpeed, RiskForecast, existing breakdown, IndicesPanel.

### 4. Chat context enrichment

Rewrite `_fetch_entity_context` to:

1. Normalise input: accept the historical single-object shape AND the new array shape (for backwards compatibility during rollout).
2. For each entity, build a compact YAML-ish block:

```
Entity: port "Singapore" (SGSIN)
  Risk: latest=0.71  30d_mean=0.62  30d_max=0.83  severity=elevated
  Vessel count latest: 47  (30d mean 41)
  Avg dwell hours latest: 28.4  (30d mean 24.1, 30d max 36.0)
  Forecast (next 7d): 0.74 (band 0.65–0.80)  drivers: ["congestion","strike"]
  Indices: FBX 1234 (-3.4% 7d), WCI 2345 (+1.1% 7d)
  Active disruptions: 2 (sources: Strait of Hormuz)
  Recent events:
    - [high] anomaly at 2026-05-27T...: <narrative>
```

3. Token guard: cap each entity's block ~600 tokens; cap total context ~2500 tokens.

**Why summary stats not raw series:** raw arrays blow the context window. The LLM does not need every datapoint — it needs the shape (latest vs mean, direction, magnitude).

**Alternative considered:** Send the chart JSON straight through. Rejected — token waste; LLM tends to repeat numbers verbatim.

### 5. Frontend `entity_context` array fix

Change `ChatRequest.entity_context` to `Array<{ entity_type; entity_id; entity_name? }>`. `deriveEntityContext` returns an array (single-element today, future-proof for multi-entity selection). Backend keeps tolerating the legacy single-object shape for one release.

### 6. "Ask AI about this" affordance

Each chart card has a small button that opens the chatbot with a templated question, e.g., "Why has risk for {entity_name} moved over the last {window}?" — the chatbot then runs with the full entity context.

**Alternative considered:** Auto-stream a summary into the chat on hover. Rejected — too invasive and burns LLM credit.

### 7. Caching

`Cache-Control: public, max-age=300` on the dashboard endpoint. PortWatch refreshes hourly — 5-minute cache is safe and lowers DB load when switching windows back and forth.

## Risks / Trade-offs

- **Endpoint payload bloat** for 90d window with many metrics → mitigated by including only the curated chart families above, not every `port_watch_metric` row.
- **LLM prompt drift** if context format changes silently → mitigated by snapshot test of `_fetch_entity_context` output for a fixed entity.
- **Type-mismatch transition** if old frontend hits new backend or vice-versa → backend accepts both shapes for one release window; frontend ships array shape; remove dual support next change.
- **Visual clutter** from 4–5 charts per page → use a 2-column grid + collapsible "Macro context" section; default collapsed for chokepoints.
- **Forecast band rendering** depends on `entity_risk_forecast.predictions` shape — verify it carries `lo`/`hi` (or compute fallback band from `confidence`).

## Migration Plan

1. Ship backend endpoint and chat-context rewrite behind no flag — both are additive.
2. Ship frontend chart components and chatbot type fix together; old frontend continues to work against new backend.
3. After one release, drop the single-object compatibility branch in `_fetch_entity_context`.
4. Rollback = revert; no DB changes.

## Open Questions

- Which `port_watch_metric.metric_name` should the Throughput chart default to (`portcalls`, `vessels_in_port`, etc.)? Check the seeded data; pick the most populated.
- Should the IndicesPanel filter FBX/WCI by region (Asia vs Europe lane)? Possibly v2; ship global indices first.
- Per-port bunker selection — show only the port's own bunker series if `bunker_price.port_code == entity.id`, else show a regional average.
