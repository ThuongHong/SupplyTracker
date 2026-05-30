from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy import desc

from app.api.deps import DbSession
from app.db.models import Chokepoint, NewsItem, Port
from app.schemas.news import NewsItemSchema, NewsListResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["news"])

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 20
_VALID_ENTITY_TYPES = {"port", "chokepoint"}


def _resolve_news_entity_id(db: DbSession, entity_type: str, raw_id: str) -> str | None:
    """Map a path id (portid / chokepointid) to the entity_id stored in news_item.

    Mirrors the resolution used by the ports/chokepoints routes so the read path
    matches what the GoogleNewsCollector writes:
      - port:       news entity_id == port.portid
      - chokepoint: news entity_id == cp.name.lower().replace(" ", "_")
    """
    if entity_type == "port":
        port = db.query(Port).filter(Port.portid == raw_id).first()
        if port is None and raw_id.isdigit():
            port = db.query(Port).filter(Port.id == int(raw_id)).first()
        return port.portid if port else None

    cp = db.query(Chokepoint).filter(Chokepoint.chokepointid == raw_id).first()
    if cp is None and raw_id.isdigit():
        cp = db.query(Chokepoint).filter(Chokepoint.id == int(raw_id)).first()
    if cp is None:
        # Accept the slug form directly (collector / lane-map convention).
        cp = next(
            (
                c
                for c in db.query(Chokepoint).all()
                if c.name.lower().replace(" ", "_") == raw_id
            ),
            None,
        )
    return cp.name.lower().replace(" ", "_") if cp else None


@router.get(
    "/entities/{entity_type}/{entity_id}/news",
    response_model=NewsListResponse,
)
def list_entity_news(
    db: DbSession,
    entity_type: str = Path(description="Entity type: 'port' or 'chokepoint'"),
    entity_id: str = Path(description="Entity identifier (portid for ports, chokepointid for chokepoints)"),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, description="Maximum number of items to return (capped at 100)"),
    since: datetime | None = Query(  # noqa: B008
        None,
        description="ISO 8601 datetime cursor — return news published after this time",
    ),
) -> NewsListResponse:
    """Return news items for a given entity, ordered by published_at descending."""
    if entity_type not in _VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid entity_type '{entity_type}'. Must be one of: {sorted(_VALID_ENTITY_TYPES)}",
        )

    news_entity_id = _resolve_news_entity_id(db, entity_type, entity_id)
    if news_entity_id is None:
        raise HTTPException(
            status_code=404,
            detail=f"{entity_type.capitalize()} '{entity_id}' not found",
        )

    limit = min(limit, _MAX_LIMIT)

    q = (
        db.query(NewsItem)
        .filter(
            NewsItem.entity_type == entity_type,
            NewsItem.entity_id == news_entity_id,
        )
        .order_by(desc(NewsItem.published_at))
    )

    if since is not None:
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        q = q.filter(NewsItem.published_at > since)

    rows = q.limit(limit).all()

    items = [
        NewsItemSchema(
            id=r.id,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            url=r.url,
            title=r.title,
            source=r.source,
            published_at=r.published_at,
            summary=r.summary,
            language=r.language,
            fetched_at=r.fetched_at,
        )
        for r in rows
    ]

    return NewsListResponse(items=items, count=len(items))
