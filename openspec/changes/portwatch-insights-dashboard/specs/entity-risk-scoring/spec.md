## ADDED Requirements

### Requirement: Daily risk score computation
The system SHALL compute a daily risk score for every active port and chokepoint from PortWatch-derived feature values and persist the result into `PortRiskScore` / `ChokepointRiskScore` with a unified `entity_id` keyspace.

#### Scenario: Nightly scoring run
- **WHEN** the `compute_risk_scores` task runs after PortWatch ingestion
- **THEN** every entity with non-stale features in the last 7 days gets a new score row with `score`, `severity`, `component_scores`, `freshness_status`, and `as_of`

### Requirement: Feature snapshot persistence
The system SHALL persist the feature inputs, rolling baselines, z-scores, and deltas used for each daily score into `RiskFeatureSnapshot` so that scores are explainable and reproducible.

#### Scenario: Snapshot accompanies score
- **WHEN** a score is written for entity `port:USLAX` on date `D`
- **THEN** a `RiskFeatureSnapshot` row exists with the same `(snapshot_date=D, entity_type='port', entity_id='USLAX')`, populated `feature_values`, `baseline_values`, `z_scores`, `deltas`, and a non-null `feature_schema_version`

### Requirement: Severity bucketing
The system SHALL map continuous scores to severity buckets `low`, `elevated`, `high`, `critical` using configurable thresholds and SHALL record the active threshold set in `RiskFeatureSnapshot.driver_metadata`.

#### Scenario: Threshold mapping
- **WHEN** a score is 0.82 and the configured thresholds are `[0.3, 0.6, 0.8]`
- **THEN** `severity` is `"critical"` and `driver_metadata.thresholds` echoes the active thresholds

### Requirement: Missing-component handling
The system SHALL still produce a score when up to a configured fraction of components are missing, SHALL list missing component names in `missing_components`, and SHALL refuse to score (writing `severity="unknown"` and no score) when too many components are missing.

#### Scenario: Partial coverage
- **WHEN** 2 of 6 feature components are missing and the threshold is `max_missing_fraction=0.5`
- **THEN** a score is produced, `missing_components` lists the two, and `freshness_status` reflects the worst component freshness

#### Scenario: Insufficient coverage
- **WHEN** 5 of 6 components are missing
- **THEN** the row has `score=NULL`, `severity="unknown"`, and `reasons` includes `"insufficient_components"`

### Requirement: Rolling baseline windows
The system SHALL compute z-scores against both a 30-day and 90-day rolling baseline per entity-metric and persist both, defaulting `score` to the 30-day basis.

#### Scenario: Both baselines stored
- **WHEN** a snapshot is written
- **THEN** `z_scores` contains entries keyed by metric with `{ "z_30d": ..., "z_90d": ... }` shapes for each feature
