## ADDED Requirements

### Requirement: Event detection from snapshots
The system SHALL scan each new `RiskFeatureSnapshot` and emit `RiskStoryEvent` rows for: (a) any metric with `|z_30d| >= 2.5`, (b) any metric crossing a severity threshold relative to the prior day, (c) any metric on a streak of 5+ consecutive days above/below baseline.

#### Scenario: Z-score spike emits event
- **WHEN** a port's `port_calls` metric has `z_30d = 3.1` in today's snapshot
- **THEN** a `RiskStoryEvent` row exists with `event_type="z_spike"`, `metric="port_calls"`, `z_score=3.1`, and a non-empty `narrative`

#### Scenario: Severity transition emits event
- **WHEN** a chokepoint moves from `severity="elevated"` to `severity="critical"` between two days
- **THEN** a `RiskStoryEvent` is written with `event_type="severity_step_up"`, `attention_level="high"`, and `event_key` deterministic on `(entity, date, event_type)`

### Requirement: Event idempotency
The system SHALL use a deterministic `event_key` of the form `{entity_type}:{entity_id}:{date}:{event_type}:{metric}` and SHALL upsert rather than duplicate events on re-runs.

#### Scenario: Re-running detection produces no duplicates
- **WHEN** the detection task runs twice on the same snapshot
- **THEN** the count of `RiskStoryEvent` rows is unchanged after the second run

### Requirement: Disruption propagation linkage
The system SHALL, for any chokepoint event with `severity` in `("high","critical")`, write a `DisruptionPropagation` row linking the chokepoint to each downstream port whose region intersects the chokepoint's serviced lanes.

#### Scenario: Hormuz critical event propagates
- **WHEN** a `critical` event is emitted for `chokepoint:hormuz`
- **THEN** `DisruptionPropagation` rows exist with `source_entity_id="hormuz"` and a `target_entity_id` for each Persian-Gulf-served port in the lane mapping
