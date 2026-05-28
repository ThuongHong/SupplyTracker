## ADDED Requirements

### Requirement: Ports tab uses editorial table layout
The Ports tab SHALL render a `section__head` with double-rule title "Ports — global terminals" and a `dtable` table replacing the current card grid. Columns: Port (name + country subtext), Severity badge, Risk score (mono), Congestion bar cell, Status dot. The table SHALL preserve existing search and severity filter functionality, restyled as editorial filter strips above the table.

#### Scenario: Ports table renders with editorial styling
- **WHEN** user navigates to the Ports tab
- **THEN** ports appear in a full-width table with `dtable` editorial styling (no cards)

#### Scenario: Search filter works
- **WHEN** user types in the search input
- **THEN** table rows filter to matching ports by name or country

#### Scenario: Severity filter works
- **WHEN** user selects a severity filter pill
- **THEN** table rows filter to ports of that severity

### Requirement: Ports table shows tracked/pinned ports first
Tracked (starred) ports SHALL appear at the top of the table with a filled star icon. Untracked ports appear below. The star toggle SHALL work inline in the table row.

#### Scenario: Tracked ports sort to top
- **WHEN** a port is tracked
- **THEN** it appears before untracked ports in the table list

#### Scenario: Star toggle in table row
- **WHEN** user clicks the star in a port row
- **THEN** the port is added/removed from tracked list without page reload

### Requirement: Port row click navigates to detail
Clicking any row in the ports table SHALL navigate to `#/ports/<id>`.

#### Scenario: Row click navigates
- **WHEN** user clicks a port row
- **THEN** router navigates to `#/ports/<id>` for that port
