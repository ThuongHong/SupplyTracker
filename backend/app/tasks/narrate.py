from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from celery import shared_task

from app.db.models import Insight, LLMUsageLog
from app.db.session import get_db
from app.llm.client import LLMResponse, chat_completion
from app.llm.prompts import NARRATIVE_SYSTEM, build_messages

logger = logging.getLogger(__name__)

_COMMIT_BATCH_SIZE = 5


@shared_task(name="narrate.fill_narratives")
def fill_narratives(batch_size: int = 20) -> dict[str, Any]:
    """Fill narrative_llm for up to batch_size insights that lack one."""
    processed = 0
    errors = 0

    db_gen = get_db()
    session = next(db_gen)
    try:
        insights = (
            session.query(Insight)
            .filter(Insight.narrative_llm.is_(None))
            .limit(batch_size)
            .all()
        )

        for i, insight in enumerate(insights):
            try:
                user_prompt = (
                    f"Insight title: {insight.title}\n\n"
                    f"Structured narrative:\n{insight.narrative}\n\n"
                    "Please write an enhanced, readable narrative for this insight."
                )
                messages = build_messages(NARRATIVE_SYSTEM, user_prompt)
                response: LLMResponse = chat_completion(messages, stream=False)  # type: ignore[assignment]

                insight.narrative_llm = response.content
                insight.narrative_model = response.model
                insight.narrative_generated_at = datetime.now(tz=UTC)

                log = LLMUsageLog(
                    feature="narrative",
                    model=response.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    duration_ms=response.duration_ms,
                    status="ok",
                )
                session.add(log)
                processed += 1

            except Exception:
                logger.exception("Error generating narrative for insight id=%s", insight.id)
                errors += 1

            # Commit in batches of 5
            if (i + 1) % _COMMIT_BATCH_SIZE == 0:
                session.commit()

        # Final commit for remainder
        session.commit()

    except Exception:
        logger.exception("Fatal error in fill_narratives task")
        session.rollback()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    return {"processed": processed, "errors": errors}
