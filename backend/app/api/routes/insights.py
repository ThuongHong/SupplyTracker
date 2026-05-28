from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from sqlalchemy import desc

from app.api.deps import DbSession
from app.db.models import Insight
from app.schemas.insights import InsightItem, InsightsResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["insights"])


@router.get("/insights", response_model=InsightsResponse)
def list_insights(
    db: DbSession,
    attention_level: str | None = Query(None, description="Filter by attention_level"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of insights to return"),
) -> InsightsResponse:
    """List insights, optionally filtered by attention_level."""
    q = db.query(Insight).order_by(desc(Insight.generated_at))

    if attention_level is not None:
        q = q.filter(Insight.attention_level == attention_level)

    rows = q.limit(limit).all()

    items = [
        InsightItem(
            id=r.id,
            generated_at=r.generated_at,
            category=r.category,
            title=r.title,
            narrative=r.narrative,
            narrative_llm=r.narrative_llm,
            narrative_model=r.narrative_model,
            narrative_generated_at=r.narrative_generated_at,
            metrics=r.metrics,
            priority=r.priority,
            event_type=r.event_type,
            confidence=r.confidence,
            affected_entities=r.affected_entities,
            source_metrics=r.source_metrics,
            attention_level=r.attention_level,
        )
        for r in rows
    ]

    return InsightsResponse(items=items, count=len(items))
