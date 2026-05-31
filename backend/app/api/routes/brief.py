from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from sqlalchemy import desc

from app.api.deps import DbSession, RedisClient
from app.db.models import Insight, RiskStoryEvent
from app.llm.brief import get_decision_brief
from app.schemas.brief import BriefResponse

router = APIRouter(tags=["brief"])

_MAX_EVENTS = 10
_MAX_INSIGHTS = 10


@router.get("/brief", response_model=BriefResponse)
def get_brief(db: DbSession, redis_client: RedisClient) -> BriefResponse:
    """Return the executive Decision Brief as markdown."""
    top_events = (
        db.query(RiskStoryEvent)
        .order_by(desc(RiskStoryEvent.event_time))
        .limit(_MAX_EVENTS)
        .all()
    )
    top_insights = (
        db.query(Insight)
        .order_by(desc(Insight.generated_at))
        .limit(_MAX_INSIGHTS)
        .all()
    )

    brief = get_decision_brief(db, redis_client, top_events, top_insights)
    return BriefResponse(brief=brief, as_of=date.today().isoformat())
