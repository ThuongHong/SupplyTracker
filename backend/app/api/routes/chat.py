from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.api.deps import DbSession
from app.api.rate_limit import RateLimiter
from app.config import get_settings
from app.llm.chat import stream_chat_response
from app.schemas.chat import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Lazily initialised so settings are not read at import time (avoids issues in tests).
_chat_limiter: RateLimiter | None = None


def _get_chat_limiter() -> RateLimiter:
    global _chat_limiter
    if _chat_limiter is None:
        settings = get_settings()
        rpm = max(1, settings.chat_rate_limit_per_5min // 5)
        _chat_limiter = RateLimiter(requests_per_minute=rpm)
    return _chat_limiter


def _chat_rate_limit(request: Request) -> None:
    """FastAPI dependency: apply chat-specific rate limit."""
    _get_chat_limiter()(request)


@router.post("/chat")
def chat(
    body: ChatRequest,
    db: DbSession,
    _rate_limit: None = Depends(_chat_rate_limit),
) -> EventSourceResponse:
    """Stream a chat response as Server-Sent Events."""

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        # stream_chat_response is a sync generator doing blocking I/O (LLM HTTP calls).
        # Drive it via run_in_executor so the event loop is never blocked.
        loop = asyncio.get_event_loop()
        sync_gen = stream_chat_response(db, body.message, body.entity_context)

        def _get_next() -> tuple[str | None, bool]:
            try:
                return next(sync_gen), False
            except StopIteration:
                return None, True

        while True:
            chunk, done = await loop.run_in_executor(None, _get_next)
            if done:
                break
            yield {"data": chunk}
        yield {"data": "[DONE]"}

    return EventSourceResponse(event_generator())
