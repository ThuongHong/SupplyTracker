## ADDED Requirements

### Requirement: Catalog metadata ingest

The system SHALL ingest metadata (business id, name, country, location) for every PortWatch port and chokepoint from the ArcGIS master FeatureServers, without fetching any time-series metrics. Ports SHALL be keyed by a unique `portid`; chokepoints by a unique `chokepointid`. Re-running ingest SHALL be idempotent and SHALL preserve each entity's `is_tracked` flag.

#### Scenario: Full port catalog ingested
- **WHEN** the catalog ingest runs against `PortWatch_ports_database`
- **THEN** every port feature is upserted into `ports` with its `portid`, `name`, `country`, and a POINT geometry from `lat`/`lon`
- **AND** no rows are written to `port_watch_metric`

#### Scenario: Chokepoint geometry synthesized from point
- **WHEN** a chokepoint master feature provides only `lat`/`lon`
- **THEN** the system stores a synthesized circular POLYGON geometry for that chokepoint

#### Scenario: Paging beyond the ArcGIS record limit
- **WHEN** the master layer returns more rows than the server `maxRecordCount` (1000)
- **THEN** the ingest pages with `resultOffset` until all features are retrieved

#### Scenario: Re-sync preserves tracking
- **WHEN** an entity already has `is_tracked=true` and the catalog ingest runs again
- **THEN** the entity's metadata is updated and `is_tracked` remains `true`

### Requirement: Browseable, searchable entity lists

The list endpoints `GET /ports` and `GET /chokepoints` SHALL support pagination and SHALL accept a `q` parameter (case-insensitive match on name and country) and a `tracked` boolean parameter. Results SHALL indicate whether more pages exist.

#### Scenario: Search by name
- **WHEN** a client requests `GET /ports?q=rotterdam`
- **THEN** the response contains only ports whose name or country matches "rotterdam" (case-insensitive)

#### Scenario: Filter tracked entities
- **WHEN** a client requests `GET /ports?tracked=true`
- **THEN** the response contains only ports with `is_tracked=true`

#### Scenario: Browse untracked catalog page
- **WHEN** a client requests `GET /ports?tracked=false&limit=50&offset=0`
- **THEN** the response returns at most 50 untracked ports and a flag indicating whether more pages remain

### Requirement: Tracked and Browse-all UI tabs

The ports and chokepoints views SHALL present a "Tracked" tab and a "Browse all" tab. The Browse-all tab SHALL load entities page by page (lazy) and SHALL provide a search input. Each row SHALL expose a Sync action (untracked entities) and an Untrack action (tracked entities).

#### Scenario: Browse-all lazy loads pages
- **WHEN** the user opens the Browse-all tab and scrolls or advances pages
- **THEN** additional catalog pages are fetched on demand rather than all at once

#### Scenario: Tracked tab shows only followed entities
- **WHEN** the user opens the Tracked tab
- **THEN** only entities with `is_tracked=true` are listed, each with an Untrack action
