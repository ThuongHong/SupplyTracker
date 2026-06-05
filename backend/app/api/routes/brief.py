from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import DbSession, RedisClient
from app.db.models import Chokepoint, Insight, Port, RiskStoryEvent
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


def _chokepoint_slug(name: str) -> str:
    """Chokepoint events key off a lowercase name slug (collector convention),
    not the ``chokepointid`` business key."""
    return name.lower().replace(" ", "_")


def _tracked_entity_ids(db: Session) -> set[str]:
    """Return the ``entity_id`` values used by events/insights for tracked entities.

    Ports use the ``portid`` business key; chokepoints use a name slug. This set
    is what scopes the brief to what the user is actually tracking.
    """
    port_ids = db.query(Port.portid).filter(Port.is_tracked.is_(True)).all()
    chokepoint_names = (
        db.query(Chokepoint.name).filter(Chokepoint.is_tracked.is_(True)).all()
    )
    ids = {row[0] for row in port_ids}
    ids |= {_chokepoint_slug(row[0]) for row in chokepoint_names}
    return ids


def _insight_in_scope(insight: Insight, tracked: set[str]) -> bool:
    """True if any of the insight's affected entities is currently tracked."""
    for entity in insight.affected_entities or []:
        if entity.get("id") in tracked:
            return True
    return False


@router.get("/brief", response_model=BriefResponse)
def get_brief(db: DbSession, redis_client: RedisClient) -> BriefResponse:
    """Return the executive Decision Brief as markdown, scoped to tracked entities."""
    today = date.today().isoformat()

    tracked = _tracked_entity_ids(db)
    if not tracked:
        return BriefResponse(brief=_STEADY_BRIEF, as_of=today)

    top_events = (
        db.query(RiskStoryEvent)
        .filter(RiskStoryEvent.entity_id.in_(tracked))
        .order_by(desc(RiskStoryEvent.event_time))
        .limit(_MAX_EVENTS)
        .all()
    )
    # Insights carry affected entities in a JSONB list, so scope them in Python.
    recent_insights = (
        db.query(Insight)
        .order_by(desc(Insight.generated_at))
        .limit(_MAX_INSIGHTS * 4)
        .all()
    )
    top_insights = [i for i in recent_insights if _insight_in_scope(i, tracked)][
        :_MAX_INSIGHTS
    ]

    if not top_events and not top_insights:
        # Quiet day: no transition events. Brief the standing risk posture so a
        # tracked entity sitting at high/critical still headlines a real brief
        # instead of the generic steady line.
        from app.api.routes.risk import _get_latest_scores

        standing = [
            s
            for s in _get_latest_scores(db)
            if s.entity_id in tracked and s.severity in {"high", "critical"}
        ][:_MAX_EVENTS]
        if not standing:
            return BriefResponse(brief=_STEADY_BRIEF, as_of=today)
        brief = get_decision_brief(db, redis_client, [], [], standing_risks=standing)
        return BriefResponse(brief=brief, as_of=today)

    brief = get_decision_brief(db, redis_client, top_events, top_insights)
    return BriefResponse(brief=brief, as_of=today)
