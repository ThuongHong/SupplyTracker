"""Contract tests for GET /api/v1/story."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def client(mock_session):
    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_story_event() -> MagicMock:
    e = MagicMock()
    e.event_key = "port:SGSIN:congestion:2026-05-28"
    e.event_time = datetime(2026, 5, 28, tzinfo=timezone.utc)
    e.entity_type = "port"
    e.entity_id = "SGSIN"
    e.entity_name = "Port of Singapore"
    e.event_type = "congestion_spike"
    e.severity = "high"
    e.metric = "vessel_count"
    e.observed = 120.0
    e.expected = 80.0
    e.z_score = 2.5
    e.percent_change = 50.0
    e.drivers = {}
    e.source_metrics = {}
    e.narrative = "Vessel count spiked."
    e.confidence = 0.9
    e.attention_level = "watch"
    e.data_sufficiency = {}
    e.created_at = datetime(2026, 5, 28, tzinfo=timezone.utc)
    return e


class TestStory:
    def test_happy_path_returns_events(self, mock_session, client):
        """GET /story returns 200 with items list and count."""
        event = _make_story_event()

        mock_q = MagicMock()
        mock_q.order_by.return_value = mock_q
        mock_q.filter.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = [event]

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/story")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert data["count"] == 1
        assert data["items"][0]["event_key"] == "port:SGSIN:congestion:2026-05-28"

    def test_since_param_filters_events(self, mock_session, client):
        """GET /story?since=... passes filter and returns matching events."""
        mock_q = MagicMock()
        mock_q.order_by.return_value = mock_q
        mock_q.filter.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = []

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/story?since=2026-05-01T00:00:00Z")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["count"] == 0
