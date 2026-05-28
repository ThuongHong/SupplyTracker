## ADDED Requirements

### Requirement: Chokepoints tab uses editorial table layout
The Chokepoints tab SHALL render a `section__head` with double-rule title "Chokepoints — global arteries" and a `dtable` table. Columns: Chokepoint name + region subtext, Severity badge (using `SeverityBadge`), Risk score (mono), Status dot, Transit time (mono), Delta vs baseline (colored mono: positive green / negative red), Last updated. The existing search and severity filter functionality SHALL be preserved.

#### Scenario: Chokepoints table renders with editorial styling
- **WHEN** user navigates to the Chokepoints tab
- **THEN** chokepoints appear in a full-width `dtable` table with editorial styling

#### Scenario: Status dot color matches severity
- **WHEN** a chokepoint has critical or high severity
- **THEN** status dot appears in `var(--negative)` color

#### Scenario: Delta column shows directional color
- **WHEN** transit time delta is positive (worse)
- **THEN** delta cell uses `var(--negative)` color; if negative (better), uses `var(--positive)`

### Requirement: Chokepoint row click navigates to detail
Clicking any row in the chokepoints table SHALL navigate to `#/chokepoints/<id>`.

#### Scenario: Row click navigates
- **WHEN** user clicks a chokepoint row
- **THEN** router navigates to `#/chokepoints/<id>` for that chokepoint

### Requirement: Chokepoints filter strip
The Chokepoints tab SHALL render a filter strip above the table with a text search input and severity filter pills, styled with editorial tokens (Inter UI, `var(--card)` background, `var(--rule-thin)` borders).

#### Scenario: Search filters chokepoints
- **WHEN** user types in the search input
- **THEN** table rows filter to matching chokepoints by name or region

#### Scenario: Severity filter pills work
- **WHEN** user selects a severity filter
- **THEN** table shows only chokepoints of that severity
