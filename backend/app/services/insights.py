from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.scoring import is_adverse_deviation
from app.db.models import Insight, RiskStoryEvent

_HIGH_ATTENTION = {"high", "medium"}


def materialize_insights(
    session: Session,
    events: list[RiskStoryEvent],
) -> list[Insight]:
    """Create Insight rows for events with attention_level in {"high", "medium"}.

    Skips creation if an Insight for the same (entity_id, event_type) already
    exists within the last 24 hours to prevent spam.

    Returns the list of newly created Insight rows.
    """
    created: list[Insight] = []
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(hours=24)

    for event in events:
        if event.attention_level not in _HIGH_ATTENTION:
            continue

        # Fix #8: replace fragile JSONB containment query with a simpler
        # event_type + generated_at dedup check that avoids multi-key JSONB issues.
        stmt = select(Insight).where(
            Insight.event_type == event.event_type,
            Insight.generated_at >= cutoff,
        )
        existing = session.execute(stmt).scalars().first()
        # Narrow to the same entity_id via Python check on affected_entities
        if existing is not None:
            entities = existing.affected_entities or []
            if any(e.get("id") == event.entity_id for e in entities):
                continue

        title = _build_title(event)
        narrative = event.narrative

        insight = Insight(
            title=title,
            narrative=narrative,
            attention_level=event.attention_level,
            event_type=event.event_type,
            category="risk",
            affected_entities=[
                {"type": event.entity_type, "id": event.entity_id}
            ],
            confidence=event.confidence,
            source_metrics={
                "metric": event.metric,
                "z_score": event.z_score,
                "observed": event.observed,
                "expected": event.expected,
            },
        )
        session.add(insight)
        created.append(insight)

    session.flush()
    return created


def _build_title(event: RiskStoryEvent) -> str:
    """Build a short, human-readable title string from the event.

    Uses the display name (e.g. "Qingdao") rather than the raw entity id
    ("port1188"), and humanizes the metric key ("port_calls" -> "port calls").
    """
    name = event.entity_name or event.entity_id
    metric = (event.metric or "").replace("_", " ")
    if event.event_type == "z_spike":
        z = event.z_score or 0.0
        move = "drop" if z < 0 else "surge"
        if is_adverse_deviation(event.metric or "", z):
            return f"Anomalous {move} in {metric} at {name}"
        return f"Favorable {move} in {metric} at {name}"
    if event.event_type == "severity_step_up":
        return f"Risk severity escalated at {name}"
    if event.event_type == "severity_step_down":
        return f"Risk severity reduced at {name}"
    if event.event_type == "sustained_streak":
        return f"Sustained trend in {metric} at {name}"
    return f"Risk event at {name}: {event.event_type}"
