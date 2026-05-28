"""Contract tests for GET /api/v1/stats/coverage."""
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


def _make_coverage_row() -> MagicMock:
    r = MagicMock()
    r.source = "portwatch"
    r.entity_type = "port"
    r.entity_id = "SGSIN"
    r.entity_name = "Port of Singapore"
    r.first_observed_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    r.latest_observed_at = datetime(2026, 5, 28, tzinfo=timezone.utc)
    r.observed_rows = 500
    r.expected_days = 365
    r.missing_days = 10
    r.freshness_status = "fresh"
    r.last_collection_status = "ok"
    r.updated_at = datetime(2026, 5, 28, tzinfo=timezone.utc)
    r.metadata_ = {}
    return r


class TestStatsCoverage:
    def test_happy_path_returns_items(self, mock_session, client):
        """GET /stats/coverage returns 200 with items and count."""
        coverage = _make_coverage_row()

        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = [coverage]

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/stats/coverage")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert data["count"] == 1
        item = data["items"][0]
        assert item["source"] == "portwatch"
        assert item["entity_id"] == "SGSIN"

    def test_source_filter_applied(self, mock_session, client):
        """GET /stats/coverage?source=portwatch returns filtered results."""
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = []

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/stats/coverage?source=portwatch")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        mock_q.filter.assert_called()
