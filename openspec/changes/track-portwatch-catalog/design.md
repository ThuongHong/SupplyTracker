## Context

PortWatch data is keyed by an internal `portid` (e.g. `port1188`, `chokepoint1`). UN/LOCODEs in the master are spaced, divergent, and often null (their Shanghai is `CN SGH`, ours is `CNSHA`), so the current `locode→portid` join is lossy and is hardcoded to 14 ports. The app keys port metrics by `locode` today (`PortWatchMetric.entity_id == port.locode`). We want the full ~2065-port catalog browsable, with users tracking a chosen subset and fetching 90 days on demand.

Constraints:
- ArcGIS master/daily FeatureServers are public (no key), `maxRecordCount = 1000`.
- `ports.id` / `chokepoints.id` (int) are referenced by FKs in `PortCongestion`, `PortRiskScore`, and snapshot tables — swapping the PK is invasive.
- `chokepoints.geom` is POLYGON NOT NULL; master gives points only.

## Goals / Non-Goals

**Goals:**
- Ingest catalog metadata only (no metrics) for all ports + chokepoints, idempotently.
- `portid`/`chokepointid` as the stable business key + API identifier + port metric `entity_id`.
- Per-entity Sync that backfills 90 days and tracks; daily beat keeps tracked fresh.
- Bounded work: news + scoring touch tracked entities only.

**Non-Goals:**
- Per-user favourites / auth (single global tracked list).
- Replacing the int surrogate PK or rewriting existing FKs.
- Backfilling >90 days or historical metric reconstruction.
- Chokepoint `entity_id` scheme change (stays name-based for the disruption lane map).

## Decisions

**1. `portid` as unique business key, keep int surrogate `id`.**
Add `portid`/`chokepointid` as UNIQUE NOT NULL columns and use them as the API path id and the port metric `entity_id`; leave `id` as the FK target. *Alternative considered:* string PK swap — rejected, forces rewriting FKs in 3+ tables and a data migration for no functional gain.

**2. Port metric `entity_id` switches from `locode` to `portid` (BREAKING).**
Update `dashboard.py` (port join), `ports.py` detail route, and `google_news.py` to resolve ports by `portid`. Deletes the curated 14-port map and the locode-mismatch problem. Chokepoint `entity_id` remains `name.lower().replace(" ","_")`. *Alternative:* keep `locode` with `portid` fallback — rejected as permanently messy for null/divergent LOCODEs.

**3. Catalog ingest is metadata-only, separate from metrics.**
A `catalog` collector pages the two master FeatureServers (`resultOffset` loop, 1000/page) and upserts metadata; it never calls the daily layers. Re-sync upserts on `portid` and never resets `is_tracked`. Exposed via `POST /sync/catalog` + a make target. Chokepoint geometry is a synthesized circle from lat/lon (reuse existing helper).

**4. Sync = Track, per entity, 90 days.**
`POST /sync/{port|chokepoint}/{id}` queries the daily layer `where date >= (maxDate - 90d) AND portid = X`, upserts metrics, sets `is_tracked=true`. The old global `/sync/all` daily collector is repurposed to the beat refresh (latest day, tracked only). The daily-metrics portwatch collector drops the curated map and iterates tracked portids (chunking the `IN (...)` clause to stay under ArcGIS where-length limits).

**5. Tracked-only scope falls out of the data.**
Scoring iterates entities present in `port_watch_metric`; since metrics exist only for tracked entities, scoring is naturally tracked-only. News explicitly filters `is_tracked=true`.

## Risks / Trade-offs

- **BREAKING entity_id change orphans existing metrics keyed by locode** → migration deletes/ignores legacy `portwatch` port metrics (dev data); fresh sync repopulates by `portid`.
- **ArcGIS `IN (...)` / URL length limits on large tracked sets** → chunk portids (~100/req) in the daily refresh.
- **Catalog ingest is ~3 paged calls + 28 chokepoints; cheap, but master schema could change** → ingest tolerates missing optional fields and logs per-feature errors without aborting.
- **Geometry circle is an approximation for chokepoints** → acceptable; only used for map display, not analytics.
- **`q` search on 2065 rows** → simple `ILIKE` on indexed name/country; dataset is small enough to not need full-text.

## Migration Plan

1. Alembic `0004`: add `portid`/`chokepointid` (unique, nullable→backfill→not null) + `is_tracked` (default false) to `ports`/`chokepoints`.
2. Run catalog ingest to populate metadata for all entities.
3. Backfill: mark the known 14 ports + 8 chokepoints `is_tracked=true`; map them to their portids (one-time, from the curated list already verified).
4. Rework `seed_dev` to: catalog ingest → mark known set tracked → optional synthetic metrics for dev.
5. Rollback: drop the new columns; revert collector/service files. Legacy locode-keyed flow is replaced, not removed from history.

## Open Questions

- None blocking. Optional later: cap the number of tracked entities and surface a warning in the UI; periodic (weekly beat) catalog re-sync instead of manual.
