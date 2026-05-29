"""Contract tests for GET /entities/{entity_type}/{entity_id}/dashboard."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.schemas.dashboard import DashboardResponse, DashboardStats, DisruptionItem, EntityInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_port_dashboard_response() -> DashboardResponse:
    return DashboardResponse(
        entity=EntityInfo(type="port", id="SGSIN", name="Singapore"),
        window="30d",
        charts={
            "vessel_mix": [{"time": "2026-05-01T00:00:00Z", "anchored": 5, "moored": 10, "underway": 3}],
            "dwell_hours": [{"time": "2026-05-01T00:00:00Z", "value": 28.4}],
            "throughput": [],
            "risk_trend": [{"time": "2026-05-01T00:00:00Z", "value": 0.71}],
            "forecast": [],
            "indices": [],
            "bunker": [],
        },
        stats=DashboardStats(risk_latest=0.71, vessel_count_latest=47),
        disruptions=[],
    )


def _make_chokepoint_dashboard_response() -> DashboardResponse:
    return DashboardResponse(
        entity=EntityInfo(type="chokepoint", id="strait_of_hormuz", name="Strait of Hormuz"),
        window="30d",
        charts={
            "vessel_mix": [],
            "dwell_hours": [],
            "throughput": [],
            "risk_trend": [{"time": "2026-05-01T00:00:00Z", "value": 0.85}],
            "forecast": [],
            "indices": [],
            "bunker": [],
        },
        stats=DashboardStats(risk_latest=0.85),
        disruptions=[
            DisruptionItem(
                source_entity_id="strait_of_hormuz",
                source_entity_name="Strait of Hormuz",
                target_entity_id="SGSIN",
                target_entity_name="Singapore",
                severity="high",
                confidence=0.9,
                explanation="Tanker traffic disrupted",
                started_at="2026-05-01T00:00:00Z",
                status="active",
            )
        ],
    )


def _make_mock_port() -> MagicMock:
    port = MagicMock()
    port.id = 1
    port.locode = "SGSIN"
    port.name = "Singapore"
    return port


def _make_mock_chokepoint() -> MagicMock:
    cp = MagicMock()
    cp.id = 1
    cp.name = "Strait of Hormuz"
    return cp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 3.2 — Port dashboard happy path
# ---------------------------------------------------------------------------


class TestPortDashboard:
    def test_happy_path_200_non_empty_charts_cache_header(self, mock_session, client):
        """3.2: Port dashboard returns 200, non-empty chart arrays, and Cache-Control header."""
        port_response = _make_port_dashboard_response()
        mock_port = _make_mock_port()

        # Route resolves port via db.query(Port).filter(...).first()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_port

        with patch(
            "app.api.routes.dashboard.build_port_dashboard",
            return_value=port_response,
        ) as mock_build:
            resp = client.get("/api/v1/entities/port/SGSIN/dashboard")

        assert resp.status_code == 200
        data = resp.json()

        # Charts should be non-empty (at least one key has data)
        assert "charts" in data
        charts = data["charts"]
        assert any(len(v) > 0 for v in charts.values()), "Expected at least one non-empty chart array"

        # Cache-Control header must be set
        assert "cache-control" in resp.headers
        assert resp.headers["cache-control"] == "public, max-age=300"

        # Entity info
        assert data["entity"]["type"] == "port"
        assert data["entity"]["id"] == "SGSIN"

        mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# 3.3 — Chokepoint dashboard
# ---------------------------------------------------------------------------


class TestChokepointDashboard:
    def test_chokepoint_disruptions_populated(self, mock_session, client):
        """3.3: Chokepoint dashboard returns 200 and has disruptions populated."""
        cp_response = _make_chokepoint_dashboard_response()
        mock_cp = _make_mock_chokepoint()

        # Chokepoint entity is resolved by fetching all chokepoints and matching by name slug
        mock_session.query.return_value.all.return_value = [mock_cp]

        with patch(
            "app.api.routes.dashboard.build_chokepoint_dashboard",
            return_value=cp_response,
        ) as mock_build:
            resp = client.get("/api/v1/entities/chokepoint/strait_of_hormuz/dashboard")

        assert resp.status_code == 200
        data = resp.json()

        assert data["entity"]["type"] == "chokepoint"
        assert len(data["disruptions"]) > 0, "Expected disruptions to be populated"
        assert data["disruptions"][0]["severity"] == "high"

        mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# 3.4a — 404 on unknown port entity
# ---------------------------------------------------------------------------


class TestDashboard404:
    def test_unknown_port_returns_404(self, mock_session, client):
        """3.4a: Requesting a dashboard for an unknown port returns 404."""
        # build_port_dashboard returns None → route raises 404
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with patch(
            "app.api.routes.dashboard.build_port_dashboard",
            return_value=None,
        ):
            resp = client.get("/api/v1/entities/port/ZZZZZ/dashboard")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3.4b — 422 on invalid window parameter
# ---------------------------------------------------------------------------


class TestDashboard422InvalidWindow:
    def test_invalid_window_returns_422(self, mock_session, client):
        """3.4b: ?window=180d is not a valid window; expect 422 Unprocessable Entity."""
        resp = client.get("/api/v1/entities/port/SGSIN/dashboard?window=180d")

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3.4c — 422 on invalid entity_type
# ---------------------------------------------------------------------------


class TestDashboard422InvalidEntityType:
    def test_invalid_entity_type_returns_422(self, mock_session, client):
        """3.4c: /entities/foo/bar/dashboard → 422 because 'foo' is not a valid entity_type."""
        with patch(
            "app.api.routes.dashboard.build_port_dashboard",
            return_value=None,
        ), patch(
            "app.api.routes.dashboard.build_chokepoint_dashboard",
            return_value=None,
        ):
            resp = client.get("/api/v1/entities/foo/bar/dashboard")

        assert resp.status_code == 422
