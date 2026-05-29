## Context

The Event Log on port/chokepoint detail pages currently shows only `RiskStoryEvent` rows produced by the scoring pipeline (anomaly + LLM narrative). These are useful but disconnected from real-world incidents — strikes, sanctions, storms, congestion announcements — that operators read about in the news. Data ingestion is driven by Celery-beat (`schedule.py`): PortWatch hourly, FRED/FBX/WCI/Bunker daily, scoring at :30, forecast/narrate daily. A bearer-protected `POST /sync/{source}` endpoint already exists (`api/routes/sync.py`) and delegates to `collect_portwatch`, `collect_fred`, `collect_fbx`, `collect_wci`, `collect_bunker`, or `collect_all`. The frontend never calls it.

Two adjacent gaps motivate one change: bring external news into the Event Log, and expose force-fetch in the UI so users do not have to wait for the next scheduled tick.

## Goals / Non-Goals

**Goals:**
- Persist Google News items per entity (port, chokepoint) so the Event Log can render them next to system anomalies.
- Refresh news on a 6h cadence (and on demand via sync) without API keys or paid SaaS.
- Provide a single-click UI Sync button that triggers `POST /sync/{source}` and surfaces task progress to the user.
- Reuse existing collector base class, Celery patterns, schemas, auth, and table conventions.

**Non-Goals:**
- LLM summarisation of news (later change; could feed into narrative pipeline).
- Cross-language / non-English news sources.
- Pushing news events into the `RiskStoryEvent` table or scoring pipeline.
- Per-user feed customisation (saved filters, subscriptions).
- Real-time websocket updates — polling at 6h + manual sync is sufficient.

## Decisions

### 1. News source = Google News RSS (no API key)

**Choice:** `https://news.google.com/rss/search?q=<entity_query>&hl=en&gl=US&ceid=US:en`, parsed with `feedparser`.

**Why:** No API key, no quota cost, broad coverage, well-known schema. Alternative (NewsAPI.org, Bing News, GDELT) either requires keys, has paid tiers, or is harder to ingest.

**Trade-off:** Google News RSS is informally supported and can rate-limit aggressive scrapers. Mitigated by 6h cadence, per-entity caching, and politeness (sequential fetch with sleep + UA header).

### 2. Query construction per entity

Build the query as `entity.name` plus a small alias list (e.g., chokepoint LOCODE aliases from `_CHOKEPOINT_LANE_MAP`, port LOCODE). Quote multi-word names. Examples:
- Port: `"Port of Singapore" OR SGSIN port`
- Chokepoint: `"Strait of Hormuz" OR Hormuz shipping`

Store the query string alongside results for debugging.

**Alternative considered:** Full-text generic feeds (e.g., supply-chain bulk feed) filtered server-side. Rejected — noisier and forces us to invent ranking.

### 3. Storage: new `news_item` table, keyed by URL hash

```
news_item(
  id                BIGSERIAL PK,
  entity_type       VARCHAR(16)  -- 'port' | 'chokepoint'
  entity_id         VARCHAR(64)
  url_hash          VARCHAR(64)  -- sha256(canonical_url)
  url               TEXT
  title             TEXT
  source            VARCHAR(128) -- publisher (e.g. "Reuters")
  published_at      TIMESTAMPTZ
  summary           TEXT NULL
  language          VARCHAR(8)   DEFAULT 'en'
  fetched_at        TIMESTAMPTZ  DEFAULT now()
  UNIQUE(entity_type, entity_id, url_hash)
)
INDEX(entity_type, entity_id, published_at DESC)
```

Uniqueness on `(entity_type, entity_id, url_hash)` lets the same article appear under multiple entities (a Suez story for both Suez chokepoint and Port Said port) without dedup loss across entities.

**Alternative considered:** Store as JSON inside `RiskStoryEvent` with a new `event_type='news'`. Rejected — distorts the anomaly schema (no `metric`, `z_score`, `confidence`), pollutes scoring queries.

