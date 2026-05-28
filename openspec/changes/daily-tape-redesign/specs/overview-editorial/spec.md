## ADDED Requirements

### Requirement: Morning Brief hero section
The Overview tab SHALL render a two-column editorial hero at the top: left column contains a "Morning Brief" badge/kicker, large Newsreader serif headline summarizing current market conditions (generated from real insight data or a static template), italic subheadline, byline, and two-column body copy. Right column is an "evidence" side panel showing 4–6 key metrics (BDI, vessels at sea, port congestion, open anomalies) with mono figures and delta labels, separated by a left border.

#### Scenario: Brief section renders on Overview load
- **WHEN** user navigates to Overview tab
- **THEN** a Morning Brief section appears with a headline, subheadline, and evidence column

#### Scenario: Evidence column shows real data
- **WHEN** Overview data loads from the API
- **THEN** evidence rows display live values from the indices and insights endpoints

### Requirement: Markets / Indices panel
The Overview tab SHALL render a Markets section below the brief with the existing area chart for the selected index (BDI/FBX/WCI/IFO) and a side watchlist of mini-quotes. Tab switching and 7D/30D/90D range pills from the existing IndicesPanel logic SHALL be preserved, restyled with Daily Tape tokens (tabular mono values, `section__head` double-rule, range pill buttons).

#### Scenario: Index tabs render with editorial styling
- **WHEN** user views the Markets section
- **THEN** BDI/FBX/WCI/IFO tabs appear with mono values and delta colors using `var(--positive)`/`var(--negative)`

#### Scenario: Range pills switch chart data
- **WHEN** user clicks a range pill (7D/30D/90D)
- **THEN** the area chart updates to show the selected time range

### Requirement: Arteries / Chokepoint atlas section
The Overview tab SHALL render an "Arteries" section below Markets with a simplified chokepoint status table (name, status dot, transit time, delta vs baseline). This uses real data from `fetchChokepoints()`.

#### Scenario: Arteries section shows chokepoint status
- **WHEN** Overview loads chokepoint data
- **THEN** a table of chokepoints appears with status dots (`var(--positive)`/`var(--caution)`/`var(--negative)`) and transit time

### Requirement: Ports digest table on Overview
The Overview tab SHALL render a "Ports" section showing the top 8 ports by risk score with editorial `dtable` styling: port name + country subtext, vessels count, dwell time, deviation bar cell, congestion status. Clicking a row SHALL navigate to that port's detail page.

#### Scenario: Ports digest shows top ports
- **WHEN** Overview loads port data
- **THEN** a table shows up to 8 ports with bar-cell congestion visualization

#### Scenario: Row click navigates to port detail
- **WHEN** user clicks a port row
- **THEN** router navigates to `#/ports/<id>`

### Requirement: Side rail with Alerts and Insights
The Overview tab body SHALL use a two-column layout (main 2.3fr + siderail 1fr). The siderail SHALL contain an Alerts section (last 24h anomalies from existing insights API) and an Insights/Story card. Each alert SHALL show a severity dot, kicker label, editorial serif text, and metadata.

#### Scenario: Alerts section shows recent anomalies
- **WHEN** Overview loads insights data
- **THEN** the siderail shows up to 5 most recent high/critical insights with severity-colored dots

#### Scenario: Empty state for no alerts
- **WHEN** no insights are returned
- **THEN** siderail shows a muted "No active alerts" message
