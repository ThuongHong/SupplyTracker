## ADDED Requirements

### Requirement: SupplyChainWatch shell preserved
The system SHALL reuse the SupplyChainWatch frontend shell: hash-based router, collapsible Sidebar (auto-collapses below 760px), Header with dark/light theme toggle persisted on `documentElement`, Suspense fallback for lazy pages, and a global ChatbotWidget overlay.

#### Scenario: Hash routing
- **WHEN** the user navigates to `#/ports`
- **THEN** the Ports tab renders without a full page reload and the sidebar marks Ports active

#### Scenario: Mobile sidebar
- **WHEN** the viewport is resized to 600px wide
- **THEN** the sidebar auto-closes and a hamburger toggle is exposed

### Requirement: Three top-level tabs
The system SHALL ship exactly three top-level tabs mounted at the routes below; no other top-level pages exist.

| Route | Tab |
|-------|-----|
| `#/overview` (default) | Overview |
| `#/ports` | Ports |
| `#/chokepoints` | Chokepoints |

Per-entity detail views render inside their parent tab as nested routes (`#/ports/{id}`, `#/chokepoints/{id}`), not as separate top-level pages. Macro indices, insights feed, analytics drill-downs, and the entity map are surfaced as panels inside Overview or as sections inside the entity detail views — they are not separate tabs.

#### Scenario: Default route
- **WHEN** the app loads with no hash
- **THEN** the URL is normalized to `#/overview` and the Overview tab renders

#### Scenario: Legacy route redirects
- **WHEN** the user navigates to `#/dashboard`, `#/indices`, `#/map`, `#/analytics`, `#/insights`, or `#/vessels`
- **THEN** the router redirects to `#/overview`

#### Scenario: Entity detail nested route
- **WHEN** the user clicks port `USLAX` from the Ports tab
- **THEN** the URL becomes `#/ports/USLAX`, the Ports tab stays active in the sidebar, and the detail view renders inside the Ports tab area (Back button returns to `#/ports`)

### Requirement: Overview tab layout
The Overview tab SHALL render, in this order: a freshness banner reflecting `DataCoverage`, a KPI strip (today's chokepoint transits, count of `high`+`critical` entities, top mover by z-score), a 50-day chokepoint strip chart with per-category stacking and a chokepoint selector, an LLM-generated Decision Brief panel, a compact macro indices strip (FBX, WCI, Brent, etc. as sparklines with deltas), a top-5 ports-by-severity list, and a reverse-chronological Insights feed (last 20, with `attention_level` filter).

#### Scenario: Stale data banner
- **WHEN** `DataCoverage.freshness_status` for PortWatch is `"stale"`
- **THEN** the freshness banner renders in amber with the source name and last-observed date

#### Scenario: Chokepoint switcher
- **WHEN** the user selects "Strait of Hormuz" from the chokepoint selector
- **THEN** the 50-day strip chart updates to Hormuz breakdowns without remounting other panels

#### Scenario: Macro strip click-through
- **WHEN** the user clicks the FBX sparkline in the macro strip
- **THEN** a modal/drawer opens with the full FBX timeseries and 7d/30d delta badges

### Requirement: Ports tab — selection and list
The Ports tab SHALL render every PortWatch port and let the user mark which ports to "track". Tracked ports are pinned to the top of the list with a star indicator and persist per browser via localStorage. The list supports text search by name/country/locode, region filter, and severity filter.

#### Scenario: Track a port
- **WHEN** the user clicks the star icon next to "Port of Rotterdam (NLRTM)"
- **THEN** NLRTM is added to the tracked set in localStorage, the row pins to the top with a filled star, and the Overview tab's top-5 list prefers tracked ports when ties exist

#### Scenario: Untrack a port
- **WHEN** the user clicks a filled star
- **THEN** the port is removed from the tracked set and unpins from the top

#### Scenario: Search by name
- **WHEN** the user types "rotter" in the search box
- **THEN** the list filters to ports whose `name` or `locode` matches case-insensitively

#### Scenario: Region + severity filter
- **WHEN** the user selects region=`Europe` and severity=`high`
- **THEN** the list shows only European ports with current severity `high`

### Requirement: Ports tab — entity detail view (Hormuztracking-style)
Clicking a port row SHALL open the port detail view at `#/ports/{id}` rendering, in this order: header (name, country, locode, current severity badge, latest risk score, last-observed-at, track/untrack button), a MapLibre GL map centered on the port's `geom` with the port shown as a circle sized by 7-day mean throughput and colored by severity (no other entities on this map), a KPI strip (today's port_calls, 7d mean, 30d mean, z-score), a 50-day stacked strip chart broken down by PortWatch vessel/cargo category, a metric drill-down section (metric picker → timeseries with 30/90-day baseline bands + z-score strip + drivers bar chart pulled from the latest `RiskFeatureSnapshot.driver_metadata`), a 14-day forecast panel (with bands, or an "insufficient history" badge when gated), the LLM narrative from the latest `Insight` for this port, and a chronological event log from `RiskStoryEvent`.

#### Scenario: Open port detail
- **WHEN** the user navigates to `#/ports/USLAX`
- **THEN** all sections (header, map, KPIs, 50-day strip, metric drill-down, forecast, narrative, event log) render and the map is centered on the USLAX `geom`

#### Scenario: Insufficient forecast
- **WHEN** the port has fewer than 60 days of history
- **THEN** the forecast panel shows an "Insufficient history" badge with the reason, not a chart

#### Scenario: Metric switcher in drill-down
- **WHEN** the user picks metric `dwell_hours` in the drill-down
- **THEN** the timeseries, baseline bands, z-score strip, and drivers chart all re-bind to `dwell_hours` without leaving the page

### Requirement: Chokepoints tab — selection, list, and detail
The Chokepoints tab SHALL mirror the Ports tab structure: a list of every PortWatch chokepoint with track/untrack stars (localStorage-persisted), search and severity filters, and a click-through detail view at `#/chokepoints/{id}` with the same section order as the port detail view, substituting chokepoint-appropriate metrics (`transit_calls`, `median_speed`, `vessel_count` where available) and using the chokepoint `geom` for the map.

#### Scenario: Track a chokepoint
- **WHEN** the user stars "Strait of Hormuz"
- **THEN** Hormuz pins to the top of the chokepoints list, persists across reloads, and becomes the default selection in the Overview chokepoint switcher

#### Scenario: Open chokepoint detail
- **WHEN** the user navigates to `#/chokepoints/hormuz`
- **THEN** the chokepoint detail view renders the same section layout as a port detail with `transit_calls` as the primary KPI and a 50-day stacked breakdown by vessel/cargo category

### Requirement: Theme and accessibility
The system SHALL persist the dark/light theme on `documentElement` and SHALL meet WCAG AA color contrast for both themes.

#### Scenario: Theme persistence
- **WHEN** the user toggles to dark theme and reloads
- **THEN** the app loads in dark theme

### Requirement: Lazy-loading boundaries
Entity detail views (Ports and Chokepoints detail), including their MapLibre + deck.gl map and recharts components, SHALL be code-split and lazy-loaded with a Suspense fallback that does not shift layout.

#### Scenario: First navigation to a detail view
- **WHEN** the user opens `#/ports/USLAX` for the first time in a session
- **THEN** a non-blocking fallback renders for at most the load duration, then the detail mounts in the same container without layout jump
