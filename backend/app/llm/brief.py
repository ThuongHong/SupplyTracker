from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import redis as redis_lib
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Insight, LLMUsageLog, RiskStoryEvent
from app.llm.client import LLMResponse, chat_completion
from app.llm.prompts import DECISION_BRIEF_SYSTEM, build_messages

# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------


def _cache_key(
    top_events: list[RiskStoryEvent], standing_risks: list[Any] | None = None
) -> str:
    today = date.today().isoformat()
    parts = sorted(str(e.event_key) for e in top_events)
    # On a quiet (no-event) day the brief is driven by standing risk instead, so
    # the cache must key off those entities/severities or every quiet day collides.
    if standing_risks:
        parts += sorted(
            f"{s.entity_type}:{s.entity_id}:{s.severity}" for s in standing_risks
        )
    events_hash = hashlib.md5(":".join(parts).encode()).hexdigest()[:8]
    return f"brief:{today}:{events_hash}"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_brief_prompt(
    top_events: list[RiskStoryEvent],
    top_insights: list[Insight],
    standing_risks: list[Any] | None = None,
) -> str:
    lines: list[str] = ["Top risk events:"]
    for event in top_events:
        lines.append(
            f"  - [{event.severity.upper()}] {event.entity_name} ({event.entity_type}): "
            f"{event.event_type} — {event.narrative}"
        )

    lines.append("\nTop insights:")
    for insight in top_insights:
        lines.append(f"  - [{insight.attention_level or 'N/A'}] {insight.title}: {insight.narrative}")

    # Quiet day: no new events/insights, but some tracked entities are still
    # sitting at high/critical risk. Brief the current posture so the executive
    # summary reflects reality instead of a generic "steady" line.
    if standing_risks:
        lines.append(
            "\nNo new risk events today. Current standing risk posture for "
            "tracked entities (score 0–1):"
        )
        for s in standing_risks:
            score = f"{s.score:.2f}" if s.score is not None else "n/a"
            lines.append(
                f"  - [{(s.severity or 'unknown').upper()}] {s.entity_name} "
                f"({s.entity_type}): risk score {score}"
            )

    lines.append("\nPlease generate a concise executive Decision Brief based on the above data.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def get_decision_brief(
    session: Session,
    redis_client: redis_lib.Redis,
    top_events: list[RiskStoryEvent],
    top_insights: list[Insight],
    standing_risks: list[Any] | None = None,
) -> str:
    """Return a cached or freshly generated Decision Brief string.

    ``standing_risks`` is used on quiet days (no events/insights) to brief the
    current high/critical risk posture instead of a generic steady line.
    """
    settings = get_settings()
    cache_key = _cache_key(top_events, standing_risks)

    # Cache hit
    cached = redis_client.get(cache_key)
    if cached is not None:
        if isinstance(cached, bytes):
            return cached.decode("utf-8")
        return str(cached)

    # Cache miss — generate
    user_prompt = _build_brief_prompt(top_events, top_insights, standing_risks)
    messages = build_messages(DECISION_BRIEF_SYSTEM, user_prompt)

    response: LLMResponse = chat_completion(messages, stream=False)  # type: ignore[assignment]

    # Cache result
    redis_client.setex(cache_key, settings.decision_brief_cache_ttl_s, response.content)

    # Persist usage log
    log = LLMUsageLog(
        feature="decision_brief",
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        duration_ms=response.duration_ms,
        status="ok",
    )
    session.add(log)
    session.commit()

    return response.content
