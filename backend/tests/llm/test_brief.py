from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.llm.brief import get_decision_brief
from app.llm.client import LLMResponse


def _make_events(n: int = 2) -> list:
    events = []
    for i in range(n):
        ev = MagicMock()
        ev.event_key = f"event-key-{i}"
        ev.severity = "high"
        ev.entity_name = f"Port {i}"
        ev.entity_type = "port"
        ev.event_type = "congestion_spike"
        ev.narrative = f"Narrative for event {i}."
        events.append(ev)
    return events


def _make_insights(n: int = 2) -> list:
    insights = []
    for i in range(n):
        ins = MagicMock()
        ins.attention_level = "urgent"
        ins.title = f"Insight {i}"
        ins.narrative = f"Insight narrative {i}."
        insights.append(ins)
    return insights


class TestGetDecisionBrief:
    def test_cache_hit_returns_cached_and_skips_llm(self):
        """When Redis has a cached brief, return it without calling the LLM."""
        session = MagicMock()
        redis_client = MagicMock()
        redis_client.get.return_value = b"Cached brief content."

        top_events = _make_events()
        top_insights = _make_insights()

        with patch("app.llm.brief.chat_completion") as mock_llm:
            result = get_decision_brief(session, redis_client, top_events, top_insights)

        assert result == "Cached brief content."
        mock_llm.assert_not_called()
        session.add.assert_not_called()

    def test_cache_miss_calls_llm_and_caches_result(self):
        """On a cache miss, call the LLM, cache result, and write LLMUsageLog."""
        session = MagicMock()
        redis_client = MagicMock()
        redis_client.get.return_value = None  # cache miss

        top_events = _make_events()
        top_insights = _make_insights()

        fake_response = LLMResponse(
            content="Fresh decision brief.",
            model="qwen-plus",
            input_tokens=100,
            output_tokens=50,
            duration_ms=800,
        )

        with patch("app.llm.brief.chat_completion", return_value=fake_response):
            result = get_decision_brief(session, redis_client, top_events, top_insights)

        assert result == "Fresh decision brief."

        # Redis setex must have been called to cache
        redis_client.setex.assert_called_once()
        cache_key_used, ttl, cached_value = redis_client.setex.call_args[0]
        assert cache_key_used.startswith("brief:")
        assert ttl > 0
        assert cached_value == "Fresh decision brief."

        # LLMUsageLog written and committed
        session.add.assert_called_once()
        session.commit.assert_called_once()
        added_obj = session.add.call_args[0][0]
        assert added_obj.feature == "decision_brief"
        assert added_obj.model == "qwen-plus"
        assert added_obj.status == "ok"

    def test_cache_key_is_deterministic(self):
        """Same events always produce the same cache key."""
        from app.llm.brief import _cache_key

        events = _make_events(3)
        key1 = _cache_key(events)
        key2 = _cache_key(events)
        assert key1 == key2

    def test_cache_key_differs_for_different_events(self):
        """Different event sets produce different cache keys."""
        from app.llm.brief import _cache_key

        events_a = _make_events(2)
        events_b = _make_events(3)
        assert _cache_key(events_a) != _cache_key(events_b)
