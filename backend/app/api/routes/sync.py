from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.deps import AuthRequired, DbSession
from app.collectors.portwatch import PortWatchCollector
from app.db.models import Chokepoint, Port
from app.schemas.sync import EntitySyncResponse, SyncResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])

_VALID_SOURCES = {"portwatch", "fred", "fbx", "wci", "bunker", "news", "catalog", "all"}

# Jobs the /cron/run endpoint can run, in dependency order (collect → score →
# forecast → narrate). Mirrors what celery-beat schedules, for workerless
# deploys where an external cron drives the pipeline instead.
#
# "backfill" is a one-off: it scores every entity for each of the last ``days``
# days so the risk-trend chart has history (normal scoring only writes today's
# snapshot). It is NOT in the default jobs string — request it explicitly with
# ?jobs=backfill — so a daily cron never re-runs the expensive sweep.
_VALID_CRON_JOBS = ("backfill", "collect", "score", "forecast", "narrate")


@router.post("/sync/{source}", response_model=SyncResponse)
def trigger_sync(
    _auth: AuthRequired,
    source: str = Path(description="One of: portwatch, fred, fbx, wci, bunker, all"),
) -> SyncResponse:
    """Trigger a Celery collection task for the given source (bearer-protected)."""
    if source not in _VALID_SOURCES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown source '{source}'. Valid sources: {sorted(_VALID_SOURCES)}",
        )

    from app.tasks.collect import (
        collect_all,
        collect_bunker,
        collect_catalog,
        collect_fbx,
        collect_fred,
        collect_news,
        collect_portwatch,
        collect_wci,
    )

    task_map = {
        "portwatch": collect_portwatch,
        "fred": collect_fred,
        "fbx": collect_fbx,
        "wci": collect_wci,
        "bunker": collect_bunker,
        "news": collect_news,
        "catalog": collect_catalog,
        "all": collect_all,
    }

    task_fn = task_map[source]
    result = task_fn.delay()

    logger.info("Triggered sync task '%s' — task_id=%s", source, result.id)

    return SyncResponse(task_id=result.id, source=source)


# ── Cron driver (workerless deploys) ─────────────────────────────────────────


def _run_backfill(days: int) -> dict[str, Any]:
    """Score every entity for each of the last ``days`` days.

    Normal scoring (`score.run_pipeline`) only writes a snapshot for *today*, so
    the risk-trend chart starts life with a single point. This sweep replays the
    scorer date-by-date — `score_entity` upserts `RiskFeatureSnapshot` keyed by
    `(snapshot_date, entity_type, entity_id)` and baselines are point-in-time
    (data ≤ as_of), so each historical day gets a valid snapshot.
    """
    from datetime import date, timedelta

    from app.analysis.scoring import load_components, score_entity
    from app.db.models import PortWatchMetric
    from app.db.session import get_db

    db_gen = get_db()
    session = next(db_gen)
    try:
        components, _ = load_components()
        entities = (
            session.query(
                PortWatchMetric.entity_type,
                PortWatchMetric.entity_id,
                PortWatchMetric.entity_name,
            )
            .distinct()
            .all()
        )

        today = date.today()
        start = today - timedelta(days=max(days - 1, 0))
        snapshots = 0
        errors = 0
        day = start
        while day <= today:
            for entity_type, entity_id, entity_name in entities:
                try:
                    score_entity(
                        session, entity_type, entity_id, entity_name, day, components
                    )
                    snapshots += 1
                except Exception:
                    logger.exception(
                        "backfill score_entity failed for %s/%s on %s",
                        entity_type,
                        entity_id,
                        day,
                    )
                    errors += 1
            session.commit()  # commit per day to keep transactions short
            day += timedelta(days=1)

        return {
            "days": days,
            "entities": len(entities),
            "snapshots_written": snapshots,
            "errors": errors,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


@router.post("/cron/run")
def cron_run(
    _auth: AuthRequired,
    jobs: str = Query(
        "collect,score,forecast,narrate",
        description=(
            "Comma-separated subset of: backfill, collect, score, forecast, "
            "narrate. 'backfill' is a one-off historical risk-score sweep."
        ),
    ),
    days: int = Query(
        90,
        ge=1,
        le=365,
        description="Lookback window (days) for the 'backfill' job.",
    ),
) -> dict[str, Any]:
    """Run the data pipeline synchronously — the workerless replacement for
    celery-beat. An external scheduler (cron-job.org, GitHub Actions, …) hits
    this with the Bearer token. Each task runs via ``.apply()`` so it executes
    in-process regardless of the eager flag; set ``CELERY_TASK_ALWAYS_EAGER=true``
    so nested ``.delay()`` calls inside the pipeline also run inline.
    """
    requested = [j.strip() for j in jobs.split(",") if j.strip()]
    unknown = [j for j in requested if j not in _VALID_CRON_JOBS]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown job(s) {unknown}. Valid: {list(_VALID_CRON_JOBS)}",
        )
    # Preserve dependency order regardless of how the caller ordered them.
    ordered = [j for j in _VALID_CRON_JOBS if j in requested]

    from app.tasks.collect import (
        collect_bunker,
        collect_fbx,
        collect_fred,
        collect_news,
        collect_portwatch,
        collect_wci,
    )
    from app.tasks.forecast import run_forecast
    from app.tasks.narrate import fill_narratives
    from app.tasks.score import run_pipeline

    results: dict[str, Any] = {}
    for job in ordered:
        try:
            if job == "backfill":
                results["backfill"] = _run_backfill(days)
            elif job == "collect":
                results["collect"] = {
                    name: task.apply().result
                    for name, task in (
                        ("portwatch", collect_portwatch),
                        ("fred", collect_fred),
                        ("fbx", collect_fbx),
                        ("wci", collect_wci),
                        ("bunker", collect_bunker),
                        ("news", collect_news),
                    )
                }
            elif job == "score":
                results["score"] = run_pipeline.apply().result
            elif job == "forecast":
                results["forecast"] = run_forecast.apply().result
            elif job == "narrate":
                results["narrate"] = fill_narratives.apply().result
            logger.info("cron_run job '%s' done", job)
        except Exception as exc:  # noqa: BLE001 — report per-job, keep going
            logger.exception("cron_run job '%s' failed", job)
            results[job] = {"error": str(exc)}

    return {"ran": ordered, "results": results}


