from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import LLMUsageLog
from app.llm.client import chat_completion
from app.llm.grounding import build_grounding_context
from app.llm.prompts import CHATBOT_SYSTEM, build_messages
from app.llm.safety import validate_input

logger = logging.getLogger(__name__)

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
# Context normalisation
# ---------------------------------------------------------------------------


def _normalise_entity_context(
    raw: list[dict[str, Any]] | dict[str, Any],
) -> list[dict[str, Any]]:
    """Accept both a list (new shape) and a single dict (legacy); always return a list."""
    if isinstance(raw, dict):
        logger.warning(
            "entity_context received as single dict (deprecated); wrapping in list"
        )
        return [raw]
    return raw


# ---------------------------------------------------------------------------
# Context builder (delegates to grounding.py)
# ---------------------------------------------------------------------------


def _fetch_entity_context(session: Session, entity_context: list[dict[str, Any]]) -> str:
    """Build a rich grounded context string from the DB for each requested entity."""
    return build_grounding_context(session, entity_context)


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
    normalised = _normalise_entity_context(entity_context)
    context = _fetch_entity_context(session, normalised)

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
