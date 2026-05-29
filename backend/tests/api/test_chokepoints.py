"""Contract tests for chokepoints routes."""
from __future__ import annotations

from datetime import date
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


def _make_chokepoint(cp_id: int = 1) -> MagicMock:
    cp = MagicMock()
    cp.id = cp_id
    cp.chokepointid = "chokepoint5"
    cp.is_tracked = True
    cp.name = "Strait of Malacca"
    cp.geom = None
    return cp


class TestChokepointsList:
    def test_happy_path_returns_list(self, mock_session, client):
        """GET /chokepoints returns 200 with items/total/limit/offset/has_more."""
        cp = _make_chokepoint()

        mock_q = MagicMock()
        mock_q.count.return_value = 1
        mock_offset = MagicMock()
        mock_limit = MagicMock()
        mock_limit.all.return_value = [cp]
        mock_offset.limit.return_value = mock_limit
        mock_q.offset.return_value = mock_offset

        mock_score_q = MagicMock()
        mock_score_q.join.return_value = mock_score_q
        mock_score_q.all.return_value = []

        def query_side_effect(model, *args):
            from app.db.models import Chokepoint
            if model is Chokepoint:
                return mock_q
            return mock_score_q

        mock_session.query.side_effect = query_side_effect

        resp = client.get("/api/v1/chokepoints")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Strait of Malacca"


class TestChokepointDetail:
    def test_happy_path_returns_chokepoint(self, mock_session, client):
        """GET /chokepoints/1 returns 200 with id and name."""
        cp = _make_chokepoint()

        call_count = [0]

        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            if call_count[0] == 1:
                # First call: Chokepoint lookup → return cp
                mock_q.first.return_value = cp
            else:
                # Second call: severity lookup → None (no risk score)
                mock_q.first.return_value = None
            return mock_q

        mock_session.query.side_effect = query_side_effect

        resp = client.get("/api/v1/chokepoints/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["name"] == "Strait of Malacca"

    def test_unknown_chokepoint_returns_404(self, mock_session, client):
        """GET /chokepoints/9999 → 404."""
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = None

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/chokepoints/9999")

        assert resp.status_code == 404


class TestChokepointBreakdown:
    def test_happy_path_returns_days(self, mock_session, client):
        """GET /chokepoints/1/breakdown returns 200 with chokepoint_id and days list."""
        cp = _make_chokepoint()

        # Route calls: db.query(Chokepoint).filter().first() → cp
        # then db.query(cast(...), ...).filter().group_by().order_by().all() → rows
        first_calls = [0]

        def query_side_effect(*args, **kwargs):
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.group_by.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            # First call: chokepoint lookup → return cp
            # Second call: metric rows → return []
            first_calls[0] += 1
            if first_calls[0] == 1:
                mock_q.first.return_value = cp
            else:
                mock_q.all.return_value = []
            return mock_q

        mock_session.query.side_effect = query_side_effect

        resp = client.get("/api/v1/chokepoints/1/breakdown")

        assert resp.status_code == 200
        data = resp.json()
        assert data["chokepoint_id"] == 1
        assert data["name"] == "Strait of Malacca"
        assert isinstance(data["days"], list)

    def test_unknown_chokepoint_breakdown_returns_404(self, mock_session, client):
        """GET /chokepoints/9999/breakdown → 404."""
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = None

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/chokepoints/9999/breakdown")

        assert resp.status_code == 404
