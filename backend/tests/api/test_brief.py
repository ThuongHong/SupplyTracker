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
    event.entity_id = "chokepoint1"
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
    insight.affected_entities = [{"type": "port", "id": "port1"}]
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
        monkeypatch.setattr(
            "app.api.routes.brief._tracked_entity_ids",
            lambda db: {"chokepoint1", "port1"},
        )
        story_query = MagicMock()
        story_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            _story_event()
        ]
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

    def test_no_tracked_entities_returns_steady_fallback(
        self, mock_session, client, monkeypatch
    ):
        """Nothing tracked => skip the LLM entirely and return the steady line."""
        monkeypatch.setattr(
            "app.api.routes.brief._tracked_entity_ids", lambda db: set()
        )

        def _boom(*args, **kwargs):
            raise AssertionError("get_decision_brief must not run with nothing tracked")

        monkeypatch.setattr("app.api.routes.brief.get_decision_brief", _boom)

        resp = client.get("/api/v1/brief")

        assert resp.status_code == 200
        body = resp.json()
        assert "steady" in body["brief"].lower()
        assert body["as_of"]

    def test_tracked_but_no_events_or_standing_risk_returns_steady_fallback(
        self, mock_session, client, monkeypatch
    ):
        """No events/insights AND no high/critical standing risk => fallback, no LLM."""
        monkeypatch.setattr(
            "app.api.routes.brief._tracked_entity_ids", lambda db: {"port1"}
        )
        story_query = MagicMock()
        story_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        insight_query = MagicMock()
        insight_query.order_by.return_value.limit.return_value.all.return_value = []
        mock_session.query.side_effect = [story_query, insight_query]
        # No standing high/critical risk for tracked entities.
        monkeypatch.setattr("app.api.routes.risk._get_latest_scores", lambda db: [])

        def _boom(*args, **kwargs):
            raise AssertionError("get_decision_brief must not run with empty data")

        monkeypatch.setattr("app.api.routes.brief.get_decision_brief", _boom)

        resp = client.get("/api/v1/brief")

        assert resp.status_code == 200
        body = resp.json()
        assert "steady" in body["brief"].lower()
        assert body["as_of"]

    def test_standing_high_risk_drives_brief_when_no_events(
        self, mock_session, client, monkeypatch
    ):
        """Quiet day but a tracked entity at high risk => LLM brief from standing posture."""
        monkeypatch.setattr(
            "app.api.routes.brief._tracked_entity_ids", lambda db: {"port1"}
        )
        story_query = MagicMock()
        story_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        insight_query = MagicMock()
        insight_query.order_by.return_value.limit.return_value.all.return_value = []
        mock_session.query.side_effect = [story_query, insight_query]

        standing = MagicMock(entity_id="port1", severity="high")
        untracked = MagicMock(entity_id="port999", severity="critical")
        monkeypatch.setattr(
            "app.api.routes.risk._get_latest_scores",
            lambda db: [standing, untracked],
        )

        captured: dict = {}

        def _fake_brief(db, redis_client, events, insights, standing_risks=None):
            captured["events"] = events
            captured["standing"] = standing_risks
            return "Tracked port at high risk this session."

        monkeypatch.setattr(
            "app.api.routes.brief.get_decision_brief", _fake_brief
        )

        resp = client.get("/api/v1/brief")

        assert resp.status_code == 200
        assert "high risk" in resp.json()["brief"].lower()
        # Only the tracked entity is passed; events list stays empty.
        assert captured["events"] == []
        assert [s.entity_id for s in captured["standing"]] == ["port1"]

    def test_chokepoint_slug_matches_event_entity_id(self):
        from app.api.routes.brief import _chokepoint_slug

        assert _chokepoint_slug("Panama Canal") == "panama_canal"
        assert _chokepoint_slug("Strait of Dover") == "strait_of_dover"

    def test_insight_scope_filters_untracked_entities(self):
        from app.api.routes.brief import _insight_in_scope

        tracked = {"port1"}
        in_scope = MagicMock(affected_entities=[{"type": "port", "id": "port1"}])
        out_scope = MagicMock(affected_entities=[{"type": "port", "id": "port999"}])
        no_entities = MagicMock(affected_entities=None)

        assert _insight_in_scope(in_scope, tracked) is True
        assert _insight_in_scope(out_scope, tracked) is False
        assert _insight_in_scope(no_entities, tracked) is False
