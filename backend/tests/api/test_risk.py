"""Contract tests for risk routes."""
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


def _make_port_risk_score() -> MagicMock:
    r = MagicMock()
    r.entity_type = "port"
    r.entity_id = "SGSIN"
    r.entity_name = "Port of Singapore"
    r.score = 55.0
    r.severity = "moderate"
    r.freshness_status = "fresh"
    r.as_of = datetime(2026, 5, 28, tzinfo=timezone.utc)
    r.time = datetime(2026, 5, 28, tzinfo=timezone.utc)
    r.component_scores = {"portwatch": 60.0}
    r.missing_components = []
    r.reasons = ["High vessel count"]
    r.source_metrics = {}
    return r


def _make_forecast() -> MagicMock:
    f = MagicMock()
    f.forecast_key = "port:SGSIN:2026-05-28"
    f.entity_type = "port"
    f.entity_id = "SGSIN"
    f.entity_name = "Port of Singapore"
    f.horizon_days = 7
    f.predictions = []
    f.confidence = 0.8
    f.train_window_start = None
    f.train_window_end = None
    f.data_sufficiency_status = "sufficient"
    f.unavailable_reason = None
    f.key_drivers = []
    f.metrics = {}
    f.model_name = "linear"
    f.feature_schema_version = "v1"
    f.created_at = datetime(2026, 5, 28, tzinfo=timezone.utc)
    return f


class TestRiskScoresList:
    def test_happy_path_returns_list(self, mock_session, client):
        """GET /risk/scores returns 200 with items list."""
        score = _make_port_risk_score()

        # The route calls db.query(PortRiskScore).group_by().subquery() then
        # db.query(PortRiskScore).join().all() for ports, similarly for chokepoints.
        call_count = [0]

        def query_side_effect(*args, **kwargs):
            mock_q = MagicMock()
            mock_q.group_by.return_value = mock_q
            mock_q.subquery.return_value = MagicMock()
            mock_q.join.return_value = mock_q
            call_count[0] += 1
            # 1st join().all() → port scores; 2nd → chokepoint scores (empty)
            if call_count[0] % 2 == 0:
                mock_q.all.return_value = [score]
            else:
                mock_q.all.return_value = []
            return mock_q

        mock_session.query.side_effect = query_side_effect

        resp = client.get("/api/v1/risk/scores")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)


class TestRiskScoreDetail:
    def test_happy_path_returns_score_and_snapshot(self, mock_session, client):
        """GET /risk/scores/port:SGSIN returns 200 with entity fields."""
        score = _make_port_risk_score()

        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        # First call → risk score row; second call → snapshot (None)
        first_call = [True]

        def first_side_effect():
            if first_call[0]:
                first_call[0] = False
                return score
            return None

        mock_q.first.side_effect = first_side_effect
        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/risk/scores/port:SGSIN")

        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "SGSIN"
        assert data["entity_type"] == "port"
        assert data["score"] == 55.0

    def test_unknown_entity_returns_404(self, mock_session, client):
        """GET /risk/scores/port:UNKNOWN → 404."""
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.first.return_value = None

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/risk/scores/port:UNKNOWN")

        assert resp.status_code == 404

    def test_malformed_entity_ref_returns_422(self, mock_session, client):
        """GET /risk/scores/invalid → 422 (no colon separator)."""
        resp = client.get("/api/v1/risk/scores/invalid")

        # The route raises HTTPException(422) for missing colon
        assert resp.status_code == 422


class TestRiskForecast:
    def test_happy_path_returns_forecast(self, mock_session, client):
        """GET /risk/forecasts/port:SGSIN returns 200 with forecast fields."""
        forecast = _make_forecast()

        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.first.return_value = forecast

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/risk/forecasts/port:SGSIN")

        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "SGSIN"
        assert data["entity_type"] == "port"
        assert "stale" in data
        assert "predictions" in data

    def test_unknown_entity_returns_404(self, mock_session, client):
        """GET /risk/forecasts/port:UNKNOWN → 404."""
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.first.return_value = None

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/risk/forecasts/port:UNKNOWN")

        assert resp.status_code == 404
