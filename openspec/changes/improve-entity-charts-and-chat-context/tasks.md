## 1. Backend — dashboard endpoint

- [x] 1.1 Add `DashboardResponse` Pydantic schema in `backend/app/schemas/dashboard.py` covering `entity`, `window`, `charts.*`, `stats`, `disruptions`.
- [x] 1.2 Create `backend/app/services/dashboard.py` with `build_port_dashboard(session, port_id, window)` and `build_chokepoint_dashboard(session, cp_id, window)` that read `port_congestion`, `chokepoint_status`, `port_watch_metric`, `port_risk_score`, `chokepoint_risk_score`, `entity_risk_forecast`, `freight_index`, `bunker_price`, `disruption_propagation`.
- [x] 1.3 Create route `GET /entities/{entity_type}/{entity_id}/dashboard` in a new `backend/app/api/routes/dashboard.py`; validate entity_type and window, 404 on unknown entity, set `Cache-Control: public, max-age=300`.
- [x] 1.4 Register router in `backend/app/api/router.py`.
- [x] 1.5 Pick the default `Throughput` metric_name by querying `port_watch_metric` populated densities at startup (fallback: `vessels_in_port`).

## 2. Backend — chat context rewrite

- [x] 2.1 Refactor `_fetch_entity_context` in `backend/app/llm/chat.py` to call into a new helper `app/llm/grounding.py::build_entity_grounding(session, entity)` returning a string block per entity.
- [x] 2.2 In `build_entity_grounding`, compute latest + 30d mean/max for risk; latest vessel count / dwell hours; latest forecast point + lo/hi; FBX/WCI latest + 7d % change; bunker latest; active disruption count.
- [x] 2.3 Add per-entity 600-token cap and total 2500-token cap (use `tiktoken` if available, else heuristic word-count).
- [x] 2.4 Normalise `entity_context` input: accept both `dict` and `list[dict]`; emit a deprecation log when single-dict is received.

## 3. Backend — tests

- [x] 3.1 Pytest fixture: seed a port with 30d of `port_congestion`, `port_watch_metric`, `port_risk_score`, `entity_risk_forecast`, plus FBX/WCI rows.
- [x] 3.2 Test `GET /entities/port/{id}/dashboard?window=30d` returns expected non-empty arrays and `Cache-Control` header.
- [x] 3.3 Test chokepoint dashboard; assert `disruptions` populated when `disruption_propagation` rows exist.
- [x] 3.4 Test 404 on unknown entity and 422 on invalid window.
- [x] 3.5 Snapshot test `build_entity_grounding` output for a fixed seeded port and chokepoint.
- [x] 3.6 Test legacy single-object `entity_context` is accepted by the chat endpoint.

## 4. Frontend — API client

- [x] 4.1 Add `DashboardResponse` (with `EntityDashboardCharts`, `EntityDashboardStats`) types in `frontend/src/api/types.ts`.
- [x] 4.2 Add `fetchEntityDashboard(entityType, entityId, window)` in `frontend/src/api/dashboard.ts`.
- [x] 4.3 Update `ChatRequest.entity_context` type to `Array<{ entity_type; entity_id; entity_name? }>`.

## 5. Frontend — chart components

- [x] 5.1 `frontend/src/components/charts/VesselMixChart.tsx` (stacked area: anchored/moored/underway).
- [x] 5.2 `frontend/src/components/charts/DwellTrendChart.tsx`.
- [x] 5.3 `frontend/src/components/charts/RiskForecastChart.tsx` (history + forecast + band + "now" separator).
- [x] 5.4 `frontend/src/components/charts/VesselCountChart.tsx` & `MedianSpeedChart.tsx` for chokepoints.
- [x] 5.5 `frontend/src/components/charts/IndicesPanel.tsx` (FBX & WCI rebased to 100, plus bunker sparkline; collapsible with `localStorage` persistence).
- [x] 5.6 `frontend/src/components/ui/WindowPicker.tsx` (7d/30d/90d, persists choice in `localStorage`).
- [x] 5.7 Wire `<AskAIButton entity={…} chart={…} window={…} />` on each chart card that calls `openChatWithPrompt(prompt, entityContext)`.

## 6. Frontend — view integration

- [x] 6.1 Refactor `PortDetailView.tsx` to fetch the dashboard bundle once and pass slices to the chart components; keep existing throughput chart but source it from `charts.throughput`.
- [x] 6.2 Refactor `ChokepointDetailView.tsx` similarly; keep `BreakdownChart` for the 50-day vessel-category breakdown (separate endpoint as today).
- [x] 6.3 Mount `<WindowPicker />` in the detail-page header; pipe its value to the bundle fetch.

## 7. Frontend — chatbot wiring

- [x] 7.1 Update `deriveEntityContext` in `ChatbotWidget.tsx` to return an array (single-element or empty).
- [x] 7.2 Add `openChatWithPrompt(prompt: string, entityContext: …)` exported from the chatbot module (and a small event bus or context provider) so `AskAIButton` can pre-fill the textarea and trigger open.
- [x] 7.3 Verify existing send path still works when `entity_context` is an empty array.

## 8. Frontend — tests

- [x] 8.1 Vitest for `fetchEntityDashboard` URL + parsing.
- [x] 8.2 Vitest for `WindowPicker` selection + persistence.
- [x] 8.3 Vitest for `RiskForecastChart` band rendering with a fixture.
- [x] 8.4 Vitest for `ChatbotWidget`: `entity_context` is an array; `AskAIButton` opens chatbot with prefilled prompt and context.

## 9. Verification

- [x] 9.1 `make test` — backend + frontend green.
- [x] 9.2 `make lint` — clean.
- [x] 9.3 `make up && make bootstrap`; open a port and a chokepoint detail page; visually verify all new charts populate and the window picker refetches.
- [x] 9.4 Open the chatbot from a port detail page; ask "Why is risk elevated?"; verify the streamed reply references concrete numbers (e.g., dwell hours, FBX move) from the on-screen window.
- [x] 9.5 Click "Ask AI" on the dwell chart; verify the textarea is pre-filled and the entity context is sent.

## 10. Cleanup

- [x] 10.1 Add a TODO note for next change: remove legacy single-object `entity_context` branch in `_fetch_entity_context`.
- [x] 10.2 Update `README.md` "Common make targets" if any new make target is introduced (probably none).
