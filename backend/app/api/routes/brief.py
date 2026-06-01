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

# Deterministic fallback for a fresh/quiet DB. Skips the LLM entirely so an empty
# prompt can never produce a refusal ("required data is not present") in the hero.
_STEADY_BRIEF = (
    "Global supply chain risk opens **steady**, with no critical watchpoints "
    "across ports and arteries this session."
)


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

    if not top_events and not top_insights:
        return BriefResponse(brief=_STEADY_BRIEF, as_of=date.today().isoformat())

    brief = get_decision_brief(db, redis_client, top_events, top_insights)
    return BriefResponse(brief=brief, as_of=date.today().isoformat())
