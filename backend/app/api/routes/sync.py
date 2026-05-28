from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Path

from app.api.deps import AuthRequired
from app.schemas.sync import SyncResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])

_VALID_SOURCES = {"portwatch", "fred", "fbx", "wci", "bunker", "all"}


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
        collect_fbx,
        collect_fred,
        collect_portwatch,
        collect_wci,
    )

    task_map = {
        "portwatch": collect_portwatch,
        "fred": collect_fred,
        "fbx": collect_fbx,
        "wci": collect_wci,
        "bunker": collect_bunker,
        "all": collect_all,
    }

    task_fn = task_map[source]
    result = task_fn.delay()

    logger.info("Triggered sync task '%s' — task_id=%s", source, result.id)

    return SyncResponse(task_id=result.id, source=source)
