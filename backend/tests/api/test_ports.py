"""Contract tests for GET /api/v1/ports and GET /api/v1/ports/{id}."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

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


def _make_port(port_id: int = 1) -> MagicMock:
    p = MagicMock()
    p.id = port_id
    p.locode = "SGSIN"
    p.name = "Port of Singapore"
    p.country = "SG"
    p.region = "Asia"
    p.radius_km = 10.0
    p.twenty_ft_eq_units_year = 37_000_000
    p.geom = None
    return p


class TestPortsList:
    def test_happy_path_returns_paginated_list(self, mock_session, client):
        """GET /ports returns 200 with items/total/limit/offset/has_more."""
        port = _make_port()

        # Set up query chain for list_ports:
        # db.query(Port) → base_q → .count(), .offset().limit().all()
        mock_query = MagicMock()
        mock_query.count.return_value = 1
        mock_offset = MagicMock()
        mock_limit = MagicMock()
        mock_limit.all.return_value = [port]
        mock_offset.limit.return_value = mock_limit
        mock_query.offset.return_value = mock_offset

        # _bulk_latest_scores uses db.query(PortRiskScore).join().all()
        mock_score_query = MagicMock()
        mock_score_query.join.return_value = mock_score_query
        mock_score_query.all.return_value = []

        # Also handle distinct().all() for index names (not used here, but safe)
        def query_side_effect(model, *args):
            from app.db.models import Port
            if model is Port:
                return mock_query
            return mock_score_query

        mock_session.query.side_effect = query_side_effect

        resp = client.get("/api/v1/ports")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "has_more" in data
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Port of Singapore"

    def test_invalid_severity_returns_empty_list(self, mock_session, client):
        """Severity filter with no matches → 200 with empty items list."""
        # When severity is given the route runs a more complex query chain;
        # mock it to return no matches.
        mock_q = MagicMock()
        mock_q.count.return_value = 0
        mock_offset = MagicMock()
        mock_limit = MagicMock()
        mock_limit.all.return_value = []
        mock_offset.limit.return_value = mock_limit
        mock_q.offset.return_value = mock_offset
        mock_q.filter.return_value = mock_q
        mock_q.group_by.return_value = mock_q
        mock_q.join.return_value = mock_q
        mock_q.subquery.return_value = MagicMock()

        # The query for matching entity_ids returns an empty iterable
        mock_q.__iter__ = lambda self: iter([])

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/ports?severity=nonexistent")

        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestPortDetail:
    def test_happy_path_returns_port(self, mock_session, client):
        """GET /ports/1 returns 200 with port detail fields."""
        port = _make_port(port_id=1)

        call_count = [0]

        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.order_by.return_value = mock_q
            if call_count[0] == 1:
                # First call: Port lookup
                mock_q.first.return_value = port
            else:
                # Second call: _latest_severity → return None (no risk score)
                mock_q.first.return_value = None
            return mock_q

        mock_session.query.side_effect = query_side_effect

        resp = client.get("/api/v1/ports/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["name"] == "Port of Singapore"
        assert data["country"] == "SG"

    def test_unknown_port_returns_404(self, mock_session, client):
        """GET /ports/9999 → 404."""
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = None

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/ports/9999")

        assert resp.status_code == 404
