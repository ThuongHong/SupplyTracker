## ADDED Requirements

### Requirement: REST surface
The system SHALL expose a versioned REST API under `/api/v1` with routers for `health`, `ports`, `chokepoints`, `indices`, `risk`, `story`, `insights`, `stats`, `sync`, and `chat`.

#### Scenario: Health probe
- **WHEN** a client calls `GET /api/v1/health`
- **THEN** the response is HTTP 200 with `{ "status": "ok", "db": "ok", "redis": "ok", "version": <semver> }`

### Requirement: Ports list and detail
The system SHALL expose `GET /api/v1/ports` returning paginated port summaries (id, locode, name, country, region, current severity, latest risk score, last-observed-at) and `GET /api/v1/ports/{id}` returning the full detail (recent metrics, recent events, last forecast, last snapshot).

#### Scenario: Pagination
- **WHEN** a client calls `GET /api/v1/ports?limit=50&offset=0&severity=high`
- **THEN** at most 50 results are returned, all with `severity="high"`, and the envelope includes `total` and `has_more`

### Requirement: Chokepoints list and detail
The system SHALL expose `GET /api/v1/chokepoints` and `GET /api/v1/chokepoints/{id}` mirroring the ports endpoints, plus `GET /api/v1/chokepoints/{id}/breakdown` returning the last 50 days of transit counts broken down by vessel/cargo category.

#### Scenario: 50-day breakdown
- **WHEN** a client calls `GET /api/v1/chokepoints/hormuz/breakdown`
- **THEN** the response contains exactly up to 50 daily rows, each with `date`, `total`, and counts per category from PortWatch's category dimension

### Requirement: Risk endpoints
The system SHALL expose `GET /api/v1/risk/scores`, `GET /api/v1/risk/scores/{entity}`, and `GET /api/v1/risk/forecasts/{entity}` returning the latest persisted rows with appropriate freshness metadata.

#### Scenario: Latest score
- **WHEN** a client calls `GET /api/v1/risk/scores/port:USLAX`
- **THEN** the response is the most recent `PortRiskScore` row plus the matching `RiskFeatureSnapshot` for that day

### Requirement: Story and insights feeds
The system SHALL expose `GET /api/v1/story?since=<iso>` returning ordered `RiskStoryEvent` rows and `GET /api/v1/insights?attention_level=<level>` returning `Insight` rows filtered by level.

#### Scenario: Story feed since timestamp
- **WHEN** a client calls `GET /api/v1/story?since=2026-05-20T00:00:00Z`
- **THEN** only events with `event_time >= 2026-05-20T00:00:00Z` are returned, ordered by `event_time desc`, capped at 200

### Requirement: Sync trigger endpoint
The system SHALL expose an authenticated `POST /api/v1/sync/{source}` that enqueues the corresponding Celery collector task and SHALL reject unauthorized calls with HTTP 401.

#### Scenario: Manual portwatch sync
- **WHEN** an authenticated client posts to `/api/v1/sync/portwatch`
- **THEN** a Celery task is enqueued and the response includes its `task_id`

### Requirement: Error envelope
The system SHALL return errors in a consistent JSON envelope `{ "error": { "code": <str>, "message": <str>, "details": <obj?> } }` with appropriate HTTP status codes.

#### Scenario: Unknown entity
- **WHEN** a client calls `GET /api/v1/ports/UNKNOWN`
- **THEN** the response is HTTP 404 with body `{ "error": { "code": "not_found", "message": "Port UNKNOWN does not exist" } }`
