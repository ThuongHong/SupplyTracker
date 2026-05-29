# PortWatch Insights Revamp — Design

Date: 2026-05-29
Branch: `feat/portwatch-insights`

## Goal

Refine the PortWatch feature set already built on this branch:

1. Fold Growth & Market Insights into the Overview page and remove the standalone tab.
2. Give port/chokepoint detail views a tabbed layout with a per-entity AI Summary.
3. Split the single tracked-state button into separate Re-sync and Untrack actions.
4. Replace the Risk & Forecast chart with a probability-hypothesis (z-score + anomaly probability) card on the throughput metric.
5. Fix the empty "Transit Mix — by vessel type" chart on chokepoint detail.

Non-goals: new data collectors, auth changes, re-theming, mobile redesign.

---

## 1. Merge Growth & Market into Overview

**Remove:**
- `frontend/src/views/MarketView.tsx`
- `frontend/src/__tests__/marketView.test.tsx` (move assertions into the Overview test)
- `/market` route branch in `frontend/src/router.ts`
- `market` lazy import + render branch in `frontend/src/App.tsx`
- `market` nav entry in `frontend/src/components/layout/NavBar.tsx`

**Keep:** `frontend/src/api/market.ts`, backend `build_market_insights`, `/api/v1/market/insights` route, `backend/app/services/market.py`.

**Overview changes (`frontend/src/views/OverviewView.tsx`):**
- Fetch market insights (reuse `fetchMarketInsights` + `getCachedMarket`, cache-then-refresh pattern from MarketView).
- New top "morning brief" header: section title plus `data.narrative` rendered prominently, with `{tracked_count} tracked ports · as of {as_of}` subline.
- Below the brief, in order: trade-growth KPI cards (port_calls / import_volume / export_volume), trade-volume area chart (import vs export), freight indices + bunker panel.
- Existing Overview content remains below the merged market block.
- The Overview window picker drives both existing Overview data and the market window (single shared `window` state, persisted to `localStorage` key `entity_window`, matching current MarketView behavior).

**Data flow:** unchanged on the backend. Overview now issues one extra GET to `/api/v1/market/insights?window=…`.

---

## 2. Tabbed detail view + per-entity AI Summary

### Frontend

Add a small tab strip to both `PortDetailView` and `ChokepointDetailView`:

- Tabs: **Overview · AI Summary · Events**.
- State: local `useState` for active tab; default `overview`. (No router change — keeps the existing single-route detail pages.)
- **Overview tab:** current stacked cards minus the Event Log (KPI strip, map, metric breakdown, anomaly card [see §4], vessel/transit mix, macro indices, narrative, insights).
- **AI Summary tab:** new component `EntitySummary` that fetches the summary endpoint and renders the narrative plus the z-score/anomaly stats it was grounded on.
- **Events tab:** the existing `EventLog`.

The header (back button, title, badges, window picker, sync/untrack buttons) stays above the tab strip on all tabs.

### Backend

New endpoint: `GET /api/v1/dashboard/{entity_type}/{entity_id}/summary?window=…`
→ `{ entity, window, narrative, stats: { z_score, p_value, anomaly_level, mean, std, latest } }`

- New function `build_entity_summary(session, entity_type, entity_id, window)` in `backend/app/services/dashboard.py` (or a new `summary.py` if dashboard.py grows past comfort — see Code Health).
- Reuses the throughput series already gathered for the dashboard and the anomaly stats from §4.
- Narrative via `app.llm.client.chat_completion`, mirroring `market._narrative`: an LLM summary of the entity's throughput trend, z-score, and risk, with a deterministic data-driven fallback when the LLM is unavailable. No invented numbers.

---

## 3. Separate Re-sync from Untrack

In both detail views, replace the single toggle button with:

- **Untracked state:** one button — "Sync data" (calls `syncPort` / `syncChokepoint`).
- **Tracked state:** two buttons —
  - "Re-sync" → `syncPort` / `syncChokepoint`, then `reloadKey++`.
  - "Untrack" → `untrackPort` / `untrackChokepoint` (already in `frontend/src/api/sync.ts`), then `reloadKey++` so `is_tracked` flips and the button set collapses to "Sync data".

Both gated behind `canSync` (`getSyncToken() !== null`), as today. Disable buttons while their action is in flight; track `syncing` and `untracking` separately.

---

## 4. Probability-hypothesis card (replaces Risk & Forecast)

Scope: **throughput metric only** (`port_calls` for ports, `transit_calls` for chokepoints).

### Backend

Add to `backend/app/services/dashboard.py` a helper `_anomaly_stats(series)`:

