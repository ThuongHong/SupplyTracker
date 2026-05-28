from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import ChokepointRiskScore, LLMUsageLog, PortRiskScore, RiskStoryEvent
from app.llm.client import chat_completion
from app.llm.prompts import CHATBOT_SYSTEM, build_messages
from app.llm.safety import validate_input

# ---------------------------------------------------------------------------
# Refusal / error messages
# ---------------------------------------------------------------------------

_BLOCKED_REFUSAL = (
    "I'm sorry, but I can't process that request. "
    "Please ask a question related to maritime supply chain risk analysis."
)

_ERROR_MESSAGE = (
    "I encountered an error while processing your request. "
    "Please try again in a moment."
)

# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def _fetch_entity_context(session: Session, entity_context: list[dict[str, Any]]) -> str:
    """Build a grounded context string from the DB for each requested entity."""
    lines: list[str] = []

    for entity in entity_context:
        entity_type = entity.get("type", "")
        entity_id = entity.get("id", "")
        risk_row: PortRiskScore | ChokepointRiskScore | None = None

        if entity_type == "port":
            risk_row = (
                session.query(PortRiskScore)
                .filter(PortRiskScore.entity_id == entity_id)
                .order_by(desc(PortRiskScore.as_of))
                .first()
            )
            if risk_row:
                lines.append(
                    f"Port '{risk_row.entity_name}' (id={entity_id}): "
                    f"risk_score={risk_row.score}, severity={risk_row.severity}, "
                    f"as_of={risk_row.as_of.isoformat()}"
                )
            else:
                lines.append(f"Port id={entity_id}: no risk score data available.")

        elif entity_type == "chokepoint":
            risk_row = (
                session.query(ChokepointRiskScore)
                .filter(ChokepointRiskScore.entity_id == entity_id)
                .order_by(desc(ChokepointRiskScore.as_of))
                .first()
            )
            if risk_row:
                lines.append(
                    f"Chokepoint '{risk_row.entity_name}' (id={entity_id}): "
                    f"risk_score={risk_row.score}, severity={risk_row.severity}, "
                    f"as_of={risk_row.as_of.isoformat()}"
                )
            else:
                lines.append(f"Chokepoint id={entity_id}: no risk score data available.")

        # Recent events (up to 3) for this entity regardless of type
        events = (
            session.query(RiskStoryEvent)
            .filter(
                RiskStoryEvent.entity_id == entity_id,
                RiskStoryEvent.entity_type == entity_type,
            )
            .order_by(desc(RiskStoryEvent.event_time))
            .limit(3)
            .all()
        )
        if events:
            lines.append(f"  Recent events for {entity_type} id={entity_id}:")
            for ev in events:
                lines.append(
                    f"    - [{ev.severity}] {ev.event_type} at {ev.event_time.isoformat()}: "
                    f"{ev.narrative}"
                )

    return "\n".join(lines) if lines else "No entity context data available."


# ---------------------------------------------------------------------------
# Public streaming function
# ---------------------------------------------------------------------------


def stream_chat_response(
    session: Session,
    user_message: str,
    entity_context: list[dict[str, Any]],
) -> Generator[str, None, None]:
    """Validate input, build grounded context, stream LLM response as SSE chunks."""

    # 1. Safety check
    ok, reason = validate_input(user_message)
    if not ok:
        log = LLMUsageLog(
            feature="chat",
            model="none",
            input_tokens=None,
            output_tokens=None,
            duration_ms=None,
            status="blocked_input",
            error=reason,
        )
        session.add(log)
        session.commit()
        yield _BLOCKED_REFUSAL
        return

    # 2. Build grounded context
    context = _fetch_entity_context(session, entity_context)

    # 3. Build messages
    messages = build_messages(CHATBOT_SYSTEM, user_message, context)

    # 4. Stream LLM response
    try:
        stream = chat_completion(messages, stream=True)
        yield from stream  # type: ignore[misc]

        # 5. Write usage log (no token counts for streaming)
        log = LLMUsageLog(
            feature="chat",
            model="streaming",
            input_tokens=None,
            output_tokens=None,
            duration_ms=None,
            status="ok",
        )
        session.add(log)
        session.commit()

    except Exception as exc:
        error_log = LLMUsageLog(
            feature="chat",
            model="streaming",
            input_tokens=None,
            output_tokens=None,
            duration_ms=None,
            status="error",
            error=str(exc)[:500],
        )
        session.add(error_log)
        session.commit()
        yield _ERROR_MESSAGE
