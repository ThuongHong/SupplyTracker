from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Path, Query, Response

from app.api.deps import DbSession
from app.schemas.dashboard import DashboardResponse, EntitySummaryResponse
from app.services.dashboard import (
    build_chokepoint_dashboard,
    build_entity_summary,
    build_port_dashboard,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

_VALID_ENTITY_TYPES = {"port", "chokepoint"}


@router.get(
    "/entities/{entity_type}/{entity_id}/dashboard",
    response_model=DashboardResponse,
)
def get_entity_dashboard(
    db: DbSession,
    response: Response,
    entity_type: str = Path(..., description="Entity type: 'port' or 'chokepoint'"),
    entity_id: str = Path(..., description="Entity identifier (locode for ports, slug for chokepoints)"),
    window: str = Query("30d", pattern="^(7d|30d|90d)$", description="Time window: 7d, 30d, or 90d"),
) -> DashboardResponse:
    """Return bundled chart payload for a port or chokepoint detail page."""
    if entity_type not in _VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid entity_type '{entity_type}'. Must be one of: {sorted(_VALID_ENTITY_TYPES)}",
        )

    if entity_type == "port":
        result = build_port_dashboard(db, entity_id, window)
    else:
        result = build_chokepoint_dashboard(db, entity_id, window)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"{entity_type.capitalize()} '{entity_id}' not found",
        )

    response.headers["Cache-Control"] = "public, max-age=300"
    return result


@router.get(
    "/entities/{entity_type}/{entity_id}/summary",
    response_model=EntitySummaryResponse,
)
def get_entity_summary(
    db: DbSession,
    entity_type: str = Path(..., description="Entity type: 'port' or 'chokepoint'"),
    entity_id: str = Path(..., description="Entity identifier (portid/locode for ports, slug for chokepoints)"),
    window: str = Query("30d", pattern="^(7d|30d|90d)$", description="Time window: 7d, 30d, or 90d"),
    force: bool = Query(False, description="Regenerate the LLM summary (e.g. after sync) instead of serving cache"),
) -> EntitySummaryResponse:
    """Return an AI summary + z-score anomaly stats for one entity's throughput."""
    if entity_type not in _VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid entity_type '{entity_type}'. Must be one of: {sorted(_VALID_ENTITY_TYPES)}",
        )

    result = build_entity_summary(db, entity_type, entity_id, window, force=force)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"{entity_type.capitalize()} '{entity_id}' not found",
        )
    return result
