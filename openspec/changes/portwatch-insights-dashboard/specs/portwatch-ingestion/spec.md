## ADDED Requirements

### Requirement: Scheduled PortWatch collection
The system SHALL run a Celery beat task at least once per day that fetches IMF PortWatch metrics for every active port and chokepoint entity and persists them into `PortWatchMetric` with an idempotent upsert keyed on `(observed_at, entity_type, entity_id, metric_name, source)`.

#### Scenario: Daily refresh succeeds
- **WHEN** the scheduled `collect_portwatch` task runs and PortWatch returns new daily rows
- **THEN** every returned row is upserted into `PortWatchMetric`, a `CollectionLog` row is written with `status="success"` and the row count, and `DataCoverage.latest_observed_at` for that `(source, entity)` is advanced

#### Scenario: Re-running on the same day is idempotent
- **WHEN** `collect_portwatch` runs twice for the same observation date
- **THEN** the second run produces zero net inserts and `CollectionLog` records `rows_collected=0` (or only late-arriving rows)

### Requirement: Entity bootstrap from PortWatch reference data
The system SHALL bootstrap `Port` and `Chokepoint` rows from PortWatch reference endpoints on first run and on a weekly refresh, populating `name`, `country`, `region`, `locode` (where available), and PostGIS `geom` for each entity.

#### Scenario: First-run bootstrap
- **WHEN** the database has no ports or chokepoints and the bootstrap task runs
- **THEN** every PortWatch port and chokepoint is inserted with a non-null `geom` and the entity is mapped to its PortWatch `source_entity_id` via `DataCoverage`

#### Scenario: Reference refresh adds new entities only
- **WHEN** PortWatch publishes a new port and the weekly refresh runs
- **THEN** only the new entity is inserted; existing entities are not duplicated or overwritten unless `name`/`country` changed

### Requirement: Collection failure isolation
The system SHALL isolate per-entity collection failures so that a single failing entity does not abort the run.

#### Scenario: One port returns 5xx
- **WHEN** PortWatch returns HTTP 500 for one port and 200 for the rest
- **THEN** all other ports' metrics are persisted, the failing port's error is recorded in `CollectionLog.error`, and `DataCoverage.last_collection_status` for that port is set to `"error"`

### Requirement: Rate-limit and backoff
The system SHALL respect PortWatch rate limits via configurable concurrency and SHALL retry transient failures (HTTP 429/5xx, timeouts) with exponential backoff up to 3 attempts.

#### Scenario: Rate limit response
- **WHEN** PortWatch returns HTTP 429 with a `Retry-After` header
- **THEN** the collector waits the indicated duration and retries, and only marks the row as failed after the third attempt
