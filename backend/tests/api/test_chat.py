"""Contract tests for POST /api/v1/chat (SSE endpoint)."""
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
    # Reset cached rate limiter so it gets a fresh settings-aware instance
    import app.api.routes.chat as chat_module
    chat_module._chat_limiter = None

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    chat_module._chat_limiter = None


class TestChat:
    def test_happy_path_returns_sse_response(self, client):
        """POST /chat with valid body returns 200 with text/event-stream content type."""
        payload = {"message": "What is the risk at Singapore?", "entity_context": []}

        with patch("app.api.routes.chat.stream_chat_response", return_value=iter(["Hello", " world"])):
            resp = client.post("/api/v1/chat", json=payload)

        assert resp.status_code == 200
        # SSE responses have text/event-stream content type
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_empty_message_returns_422(self, client):
        """POST /chat with empty message body → 422 validation error."""
        resp = client.post("/api/v1/chat", json={})

        assert resp.status_code == 422

    def test_message_too_long_returns_422(self, client):
        """POST /chat with message exceeding 4000 chars → 422."""
        payload = {"message": "x" * 4001, "entity_context": []}

        resp = client.post("/api/v1/chat", json=payload)

        assert resp.status_code == 422
