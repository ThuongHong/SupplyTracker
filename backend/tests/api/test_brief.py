"""Contract tests for GET /api/v1/brief."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_redis
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def mock_redis():
    return MagicMock()


@pytest.fixture()
def client(mock_session, mock_redis):
    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _story_event() -> MagicMock:
    event = MagicMock()
    event.event_key = "evt-1"
    event.severity = "critical"
    event.entity_name = "Suez Canal"
    event.entity_type = "chokepoint"
    event.event_type = "transit_disruption"
    event.narrative = "Transit halted"
    event.event_time = datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc)
    return event


def _insight() -> MagicMock:
    insight = MagicMock()
    insight.attention_level = "high"
    insight.title = "LA congestion"
    insight.narrative = "Dwell rising"
    return insight


class TestBrief:
    def test_get_redis_passes_string_url(self, monkeypatch):
        calls: list[tuple[object, bool]] = []

        def fake_from_url(url, *, decode_responses):
            calls.append((url, decode_responses))
            return MagicMock()

        monkeypatch.setattr("app.api.deps.redis_lib.Redis.from_url", fake_from_url)

        get_redis()

        assert isinstance(calls[0][0], str)
        assert calls[0][1] is True

    def test_returns_brief_markdown(self, mock_session, client, monkeypatch):
        story_query = MagicMock()
        story_query.order_by.return_value.limit.return_value.all.return_value = [_story_event()]
        insight_query = MagicMock()
        insight_query.order_by.return_value.limit.return_value.all.return_value = [_insight()]
        mock_session.query.side_effect = [story_query, insight_query]

        monkeypatch.setattr(
            "app.api.routes.brief.get_decision_brief",
            lambda session, redis_client, top_events, top_insights: "## Situation\nAll clear.",
        )

        resp = client.get("/api/v1/brief")

        assert resp.status_code == 200
        body = resp.json()
        assert body["brief"] == "## Situation\nAll clear."
        assert body["as_of"]

    def test_empty_data_skips_llm_and_returns_steady_fallback(
        self, mock_session, client, monkeypatch
    ):
        """No events + no insights => never call the LLM (avoids refusal text)."""
        empty_query = MagicMock()
        empty_query.order_by.return_value.limit.return_value.all.return_value = []
        mock_session.query.side_effect = [empty_query, empty_query]

        def _boom(*args, **kwargs):
            raise AssertionError("get_decision_brief must not run with empty data")

        monkeypatch.setattr("app.api.routes.brief.get_decision_brief", _boom)

        resp = client.get("/api/v1/brief")

        assert resp.status_code == 200
        body = resp.json()
        assert "steady" in body["brief"].lower()
        assert body["as_of"]
