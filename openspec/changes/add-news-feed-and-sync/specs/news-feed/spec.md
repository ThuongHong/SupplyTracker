## ADDED Requirements

### Requirement: System SHALL collect Google News items per port and chokepoint

The backend SHALL fetch Google News RSS results for each active port and chokepoint at a fixed cadence (every 6 hours) and on demand via the manual-sync trigger, parse the items, and upsert them into a dedicated `news_item` table.

#### Scenario: Scheduled fetch populates news_item

- **WHEN** the Celery-beat schedule fires `collect.news` at minute 15 of hours 0, 6, 12, 18 UTC
- **THEN** the collector iterates over every `Port` and `Chokepoint` row, builds a query from the entity name plus its known aliases (LOCODE / lane keys), fetches the Google News RSS feed, and inserts each parsed item into `news_item` with `(entity_type, entity_id, url_hash)` as the unique key

#### Scenario: Duplicate articles are not re-inserted

- **WHEN** the collector fetches an article whose `(entity_type, entity_id, url_hash)` already exists
- **THEN** the existing row is left in place and no duplicate row is written

#### Scenario: A single article is stored per entity it matches

- **WHEN** the same article URL is returned for both a chokepoint and a downstream port
- **THEN** two rows are stored — one for each `(entity_type, entity_id)` — so each entity's feed shows the article

#### Scenario: Old news is pruned

- **WHEN** the collector finishes a successful run
- **THEN** any `news_item` row with `published_at < now() - 90 days` is deleted

#### Scenario: Collector failure does not break the rest of the pipeline

- **WHEN** the Google News RSS fetch fails for one entity (HTTP error, parse error, timeout)
- **THEN** the collector logs the error against that entity, continues with the remaining entities, and the task retries with Celery's default retry policy if the whole run errors out

### Requirement: API SHALL expose news items per entity

The backend SHALL provide a public read-only endpoint `GET /entities/{entity_type}/{entity_id}/news` that returns the most recent news items for the entity, ordered by `published_at` descending.

#### Scenario: Fetching news for a known port

- **WHEN** a client calls `GET /entities/port/SGSIN/news?limit=20`
- **THEN** the response is `200 OK` with `{ items: NewsItem[], count: int }` where each `NewsItem` contains `id`, `url`, `title`, `source`, `published_at`, `summary`, `language`, and `fetched_at`, sorted by `published_at` desc, capped at 20

#### Scenario: Fetching news for a known chokepoint

- **WHEN** a client calls `GET /entities/chokepoint/hormuz/news`
- **THEN** the response is `200 OK` with the recent news rows for that chokepoint, default limit 20

#### Scenario: Limit clamping

- **WHEN** a client passes `limit=500`
- **THEN** the response contains at most 100 items

#### Scenario: Invalid entity_type

- **WHEN** a client calls `GET /entities/foo/SGSIN/news`
- **THEN** the response is `422 Unprocessable Entity`

#### Scenario: Unknown entity_id

- **WHEN** a client calls `GET /entities/port/ZZZZZ/news` and `ZZZZZ` does not exist
- **THEN** the response is `404 Not Found`

#### Scenario: Since cursor

- **WHEN** a client passes `since=<iso8601>`
- **THEN** only items with `published_at > since` are returned

### Requirement: Event Log UI SHALL surface news alongside system events

The port and chokepoint detail views SHALL render two grouped sections within the Event Log: existing system-detected events (from `/story`) and external news (from `/entities/{type}/{id}/news`).

#### Scenario: Switching between tabs

- **WHEN** a user opens a port or chokepoint detail page
- **THEN** the Event Log card shows two tabs ("System events" and "News"); "System events" is selected by default

#### Scenario: News tab content

- **WHEN** the user clicks the "News" tab
- **THEN** up to 20 news items render, each showing the article title (as an external link to `url` opened in a new tab with `rel="noopener noreferrer"`), publisher, and human-readable published time

#### Scenario: Empty news state

- **WHEN** there are no news items for the entity
- **THEN** the News tab shows an empty-state message "No news available"

#### Scenario: Error on news fetch

- **WHEN** the news endpoint returns a non-2xx response or a network error
- **THEN** the News tab shows an error state with a retry affordance and the System events tab remains usable

### Requirement: News collection SHALL be controllable via config

The collector SHALL respect environment configuration to disable fetching and to cap per-entity items.

#### Scenario: Feature flag disables fetch

- **WHEN** `NEWS_FETCH_ENABLED=false` is set
- **THEN** scheduled and manual news collection runs exit immediately with a no-op summary `{rows: 0, errors: []}`

#### Scenario: Per-entity item cap

- **WHEN** `NEWS_MAX_ITEMS_PER_ENTITY=N` is set (default 30)
- **THEN** the collector inserts at most N items per entity per run, selecting the most recent by `published_at`
