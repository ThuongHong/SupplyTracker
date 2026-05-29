"""Contract tests for POST /api/v1/sync/{source}."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

VALID_TOKEN = "test-secret-token"


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


class TestSync:
    def test_happy_path_with_bearer_returns_task_id(self, client):
        """POST /sync/portwatch with valid bearer returns 200 with task_id and source."""
        mock_task = MagicMock()
        mock_task.id = "celery-task-uuid-1234"

        mock_collect_fn = MagicMock()
        mock_collect_fn.delay.return_value = mock_task

        with patch("app.api.routes.sync.collect_portwatch", mock_collect_fn, create=True):
            # We need to patch inside the import block in the route
            with patch.dict(
                "sys.modules",
                {},
            ):
                with patch("app.tasks.collect.collect_portwatch") as mock_cp:
                    mock_cp.delay.return_value = mock_task

                    resp = client.post(
                        "/api/v1/sync/portwatch",
                        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
                    )

        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["source"] == "portwatch"

    def test_missing_bearer_returns_401(self, client):
        """POST /sync/portwatch without Authorization header → 401."""
        resp = client.post("/api/v1/sync/portwatch")

        assert resp.status_code == 401

    def test_invalid_bearer_returns_401(self, client):
        """POST /sync/portwatch with wrong token → 401."""
        resp = client.post(
            "/api/v1/sync/portwatch",
            headers={"Authorization": "Bearer wrong-token"},
        )

        assert resp.status_code == 401

    def test_invalid_source_returns_422(self, client):
        """POST /sync/invalid_source with valid bearer → 422."""
        resp = client.post(
            "/api/v1/sync/invalid_source",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 422


class TestPerEntitySync:
    def test_sync_port_backfills_and_tracks(self, mock_session, client):
        from app.collectors.base import CollectionResult

        port = MagicMock()
        port.portid = "port1000"
        port.name = "Test Port"
        port.is_tracked = False
        mock_session.query.return_value.filter.return_value.first.return_value = port

        with patch(
            "app.api.routes.sync.PortWatchCollector.sync_port",
            return_value=CollectionResult(rows=273, errors=[]),
        ):
            resp = client.post(
                "/api/v1/sync/port/port1000",
                headers={"Authorization": f"Bearer {VALID_TOKEN}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["rows"] == 273
        assert data["is_tracked"] is True
        assert port.is_tracked is True  # flag flipped

    def test_sync_unknown_port_returns_404(self, mock_session, client):
        mock_session.query.return_value.filter.return_value.first.return_value = None
        resp = client.post(
            "/api/v1/sync/port/nope999",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )
        assert resp.status_code == 404

    def test_sync_port_requires_bearer(self, client):
        resp = client.post("/api/v1/sync/port/port1000")
        assert resp.status_code == 401

    def test_untrack_port_clears_flag(self, mock_session, client):
        port = MagicMock()
        port.portid = "port1000"
        port.is_tracked = True
        mock_session.query.return_value.filter.return_value.first.return_value = port

        resp = client.post(
            "/api/v1/untrack/port/port1000",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_tracked"] is False
        assert port.is_tracked is False
