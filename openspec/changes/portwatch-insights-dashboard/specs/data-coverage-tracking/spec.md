## ADDED Requirements

### Requirement: Per-source coverage rows
The system SHALL maintain a `DataCoverage` row per `(source, entity_type, entity_id)` and SHALL update it on every collection run.

#### Scenario: Coverage updated on success
- **WHEN** a collector successfully ingests new rows for `(source="portwatch", entity_type="port", entity_id="USLAX")`
- **THEN** the corresponding `DataCoverage` row updates `latest_observed_at`, increments `observed_rows`, recomputes `missing_days`, and sets `last_collection_status="success"`

### Requirement: Freshness status
The system SHALL compute `freshness_status` as `"fresh"` if `latest_observed_at` is within the source's expected cadence, `"stale"` if within 2x cadence, and `"missing"` beyond that.

#### Scenario: PortWatch freshness
- **WHEN** PortWatch's expected cadence is 24h and `latest_observed_at` is 36h old
- **THEN** `freshness_status` is `"stale"`

#### Scenario: Bunker scrape freshness
- **WHEN** bunker prices for a port have not updated in 5 days
- **THEN** `freshness_status` is `"missing"` and the UI freshness banner reflects this

### Requirement: Coverage API
The system SHALL expose `GET /api/v1/stats/coverage` returning all coverage rows, filterable by `source` and `entity_type`.

#### Scenario: Filter by source
- **WHEN** a client calls `GET /api/v1/stats/coverage?source=portwatch`
- **THEN** only rows with `source="portwatch"` are returned, ordered by `freshness_status` desc then `entity_name` asc

### Requirement: Backfill window calculation
The system SHALL compute `expected_days` as the integer number of days between `first_observed_at` and `now()` and SHALL compute `missing_days = expected_days - observed_rows` clamped to `>= 0`.

#### Scenario: Backfill math
- **WHEN** `first_observed_at` is 100 days ago, `observed_rows = 80`
- **THEN** `expected_days = 100` and `missing_days = 20`