### 4. Retention: rolling 90 days

Delete `news_item` rows with `published_at < now() - 90 days` in the collector run. Keeps table small; matches the dashboard's seeded data window.

### 5. New endpoint surface

```
GET /entities/{entity_type}/{entity_id}/news?limit=20&since=<iso>
  → { items: NewsItem[], count: int }
```

Public read (matches `/story`). Validates `entity_type ∈ {port, chokepoint}` and existence. Cap `limit` at 100.

**Alternative considered:** Extend `/story` to mix news + system events. Rejected — the two have different schemas and the UI groups them separately anyway; mixing forces a polymorphic response shape.

### 6. Sync button auth

The existing `/sync/{source}` requires `AuthRequired`. Re-use whatever bearer flow the frontend already employs for protected actions (check `frontend/src/api/client.ts` `apiFetch` headers — token read from `localStorage` / `import.meta.env`). The Sync button is only shown when an admin token is configured; otherwise hidden. Polling result via `GET /tasks/{task_id}` if it exists, else fire-and-toast.

**Alternative considered:** Make `/sync` public-read with rate limit. Rejected — running collectors is a side-effecting action and should stay gated.

### 7. UI placement

- **News in Event Log**: render a tabbed or grouped view inside the existing `Card title="Event Log"`. Sub-tabs: "System events" (default) and "News". Avoids cluttering current users who only want anomalies.
- **Sync button**: a small button cluster in the detail-page header (right of the title). Two options:
  - one-shot button triggering `sync/all`
  - dropdown with `portwatch | news | all` choices
  - Default to one-shot `sync/all` to keep UX simple; menu later.

### 8. Celery wiring

- Add `collect_news` task (`collect.news`) in `app/tasks/collect.py`, following the existing pattern (bind=True, retry, `_run_collector`).
- Add to `collect_all` group.
- Schedule in `schedule.py`: `crontab(minute='15', hour='*/6')` → 4×/day at :15.
- Queue: `collection`.

### 9. Frontend data fetching

- New `api/news.ts` thin wrapper around `apiFetch`.
- `EventLog` component takes `entityType + entityId`, fetches both `/story` (filtered) and `/entities/{type}/{id}/news`, switches between tabs locally.
- Page Sync button uses a small mutation hook with toast feedback (`react-hot-toast` if present, else inline status text).

## Risks / Trade-offs

- **Google News RSS unofficial** → format changes / rate limits could break the collector. Mitigation: pin `feedparser`, log parsing failures, alert if 0 rows for >24h.
- **Noisy / irrelevant articles** for short entity names (e.g., a port called "Port Said" vs the phrase "port said") → Mitigation: alias quoting + post-filter on stopwords; future LLM-based relevance scoring.
- **Sync abuse** if frontend exposes button without rate-limit awareness → Mitigation: keep bearer-protected; rely on existing `app/api/rate_limit.py` if hooked; debounce in UI.
- **`/sync` is fire-and-forget** — UI cannot show "done" without a task-status endpoint. Mitigation: surface task_id + collector source via toast; optional follow-up change adds a polling endpoint.
- **Duplicate articles cross-entity** — same news appears for chokepoint and downstream port. Acceptable; the unique key is per-entity so each gets its own row.

## Migration Plan

1. Add Alembic migration creating `news_item`.
2. Ship collector + tasks + endpoint behind a feature flag `NEWS_FETCH_ENABLED` (default true).
3. Deploy backend; verify scheduled run + sample fetch populate rows.
4. Ship frontend; verify Event Log tabs render and Sync button hits the endpoint with a token.
5. Rollback = drop migration + revert; no other table touched.

## Open Questions

- Should the news endpoint support filtering by publisher / keyword? (Probably v2.)
- Do we want Sync button to also kick off `score.run_pipeline` after `collect_all`? (Lean no — beat will pick it up at :30.)
- Per-entity Sync vs global Sync — start global for simplicity; revisit if users ask for per-port refresh.
