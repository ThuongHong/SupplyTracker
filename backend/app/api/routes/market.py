from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.services.market import build_market_insights

router = APIRouter(tags=["market"])


@router.get("/market/insights")
def get_market_insights(
    db: DbSession,
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
) -> dict[str, Any]:
    """Growth & Market Insights for tracked entities.

    The ``as_of`` field (latest port metric timestamp) lets the client cache and
    only refetch when newer data exists.
    """
    return build_market_insights(db, window)
