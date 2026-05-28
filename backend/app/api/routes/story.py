from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from sqlalchemy import desc

from app.api.deps import DbSession
from app.db.models import RiskStoryEvent
from app.schemas.story import StoryEventItem, StoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["story"])

_MAX_EVENTS = 200


@router.get("/story", response_model=StoryResponse)
def list_story_events(
    db: DbSession,
    since: datetime | None = Query(  # noqa: B008
        None,
        description="ISO 8601 datetime cursor — return events after this time",
    ),
) -> StoryResponse:
    """Return story events ordered descending by event_time, capped at 200."""
    q = db.query(RiskStoryEvent).order_by(desc(RiskStoryEvent.event_time))

    if since is not None:
        # Normalise to UTC-aware if naive
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        q = q.filter(RiskStoryEvent.event_time > since)

    rows = q.limit(_MAX_EVENTS).all()

    items = [
        StoryEventItem(
            event_key=r.event_key,
            event_time=r.event_time,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            entity_name=r.entity_name,
            event_type=r.event_type,
            severity=r.severity,
            metric=r.metric,
            observed=r.observed,
            expected=r.expected,
            z_score=r.z_score,
            percent_change=r.percent_change,
            drivers=r.drivers,
            source_metrics=r.source_metrics,
            narrative=r.narrative,
            confidence=r.confidence,
            attention_level=r.attention_level,
            data_sufficiency=r.data_sufficiency,
            created_at=r.created_at,
        )
        for r in rows
    ]

    return StoryResponse(items=items, count=len(items))
