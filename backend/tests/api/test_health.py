"""Contract tests for GET /api/v1/health."""
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


class TestHealthHappyPath:
    def test_returns_200_with_all_fields(self, client):
        """Healthy DB + Redis → 200 with status/db/redis/version fields."""
        with patch("app.api.routes.health.redis_lib.Redis") as mock_redis_cls:
            mock_redis_instance = MagicMock()
            mock_redis_cls.from_url.return_value = mock_redis_instance
            # ping() succeeds (no exception)

            resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "db" in data
        assert "redis" in data
        assert "version" in data
        assert data["db"] == "ok"
        assert data["version"] == "0.1.0"


class TestHealthErrorCase:
    def test_db_failure_returns_degraded(self, mock_session, client):
        """DB execute raises → db='error' and overall status='degraded'."""
        mock_session.execute.side_effect = Exception("DB is down")

        with patch("app.api.routes.health.redis_lib.Redis") as mock_redis_cls:
            mock_redis_cls.from_url.return_value = MagicMock()

            resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["db"] == "error"
        assert data["status"] == "degraded"
