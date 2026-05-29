## 1. Data model + migration

- [x] 1.1 Add `portid` (String, unique, not null) + `is_tracked` (bool, default false) to `Port`; add `chokepointid` (String, unique) + `is_tracked` to `Chokepoint` in `app/db/models.py`
- [x] 1.2 Write Alembic migration `0004` adding the columns (nullable → backfill → not-null for the id columns)
- [x] 1.3 Verify migration upgrades and downgrades cleanly against a fresh DB

## 2. Catalog ingest (metadata only)

- [x] 2.1 Create `app/collectors/catalog.py` paging `PortWatch_ports_database` (1000/page via `resultOffset`) and upserting portid/name/country/POINT geom — no metric calls
- [x] 2.2 Add chokepoint ingest from `PortWatch_chokepoints_database`, synthesizing a circle POLYGON from lat/lon (reuse `_circle_polygon_wkt`)
- [x] 2.3 Make ingest idempotent on portid/chokepointid and never reset `is_tracked`; log per-feature errors without aborting
- [x] 2.4 Add `collect_catalog` Celery task + `POST /sync/catalog` endpoint (bearer-protected) + `make catalog` target
- [x] 2.5 Unit tests: paging beyond 1000, idempotent re-sync preserves tracking, chokepoint geom synthesized

## 3. Switch port entity_id to portid

- [x] 3.1 Rewrite `app/collectors/portwatch.py`: drop curated map; daily refresh iterates `is_tracked` portids (chunk `IN (...)`), writes port metrics with `entity_id = portid`
- [x] 3.2 Update `app/services/dashboard.py` to join ports by `portid`
- [x] 3.3 Update `app/api/routes/ports.py` detail/metrics routes to resolve by `portid`
- [x] 3.4 Update `app/collectors/google_news.py` to use `portid` as port entity_id and query only `is_tracked` entities
- [x] 3.5 Update existing portwatch/dashboard/news tests for the portid entity_id

## 4. Per-entity sync = track (90 days)

- [x] 4.1 Add `POST /sync/port/{portid}` + `POST /sync/chokepoint/{chokepointid}` (bearer-protected): 404 on unknown id, 401 on missing token
- [x] 4.2 Implement 90-day fetch (`where date >= maxDate-90d AND portid=X`) upserting metrics, then set `is_tracked=true`
- [x] 4.3 Add untrack endpoint(s) clearing `is_tracked` while retaining metrics
- [x] 4.4 Tests: 90-day backfill + track, unknown id 404, untrack keeps metrics

## 5. Daily beat refresh of tracked

- [x] 5.1 Repurpose the daily portwatch beat task to append the latest day for `is_tracked` entities only; update `app/tasks/schedule.py`
- [x] 5.2 Confirm scoring runs tracked-only (metrics exist only for tracked) and news beat filters tracked
- [x] 5.3 Test: beat fetches latest day for tracked only, untracked get no rows

## 6. List APIs: search + tracked filter

- [x] 6.1 Extend `GET /ports` with `q` (ILIKE name/country) + `tracked` bool; keep pagination/has_more
- [x] 6.2 Extend `GET /chokepoints` with the same `q` + `tracked` params
- [x] 6.3 Tests: search match, tracked filter, untracked paging

## 7. Frontend: tracked / browse-all tabs

- [ ] 7.1 Extend `frontend/src/api/ports.ts` + `chokepoints.ts` with `q`/`tracked` params and sync/track/untrack calls
- [ ] 7.2 Build Tracked / Browse-all tabbed catalog browser (lazy paged list + search input) for ports
- [ ] 7.3 Add per-row Sync (untracked) and Untrack (tracked) buttons wired to the endpoints; reuse for chokepoints
- [ ] 7.4 Vitest coverage for the catalog browser (tab switch, search, sync/untrack actions)

## 8. Seed + migration data

- [ ] 8.1 Rework `app/scripts/seed_dev.py`: run catalog ingest → mark known 14 ports + 8 chokepoints `is_tracked=true` with their portids → optional synthetic metrics
- [ ] 8.2 One-time backfill step (script or migration data) mapping the known set to portids
- [ ] 8.3 Drop/ignore legacy locode-keyed `portwatch` port metrics; re-sync repopulates by portid

## 9. Verify end-to-end

- [ ] 9.1 Run catalog ingest; confirm ~2065 ports + 28 chokepoints metadata, zero metric rows written
- [ ] 9.2 Sync one port + one chokepoint; confirm 90 days of metrics + `is_tracked=true` + dashboard renders
- [ ] 9.3 Full `pytest`, `ruff`, `mypy` green; frontend `vitest` green
