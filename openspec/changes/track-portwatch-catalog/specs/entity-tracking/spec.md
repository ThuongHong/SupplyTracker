## ADDED Requirements

### Requirement: Per-entity sync fetches 90 days and tracks

A bearer-protected per-entity sync endpoint (`POST /sync/port/{portid}` and `POST /sync/chokepoint/{chokepointid}`) SHALL fetch the most recent 90 days of daily data for that single entity from the PortWatch daily FeatureServers, upsert the resulting metrics, and set the entity's `is_tracked` flag to `true`. Port metrics SHALL use `portid` as their `entity_id`.

#### Scenario: Sync backfills 90 days and marks tracked
- **WHEN** a client calls `POST /sync/port/{portid}` for an untracked port
- **THEN** daily rows for that portid within the last 90 days are upserted into `port_watch_metric` with `entity_id = portid`
- **AND** the port's `is_tracked` becomes `true`

#### Scenario: Unknown entity rejected
- **WHEN** a client calls the per-entity sync with a portid not present in the catalog
- **THEN** the endpoint returns a 404 and writes no metrics

#### Scenario: Missing bearer token rejected
- **WHEN** the per-entity sync is called without a valid sync bearer token
- **THEN** the endpoint returns 401

### Requirement: Untrack an entity

A bearer-protected untrack action SHALL set an entity's `is_tracked` flag to `false`. Previously collected metrics SHALL be retained.

#### Scenario: Untrack clears flag but keeps data
- **WHEN** a client untracks a tracked port
- **THEN** the port's `is_tracked` becomes `false`
- **AND** its existing rows in `port_watch_metric` remain

### Requirement: Daily refresh of tracked entities

A daily Celery-beat task SHALL append the latest available day of PortWatch data for every entity with `is_tracked=true`. Entities that are not tracked SHALL NOT be fetched.

#### Scenario: Beat appends latest day for tracked only
- **WHEN** the daily refresh task runs
- **THEN** it fetches the latest day's metrics only for entities where `is_tracked=true`
- **AND** untracked entities receive no new metric rows

### Requirement: Tracked-only scope for news and scoring

The news collector and the risk-scoring pipeline SHALL operate only on tracked entities. The previously hardcoded curated port map SHALL NOT be used.

#### Scenario: News fetched for tracked entities only
- **WHEN** the news collector runs
- **THEN** it queries news for entities with `is_tracked=true` only

#### Scenario: Scoring covers tracked entities
- **WHEN** the risk-scoring pipeline runs
- **THEN** it scores the entities that have tracked metrics and does not score untracked catalog entries
