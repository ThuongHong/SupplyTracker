## 1. Backend — schema & migration

- [x] 1.1 Add `feedparser` to `backend/pyproject.toml` and rebuild image.
- [x] 1.2 Add `NewsItem` SQLAlchemy model in `backend/app/db/models.py` per design (cols: `id`, `entity_type`, `entity_id`, `url_hash`, `url`, `title`, `source`, `published_at`, `summary`, `language`, `fetched_at`, unique key, indexes).
- [x] 1.3 Generate Alembic migration creating `news_item`; verify `alembic upgrade head` succeeds locally.
- [x] 1.4 Add `NEWS_FETCH_ENABLED: bool = True` and `NEWS_MAX_ITEMS_PER_ENTITY: int = 30` to `backend/app/config.py`.

## 2. Backend — collector

- [x] 2.1 Create `backend/app/collectors/google_news.py` with `GoogleNewsCollector` extending `BaseCollector` (source_name="news").
- [x] 2.2 Build per-entity query helper: entity name + aliases (LOCODE for ports, `_CHOKEPOINT_LANE_MAP` aliases for chokepoints).
- [x] 2.3 Fetch RSS via `feedparser.parse(<google_news_url>)`; handle HTTP / parse errors per entity and continue.
- [x] 2.4 Upsert into `news_item` keyed by `(entity_type, entity_id, url_hash=sha256(url))`; cap at `NEWS_MAX_ITEMS_PER_ENTITY`.
- [x] 2.5 Prune rows where `published_at < now() - 90d` at end of run.
- [x] 2.6 Respect `NEWS_FETCH_ENABLED` — if false, return `{rows: 0, errors: []}` immediately.

## 3. Backend — Celery wiring

- [x] 3.1 Add `collect_news` task in `backend/app/tasks/collect.py` (mirror existing `collect_*` patterns).
- [x] 3.2 Add `collect_news.s()` to the `collect_all` group.
- [x] 3.3 Add schedule entry `"collect-news-6h"` in `backend/app/tasks/schedule.py` (`crontab(minute='15', hour='*/6')`, queue=`collection`).

## 4. Backend — API surface

- [x] 4.1 Add `NewsItem` Pydantic schema in `backend/app/schemas/news.py` (response model `NewsListResponse`).
- [x] 4.2 Create `backend/app/api/routes/news.py` with `GET /entities/{entity_type}/{entity_id}/news?limit=&since=`; validate `entity_type ∈ {port, chokepoint}`, verify entity exists, clamp `limit ≤ 100`.
- [x] 4.3 Register news router in `backend/app/api/router.py`.
- [x] 4.4 Extend `backend/app/api/routes/sync.py`: add `news` to `_VALID_SOURCES` and `task_map`.

## 5. Backend — tests

- [x] 5.1 Unit test `GoogleNewsCollector` with a fixture RSS payload (mock `feedparser.parse`).
- [x] 5.2 Test dedup: same `(entity_type, entity_id, url_hash)` only inserted once.
- [x] 5.3 Test cross-entity storage: same URL stored for both chokepoint and downstream port.
- [x] 5.4 Test pruning of rows older than 90 days.
- [x] 5.5 Test endpoint happy path, 404 unknown entity, 422 invalid entity_type, limit clamp, `since` filter.
- [x] 5.6 Test `POST /sync/news` enqueues `collect_news` and `POST /sync/all` includes it.

## 6. Frontend — API client

- [x] 6.1 Add `NewsItem` and `NewsListResponse` types in `frontend/src/api/types.ts`.
- [x] 6.2 Create `frontend/src/api/news.ts` with `fetchEntityNews(entityType, entityId, opts)` using `apiFetch`.
- [x] 6.3 Create `frontend/src/api/sync.ts` with `triggerSync(source)` POSTing to `/sync/{source}` with bearer token (existing client pattern).

## 7. Frontend — UI components

- [x] 7.1 Refactor `EventLog` in `PortDetailView.tsx` and `ChokepointDetailView.tsx` into a shared component `frontend/src/components/EventLog.tsx` that accepts `entityType + entityId`.
- [x] 7.2 Add two-tab UI inside the Event Log card ("System events" default, "News"); fetch news lazily on first tab activation.
- [x] 7.3 Render news rows: title (external link, `target="_blank" rel="noopener noreferrer"`), publisher, relative published time; empty/error/loading states.
- [x] 7.4 Create `frontend/src/components/SyncButton.tsx` — hidden when no admin token is configured; on click POSTs `/sync/all`, shows toast with `task_id`, disables for 30s, re-enables on error.
- [x] 7.5 Mount `<SyncButton />` in the headers of `PortDetailView.tsx` and `ChokepointDetailView.tsx`.

## 8. Frontend — tests

- [x] 8.1 Vitest for `fetchEntityNews` query string + response parsing.
- [x] 8.2 Vitest for `SyncButton`: hidden without token, fires POST once, disabled after click, error toast on failure.
- [x] 8.3 Vitest for `EventLog` tab switching and news rendering with mocked fetch.

## 9. Verification

- [x] 9.1 Run `make test` (backend pytest + frontend vitest) — all green.
- [x] 9.2 Run `make lint` (ruff + mypy) — clean.
- [x] 9.3 `make up && make bootstrap`, then `make collect-all` and confirm `news_item` rows appear; spot-check `/entities/port/SGSIN/news` returns items.
- [x] 9.4 Manual UI smoke: open a port detail page, switch to News tab, click external link, click Sync button, verify toast + Celery log shows `collect_*` tasks enqueued.

## 10. Docs

- [x] 10.1 Update `README.md` "Common make targets" if needed and add a one-line note about `NEWS_FETCH_ENABLED` in `.env.example`.
- [x] 10.2 Document the admin bearer token used by the Sync button (where the frontend reads it from) in `README.md`.
