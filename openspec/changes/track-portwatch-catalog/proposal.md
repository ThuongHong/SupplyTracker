## Why

The app only knows 14 hardcoded ports + 8 chokepoints via a brittle curated `locode→portid` map, while PortWatch publishes ~2065 ports + 28 chokepoints. Users cannot browse the full catalog or choose which entities to follow. We need a full metadata catalog plus a user-driven "track only what I care about" model so data fetching and scoring stay bounded.

## What Changes

- Ingest **metadata only** (portid, name, country, lat/lon) for all ~2065 ports + 28 chokepoints from the PortWatch ArcGIS master FeatureServers. No metrics at catalog time.
- Add `portid` / `chokepointid` as a **UNIQUE NOT NULL business key** on `ports` / `chokepoints`, plus an `is_tracked` flag. Int surrogate `id` is kept so existing FKs do not break.
- **BREAKING**: `PortWatchMetric.entity_id` for ports becomes `portid` (was `locode`). Dashboard, port-detail route, and news collector switch to `portid`. The curated 14-port map is **removed**.
- Per-entity **Sync = Track**: clicking Sync on a catalog entity fetches its **90 days** of daily data and sets `is_tracked=true`. An Untrack action clears the flag (data retained).
- Daily Celery-beat appends the latest day for all tracked entities. News + risk scoring run for tracked entities only.
- List APIs (`/ports`, `/chokepoints`) gain `q` (name/country search) and `tracked` filters (already paginated).
- Frontend: Tracked / Browse-all tabs with paged, searchable lists and per-row Sync / Untrack buttons.

## Capabilities

### New Capabilities
- `entity-catalog`: Metadata-only ingest of the full PortWatch port/chokepoint catalog into our DB (paged from ArcGIS, idempotent re-sync preserving tracked flags), exposed via paginated + searchable list APIs and tracked/untracked browsing.
- `entity-tracking`: User-driven tracking — per-entity 90-day data sync that also marks an entity tracked, untrack, daily beat refresh of tracked entities, and tracked-only scope for news + risk scoring.

### Modified Capabilities
<!-- No existing OpenSpec specs; all behavior is introduced as new capabilities. -->

## Impact

- **DB / migration**: Alembic 0004 adds `portid`/`chokepointid` (unique) + `is_tracked` to `ports`/`chokepoints`. `seed_dev` reworked to run catalog ingest then mark the known 14 + 8 as tracked.
- **Collectors**: `portwatch.py` rewritten (drop curated map, query tracked portids / 90-day per entity); `google_news.py` filters to tracked entities.
- **API**: `app/api/routes/ports.py`, `chokepoints.py`, `sync.py` — new filters + per-entity sync/track/untrack endpoints (bearer-protected).
- **Services**: `dashboard.py`, `scoring`/`score.py` switch port `entity_id` to `portid`.
- **Frontend**: `ports.ts`, `chokepoints.ts`, port/chokepoint views + new tabbed catalog browser components.
- **External**: PortWatch ArcGIS master FeatureServers (no key, 1000 rows/req paging).
