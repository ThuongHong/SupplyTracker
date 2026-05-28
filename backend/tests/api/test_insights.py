"""Contract tests for GET /api/v1/insights."""
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


def _make_insight() -> MagicMock:
    i = MagicMock()
    i.id = 1
    i.generated_at = datetime(2026, 5, 28, tzinfo=timezone.utc)
    i.category = "congestion"
    i.title = "High congestion at Singapore"
    i.narrative = "Vessel count is elevated."
    i.narrative_llm = None
    i.narrative_model = None
    i.narrative_generated_at = None
    i.metrics = {}
    i.priority = 1
    i.event_type = "congestion_spike"
    i.confidence = 0.85
    i.affected_entities = []
    i.source_metrics = {}
    i.attention_level = "watch"
    return i


class TestInsights:
    def test_happy_path_returns_insights(self, mock_session, client):
        """GET /insights returns 200 with items and count."""
        insight = _make_insight()

        mock_q = MagicMock()
        mock_q.order_by.return_value = mock_q
        mock_q.filter.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = [insight]

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/insights")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert data["count"] == 1
        assert data["items"][0]["title"] == "High congestion at Singapore"

    def test_attention_level_filter_applied(self, mock_session, client):
        """GET /insights?attention_level=watch returns filtered results."""
        mock_q = MagicMock()
        mock_q.order_by.return_value = mock_q
        mock_q.filter.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = []

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/insights?attention_level=watch")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        # Verify filter was applied (called once for attention_level)
        mock_q.filter.assert_called()