- Input: the throughput series (list of `{time, value}`).
- Compute trailing mean and sample std over the window (exclude the latest point from the baseline so the latest is tested against its history; require ≥ 8 baseline points, else return nulls).
- `z = (latest - mean) / std` (std > 0; else null).
- `p_value` = two-sided tail probability under the standard normal: `p = 2 * (1 - Φ(|z|))`, using `math.erf` (`Φ(x) = 0.5 * (1 + erf(x / √2))`). No SciPy dependency.
- `anomaly_level`: `high` if `|z| ≥ 2.5`, `elevated` if `|z| ≥ 1.5`, else `low`.
- Return `{ z_score, p_value, anomaly_level, mean, std, latest, baseline_n }` (rounded sensibly).

Add an `anomaly` block to both dashboard payloads' `charts`/`stats` (place under `stats` is cleaner; add fields to `DashboardStats` schema, all optional). Include the `±2σ` band bounds (`mean ± 2*std`) so the frontend can overlay them on the throughput series.

### Frontend

New `frontend/src/components/charts/AnomalyCard.tsx`:

- Props: throughput series + anomaly stats.
- Renders: the throughput area chart with a shaded ±2σ band, plus a stat row — z-score, p-value (e.g. `p = 0.012`), and an "Anomaly likelihood" badge colored by `anomaly_level` (low = neutral, elevated = amber, high = red).
- Empty/insufficient-data state when stats are null ("Not enough history for a probability estimate").

Replace the `<Card title="Risk & Forecast">` block in `PortDetailView` and the equivalent in `ChokepointDetailView` with `<Card title="Throughput anomaly (z-score)"><AnomalyCard … /></Card>`.

`RiskForecastChart.tsx` and the `forecast`/`risk_trend` payload fields are removed only if no longer referenced anywhere (grep first; Overview does not use RiskForecastChart per current code). If still referenced, leave the payload fields and delete only the detail-view usage.

---

## 5. Fix empty Transit Mix

**Root cause (confirmed against the running Postgres):** per-category transit metrics (`transit_container`, `transit_dry_bulk`, `transit_general_cargo`, `transit_roro`, `transit_tanker`) exist for only 2 chokepoints (`strait_of_dover`, `strait_of_hormuz`) and under slug-form `entity_id`s. Most chokepoints have only `transit_calls`. The DB also carries stale Title-Case `entity_id`s (e.g. `Suez Canal`) from an older seed generation that the slug-keyed dashboard query ignores. `seed_dev.py` lists `transit_container`/`transit_tanker` but the current DB predates that, so the data is stale/partial.

**Fix:**
- Extend `_CHOKEPOINT_METRICS` in `seed_dev.py` to cover all five category metrics (`transit_container`, `transit_dry_bulk`, `transit_general_cargo`, `transit_roro`, `transit_tanker`) so a seeded chokepoint renders a full mix.
- Re-seed cleanly (the seed already keys chokepoint metrics by slug via `_chokepoint_entity_id`), removing the stale Title-Case rows. Confirm via a Postgres query that every seeded chokepoint has all five category metrics under its slug id within the default window.
- Improve `VesselMixChart` empty state copy to "No vessel-type breakdown yet — re-sync this chokepoint" so a genuinely unsynced entity guides the user.

No collector code change expected — `_fetch_chokepoints` already requests `n_container`/`n_dry_bulk`/… and emits under the slug id; this is verified by the dover/hormuz rows. If a post-fix live sync of another chokepoint still yields no category rows, escalate to a field-name audit of the ArcGIS chokepoint layer (out of scope unless that surfaces).

---

## Code Health

- `OverviewView.tsx` is already ~19 KB; folding market in will grow it. Extract the merged market block into a small `MarketBrief` component (in `components/` or a local section) rather than inlining, keeping the view readable.
- If `dashboard.py` grows uncomfortable with `build_entity_summary` + `_anomaly_stats`, split the summary builder into `backend/app/services/summary.py` importing the anomaly helper. Decide during implementation based on file size.

## Testing

- **Backend:** unit tests for `_anomaly_stats` (insufficient data → nulls; known series → expected z and p within tolerance; flat series std=0 → null). Test `build_entity_summary` returns a fallback narrative when the LLM is stubbed/unavailable and includes the stats. Test the new summary route (auth not required for GET; mirror dashboard route tests).
- **Frontend:** Overview test asserts the morning-brief narrative + trade KPIs render (absorbed from the deleted marketView test). New tests: detail view tab switching shows the right panel; tracked state shows Re-sync + Untrack, untracked shows Sync data; `AnomalyCard` renders z/p/badge and the insufficient-data state.
- Re-seed and manually confirm a chokepoint detail Transit Mix renders all five series.

## Out of scope

ArcGIS field-name remediation, removing the backend forecast computation pipeline, auth/permission changes, new collectors.
