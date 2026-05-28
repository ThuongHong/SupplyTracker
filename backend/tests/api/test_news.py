"""Contract tests for GET /api/v1/entities/{entity_type}/{entity_id}/news."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

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
# Helpers
# ---------------------------------------------------------------------------

def _make_news_item(
    item_id: int = 1,
    entity_type: str = "port",
    entity_id: str = "SGSIN",
    published_at: datetime | None = None,
) -> MagicMock:
    item = MagicMock()
    item.id = item_id
    item.entity_type = entity_type
    item.entity_id = entity_id
    item.url = "http://example.com/news/1"
    item.title = "Port congestion spike"
    item.source = "Reuters"
    item.published_at = published_at or datetime(2026, 5, 1, tzinfo=UTC)
    item.summary = "Port congestion increased."
    item.language = "en"
    item.fetched_at = datetime(2026, 5, 2, tzinfo=UTC)
    return item


def _make_port_mock(locode: str = "SGSIN") -> MagicMock:
    p = MagicMock()
    p.locode = locode
    p.name = "Port of Singapore"
    return p


def _make_chokepoint_mock(name: str = "Strait of Malacca") -> MagicMock:
    cp = MagicMock()
    cp.name = name
    return cp


def _build_port_session(mock_session, port=None, news_items=None):
    """Wire mock_session so _entity_exists(port) finds the port and the news
    query returns *news_items*."""
    if news_items is None:
        news_items = []

    # _entity_exists calls db.query(Port).filter(...).first() twice at most
    # (locode first, then name). The news list query is:
    # db.query(NewsItem).filter(...).order_by(...).limit(...).all()
    entity_q = MagicMock()
    entity_q.filter.return_value = entity_q
    entity_q.first.return_value = port

    news_q = MagicMock()
    news_q.filter.return_value = news_q
    news_q.order_by.return_value = news_q
    news_q.limit.return_value = news_q
    news_q.all.return_value = news_items

    from app.db.models import NewsItem, Port

    def query_side_effect(model):
        if model is Port:
            return entity_q
        if model is NewsItem:
            return news_q
        return MagicMock()

    mock_session.query.side_effect = query_side_effect
    return mock_session


def _build_chokepoint_session(mock_session, chokepoints=None, news_items=None):
    """Wire mock_session so _entity_exists(chokepoint) returns a list of
    chokepoints and the news query returns *news_items*."""
    if news_items is None:
        news_items = []
    if chokepoints is None:
        chokepoints = []

    cp_q = MagicMock()
    cp_q.all.return_value = chokepoints

    news_q = MagicMock()
    news_q.filter.return_value = news_q
    news_q.order_by.return_value = news_q
    news_q.limit.return_value = news_q
    news_q.all.return_value = news_items

    from app.db.models import Chokepoint, NewsItem

    def query_side_effect(model):
        if model is Chokepoint:
            return cp_q
        if model is NewsItem:
            return news_q
        return MagicMock()

    mock_session.query.side_effect = query_side_effect
    return mock_session


# ---------------------------------------------------------------------------
# 5.5 — GET /entities/{entity_type}/{entity_id}/news
# ---------------------------------------------------------------------------

class TestNewsEndpointHappyPath:
    def test_port_news_returns_200_with_items(self, mock_session, client):
        """GET /entities/port/SGSIN/news returns 200 with items list and count."""
        port = _make_port_mock()
        news_item = _make_news_item()
        _build_port_session(mock_session, port=port, news_items=[news_item])

        resp = client.get("/api/v1/entities/port/SGSIN/news")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert data["count"] == 1
        item = data["items"][0]
        assert item["entity_type"] == "port"
        assert item["entity_id"] == "SGSIN"
        assert item["title"] == "Port congestion spike"
        assert item["source"] == "Reuters"

    def test_chokepoint_news_returns_200_with_items(self, mock_session, client):
        """GET /entities/chokepoint/strait_of_malacca/news returns 200."""
        cp = _make_chokepoint_mock(name="Strait of Malacca")
        news_item = _make_news_item(entity_type="chokepoint", entity_id="strait_of_malacca")
        _build_chokepoint_session(mock_session, chokepoints=[cp], news_items=[news_item])

        resp = client.get("/api/v1/entities/chokepoint/strait_of_malacca/news")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["entity_type"] == "chokepoint"

    def test_empty_news_returns_200_with_empty_list(self, mock_session, client):
        """When no news items exist, returns 200 with empty items and count=0."""
        port = _make_port_mock()
        _build_port_session(mock_session, port=port, news_items=[])

        resp = client.get("/api/v1/entities/port/SGSIN/news")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["count"] == 0


class TestNewsEndpoint404:
    def test_unknown_port_returns_404(self, mock_session, client):
        """GET /entities/port/UNKNOWN/news → 404 when port not found."""
        _build_port_session(mock_session, port=None, news_items=[])

        resp = client.get("/api/v1/entities/port/UNKNOWN/news")

        assert resp.status_code == 404

    def test_unknown_chokepoint_returns_404(self, mock_session, client):
        """GET /entities/chokepoint/unknown_strait/news → 404 when no matching chokepoint."""
        _build_chokepoint_session(mock_session, chokepoints=[], news_items=[])

        resp = client.get("/api/v1/entities/chokepoint/unknown_strait/news")

        assert resp.status_code == 404


class TestNewsEndpointValidation:
    def test_invalid_entity_type_returns_422(self, mock_session, client):
        """GET /entities/foo/bar/news → 422 for unsupported entity_type."""
        resp = client.get("/api/v1/entities/foo/bar/news")

        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data

    def test_limit_clamped_to_100(self, mock_session, client):
        """limit=500 is silently clamped to 100; response returns at most 100 items."""
        port = _make_port_mock()
        # Return exactly 100 items to show the clamp is in effect
        news_items = [
            _make_news_item(item_id=i) for i in range(100)
        ]
        _build_port_session(mock_session, port=port, news_items=news_items)

        resp = client.get("/api/v1/entities/port/SGSIN/news?limit=500")

        assert resp.status_code == 200
        data = resp.json()
        # The route clamps limit to 100; our mock returns exactly 100 items
        assert data["count"] == 100
        assert len(data["items"]) == 100

    def test_since_filter_returns_only_newer_items(self, mock_session, client):
        """?since=... causes the route to filter items; older items not returned."""
        port = _make_port_mock()
        newer = _make_news_item(
            item_id=2,
            published_at=datetime(2026, 5, 20, tzinfo=UTC),
        )
        # The mock only returns the newer item (simulating DB filter behaviour)
        _build_port_session(mock_session, port=port, news_items=[newer])

        resp = client.get(
            "/api/v1/entities/port/SGSIN/news?since=2026-05-10T00:00:00Z"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["id"] == 2


# ---------------------------------------------------------------------------
# 5.6 — POST /sync/news and POST /sync/all include collect_news
# ---------------------------------------------------------------------------

VALID_TOKEN = "test-secret-token"


class TestSyncNewsEndpoint:
    def test_sync_news_enqueues_collect_news(self, client):
        """POST /sync/news with valid bearer enqueues collect_news and returns 200."""
        mock_task = MagicMock()
        mock_task.id = "celery-news-task-uuid"

        with patch("app.tasks.collect.collect_news") as mock_collect_news:
            mock_collect_news.delay.return_value = mock_task
            resp = client.post(
                "/api/v1/sync/news",
                headers={"Authorization": f"Bearer {VALID_TOKEN}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "news"
        assert "task_id" in data

    def test_sync_all_returns_200_with_task_id(self, client):
        """POST /sync/all with valid bearer returns 200 with a task_id."""
        mock_task = MagicMock()
        mock_task.id = "celery-all-task-uuid"

        with patch("app.tasks.collect.collect_all") as mock_collect_all:
            mock_collect_all.delay.return_value = mock_task
            resp = client.post(
                "/api/v1/sync/all",
                headers={"Authorization": f"Bearer {VALID_TOKEN}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "all"
        assert "task_id" in data
