## ADDED Requirements

### Requirement: UI SHALL provide a user-triggered Sync button

The frontend SHALL display a "Sync" button on the port detail view, the chokepoint detail view, and (optionally) the dashboard header that triggers a force-fetch of upstream data sources.

#### Scenario: Sync button is visible on detail views

- **WHEN** a user opens `PortDetailView` or `ChokepointDetailView`
- **THEN** a "Sync" button is rendered next to the page title

#### Scenario: Clicking Sync triggers backend collection

- **WHEN** the user clicks the Sync button
- **THEN** the frontend issues `POST /sync/all` with the configured bearer token, displays a "Sync started" toast that includes the returned `task_id`, and disables the button for at least 30 seconds to prevent accidental double-fire

#### Scenario: Bearer token missing

- **WHEN** no admin bearer token is configured in the frontend (env or local storage)
- **THEN** the Sync button is hidden (not just disabled) to avoid presenting an action that always fails

#### Scenario: Sync request fails

- **WHEN** the `POST /sync/all` call returns a non-2xx response or network error
- **THEN** the frontend shows an error toast with the response message, and the button is re-enabled immediately so the user can retry

#### Scenario: Concurrent click guard

- **WHEN** the user double-clicks the Sync button
- **THEN** only one POST request is sent

### Requirement: Sync endpoint SHALL accept "news" as a valid source

The `POST /sync/{source}` endpoint SHALL include `news` in its valid-source set and dispatch to the `collect_news` Celery task.

#### Scenario: Trigger news sync

- **WHEN** an authenticated caller does `POST /sync/news`
- **THEN** the endpoint enqueues `collect_news` and returns `{ task_id, source: "news" }` with status `202` or `200`

#### Scenario: collect_all includes news

- **WHEN** an authenticated caller does `POST /sync/all`
- **THEN** the `collect_all` chord includes `collect_news` in its group of parallel tasks

#### Scenario: Unknown source rejected

- **WHEN** the caller posts `POST /sync/foo`
- **THEN** the endpoint returns `422` with the list of valid sources including `news`

### Requirement: Sync endpoint SHALL remain bearer-protected

The `POST /sync/{source}` endpoint SHALL continue to require the existing `AuthRequired` bearer dependency; no anonymous access is permitted.

#### Scenario: Missing bearer token

- **WHEN** an unauthenticated caller does `POST /sync/all`
- **THEN** the endpoint returns `401 Unauthorized`

#### Scenario: Invalid bearer token

- **WHEN** a caller posts with a malformed or unknown bearer token
- **THEN** the endpoint returns `401 Unauthorized`
