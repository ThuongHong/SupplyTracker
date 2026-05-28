from __future__ import annotations

import time
from collections.abc import Generator
from dataclasses import dataclass

import httpx
import openai

from app.config import get_settings

# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int


# ---------------------------------------------------------------------------
# Lazy client factory
# ---------------------------------------------------------------------------

_client: openai.OpenAI | None = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = openai.OpenAI(
            api_key=settings.dashscope_api_key.get_secret_value(),
            base_url=str(settings.dashscope_base_url),
            timeout=settings.llm_request_timeout_s,
        )
    return _client


# ---------------------------------------------------------------------------
# Transient error detection
# ---------------------------------------------------------------------------

def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, openai.APIConnectionError)):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code >= 500:
        return True
    return False


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def chat_completion(
    messages: list[dict[str, str]],
    *,
    stream: bool = False,
    model: str | None = None,
) -> LLMResponse | Generator[str, None, None]:
    """Call the LLM and return a response or a stream of content chunks.

    - Non-streaming: tries primary model, falls back to secondary on transient errors.
    - Streaming: uses primary model (or override) and yields content strings.
    """
    settings = get_settings()
    client = _get_client()

    if stream:
        return _stream(client, messages, model or settings.qwen_primary_model)

    # Non-streaming with fallback
    primary = model or settings.qwen_primary_model
    fallback = settings.qwen_fallback_model

    models_to_try = [primary] if model else [primary, fallback]
    last_exc: Exception | None = None

    for attempt_model in models_to_try:
        t0 = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=attempt_model,
                messages=messages,  # type: ignore[arg-type]
            )
            duration_ms = int((time.perf_counter() - t0) * 1000)
            content = response.choices[0].message.content or ""
            usage = response.usage
            return LLMResponse(
                content=content,
                model=attempt_model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            last_exc = exc
            if not _is_transient(exc) or attempt_model == models_to_try[-1]:
                raise

    # Should never reach here, but satisfy type checker
    raise last_exc  # type: ignore[misc]


def _stream(
    client: openai.OpenAI,
    messages: list[dict[str, str]],
    model: str,
) -> Generator[str, None, None]:
    """Internal streaming generator — yields content chunk strings."""
    stream_response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        stream=True,
    )
    for chunk in stream_response:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content
