from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Path

from app.api.deps import AuthRequired, DbSession
from app.collectors.portwatch import PortWatchCollector
from app.db.models import Chokepoint, Port
from app.schemas.sync import EntitySyncResponse, SyncResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])

_VALID_SOURCES = {"portwatch", "fred", "fbx", "wci", "bunker", "news", "catalog", "all"}


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