# ── Per-entity sync = track (90-day backfill) ────────────────────────────────


@router.post("/sync/port/{portid}", response_model=EntitySyncResponse)
def sync_port(_auth: AuthRequired, db: DbSession, portid: str) -> EntitySyncResponse:
    """Fetch 90 days of data for one port and mark it tracked."""
    port = db.query(Port).filter(Port.portid == portid).first()
    if port is None:
        raise HTTPException(status_code=404, detail=f"Unknown portid '{portid}'")

    result = PortWatchCollector().sync_port(db, port.portid, port.name)
    port.is_tracked = True
    db.commit()
    from app.analysis.entity_pipeline import score_and_forecast_entity
    score_and_forecast_entity(db, "port", port.portid, port.name)
    logger.info("Synced port %s — rows=%d", portid, result.rows)
    return EntitySyncResponse(
        entity_type="port",
        entity_id=portid,
        rows=result.rows,
        is_tracked=True,
        errors=result.errors,
    )


@router.post("/sync/chokepoint/{chokepointid}", response_model=EntitySyncResponse)
def sync_chokepoint(
    _auth: AuthRequired, db: DbSession, chokepointid: str
) -> EntitySyncResponse:
    """Fetch 90 days of data for one chokepoint and mark it tracked."""
    cp = db.query(Chokepoint).filter(Chokepoint.chokepointid == chokepointid).first()
    if cp is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown chokepointid '{chokepointid}'"
        )

    result = PortWatchCollector().sync_chokepoint(db, cp.chokepointid, cp.name)
    cp.is_tracked = True
    db.commit()
    from app.analysis.entity_pipeline import score_and_forecast_entity
    # Chokepoint scoring keys off the lowercase-slug entity_id (collector convention).
    score_and_forecast_entity(
        db, "chokepoint", cp.name.lower().replace(" ", "_"), cp.name
    )
    logger.info("Synced chokepoint %s — rows=%d", chokepointid, result.rows)
    return EntitySyncResponse(
        entity_type="chokepoint",
        entity_id=chokepointid,
        rows=result.rows,
        is_tracked=True,
        errors=result.errors,
    )


# ── Untrack (keeps existing metrics) ─────────────────────────────────────────


@router.post("/untrack/port/{portid}", response_model=EntitySyncResponse)
def untrack_port(_auth: AuthRequired, db: DbSession, portid: str) -> EntitySyncResponse:
    port = db.query(Port).filter(Port.portid == portid).first()
    if port is None:
        raise HTTPException(status_code=404, detail=f"Unknown portid '{portid}'")
    port.is_tracked = False
    db.commit()
    return EntitySyncResponse(
        entity_type="port", entity_id=portid, rows=0, is_tracked=False
    )


@router.post("/untrack/chokepoint/{chokepointid}", response_model=EntitySyncResponse)
def untrack_chokepoint(
    _auth: AuthRequired, db: DbSession, chokepointid: str
) -> EntitySyncResponse:
    cp = db.query(Chokepoint).filter(Chokepoint.chokepointid == chokepointid).first()
    if cp is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown chokepointid '{chokepointid}'"
        )
    cp.is_tracked = False
    db.commit()
    return EntitySyncResponse(
        entity_type="chokepoint", entity_id=chokepointid, rows=0, is_tracked=False
    )
