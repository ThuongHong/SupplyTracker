"""Contract tests for indices routes."""
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


def _make_freight_index(name: str = "BDI") -> MagicMock:
    row = MagicMock()
    row.index_name = name
    row.source = "bloomberg"
    row.value = 1500.0
    row.time = datetime(2026, 5, 28, tzinfo=timezone.utc)
    return row


class TestIndicesList:
    def test_happy_path_returns_list_with_change_pct(self, mock_session, client):
        """GET /indices returns 200 with items list containing change_pct fields."""
        index_row = _make_freight_index()

        # distinct().all() → [("BDI",)]
        mock_distinct_q = MagicMock()
        mock_distinct_q.all.return_value = [("BDI",)]

        # For each index name: latest, 7d, 30d queries → all return same row (mocked)
        mock_filter_q = MagicMock()
        mock_filter_q.order_by.return_value = mock_filter_q
        mock_filter_q.filter.return_value = mock_filter_q
        mock_filter_q.first.return_value = index_row

        def query_side_effect(model, *args):
            from app.db.models import FreightIndex
            # The route calls db.query(FreightIndex.index_name).distinct() and
            # db.query(FreightIndex).filter(...)
            # We detect by whether args contain FreightIndex.index_name (a column)
            if args:
                # This is the distinct query on the column
                mock_q = MagicMock()
                mock_q.distinct.return_value = mock_distinct_q
                return mock_q
            return mock_filter_q

        # Simpler: just return a single mock that handles all paths
        master_q = MagicMock()
        master_q.distinct.return_value = mock_distinct_q
        master_q.filter.return_value = mock_filter_q
        master_q.order_by.return_value = mock_filter_q

        mock_session.query.return_value = master_q

        resp = client.get("/api/v1/indices")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["index_name"] == "BDI"
        assert "change_pct_7d" in item
        assert "change_pct_30d" in item

    def test_empty_db_returns_empty_list(self, mock_session, client):
        """GET /indices with no data → 200 with empty items."""
        mock_distinct_q = MagicMock()
        mock_distinct_q.all.return_value = []

        master_q = MagicMock()
        master_q.distinct.return_value = mock_distinct_q

        mock_session.query.return_value = master_q

        resp = client.get("/api/v1/indices")

        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestIndexTimeseries:
    def test_happy_path_returns_points(self, mock_session, client):
        """GET /indices/BDI/timeseries returns 200 with index_name and points."""
        row = _make_freight_index("BDI")

        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.all.return_value = [row]

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/indices/BDI/timeseries")

        assert resp.status_code == 200
        data = resp.json()
        assert data["index_name"] == "BDI"
        assert len(data["points"]) == 1
        assert data["points"][0]["value"] == 1500.0

    def test_unknown_index_returns_404(self, mock_session, client):
        """GET /indices/UNKNOWN/timeseries → 404."""
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.all.return_value = []

        mock_session.query.return_value = mock_q

        resp = client.get("/api/v1/indices/UNKNOWN/timeseries")

        assert resp.status_code == 404
