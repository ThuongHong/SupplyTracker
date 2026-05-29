## ADDED Requirements

### Requirement: System SHALL provide a bundled chart-data endpoint per entity

The backend SHALL expose `GET /entities/{entity_type}/{entity_id}/dashboard?window=7d|30d|90d` returning a single JSON payload covering all charts shown on that entity's detail page.

#### Scenario: Fetching a port dashboard

- **WHEN** a client calls `GET /entities/port/SGSIN/dashboard?window=30d`
- **THEN** the response is `200 OK` with `entity`, `window`, `charts` (containing `vessel_mix`, `dwell_hours`, `throughput`, `risk_trend`, `forecast`, `indices`, `bunker`), `stats` (latest + window aggregates), and `disruptions` (active rows targeting the entity)

#### Scenario: Fetching a chokepoint dashboard

- **WHEN** a client calls `GET /entities/chokepoint/hormuz/dashboard?window=7d`
- **THEN** the response includes `charts.vessel_count`, `charts.median_speed`, `charts.risk_trend`, `charts.forecast`, `charts.indices`, `charts.bunker`, and `disruptions` sourced from `disruption_propagation` where `source_entity_id = hormuz`

#### Scenario: Invalid window

- **WHEN** a client passes `window=180d`
- **THEN** the response is `422 Unprocessable Entity`

#### Scenario: Unknown entity

- **WHEN** a client passes an entity id that does not exist
- **THEN** the response is `404 Not Found`

#### Scenario: Caching

- **WHEN** any successful response is returned
- **THEN** `Cache-Control: public, max-age=300` is set

### Requirement: Port detail view SHALL render additional charts

The `PortDetailView` SHALL display, in addition to the existing portwatch metric chart, the following charts driven by the dashboard endpoint: vessel-status stacked area, average dwell-hours trend, and risk + 7-day forecast overlay.

#### Scenario: Charts populated from dashboard endpoint

- **WHEN** the page loads with a port that has data
- **THEN** the four charts (existing throughput + new vessel-mix, dwell, risk-forecast) render with non-empty series sourced from a single `/entities/port/{id}/dashboard?window=…` call

#### Scenario: Empty data fallback

- **WHEN** a chart series is empty for the selected window
- **THEN** that chart card shows an empty-state message instead of an empty plot, and the other charts continue to render

### Requirement: Chokepoint detail view SHALL render additional charts

The `ChokepointDetailView` SHALL display vessel-count trend, median-speed trend, and risk + 7-day forecast overlay alongside the existing 50-day breakdown chart.

#### Scenario: All chokepoint charts render

- **WHEN** the page loads with a chokepoint that has data
- **THEN** the breakdown chart plus vessel-count, median-speed, and risk-forecast charts are visible and populated from the dashboard endpoint

### Requirement: Detail views SHALL include a macro indices panel

Both port and chokepoint detail views SHALL include an "Indices" section that shows the FBX and WCI freight indices and a bunker price series for the entity window.

#### Scenario: Indices panel renders

- **WHEN** the page loads
- **THEN** an "Indices" panel shows FBX and WCI as two rebased-to-100 lines over the selected window, plus a bunker price sparkline

#### Scenario: Indices collapse

- **WHEN** the user clicks the indices section header
- **THEN** the panel collapses and remembers its collapsed state for that detail view in `localStorage`

### Requirement: Detail views SHALL provide a time-window picker shared by all charts

A single `WindowPicker` (options `7d`, `30d`, `90d`, default `30d`) SHALL drive every chart on the page through one dashboard fetch.

#### Scenario: Switching window refetches once

- **WHEN** the user selects `7d`
- **THEN** exactly one `GET /entities/{type}/{id}/dashboard?window=7d` request is made and all charts re-render from the new payload

#### Scenario: Window persists across navigation

- **WHEN** the user changes window then navigates to another port/chokepoint detail view
- **THEN** the new view opens with the same window selection

### Requirement: Each chart card SHALL provide an "Ask AI about this" action

Every chart card SHALL include a small button that opens the chatbot pre-filled with a question referencing the active entity and chart.

#### Scenario: Opening pre-filled chat

- **WHEN** the user clicks "Ask AI" on the dwell-hours chart of port "Singapore" with window=30d
- **THEN** the chatbot opens with the textarea pre-populated with "Why has Singapore's average dwell hours moved over the last 30 days?" and the entity context already attached
