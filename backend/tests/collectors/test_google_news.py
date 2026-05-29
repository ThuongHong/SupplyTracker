"""Unit tests for GoogleNewsCollector (GNews API)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.collectors.google_news import GoogleNewsCollector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session() -> MagicMock:
    return MagicMock()


def _make_port(locode: str = "SGSIN", name: str = "Port of Singapore") -> MagicMock:
    p = MagicMock()
    p.locode = locode
    p.portid = "port1201"
    p.name = name
    return p


def _make_chokepoint(name: str = "Strait of Malacca") -> MagicMock:
    cp = MagicMock()
    cp.name = name
    return cp


def _make_article(
    url: str = "https://example.com/news/1",
    title: str = "Test headline",
    description: str = "Summary text",
    source_name: str = "Reuters",
    published_at: str = "2024-06-01T10:00:00Z",
) -> dict:
    return {
        "url": url,
        "title": title,
        "description": description,
        "publishedAt": published_at,
        "source": {"name": source_name, "url": "https://reuters.com"},
    }


def _make_http_client(articles: list[dict], status_code: int = 200) -> MagicMock:
    """Return a context-manager-compatible mock httpx.Client."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"totalArticles": len(articles), "articles": articles}

    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp

    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_client
    mock_cm.__exit__.return_value = False
    return mock_cm


def _make_execute_result(rowcount: int = 1) -> MagicMock:
    r = MagicMock()
    r.rowcount = rowcount
    # Inserts now count via RETURNING (.first() is a row when a row was inserted,
    # None on conflict); prune still reads .rowcount.
    r.first.return_value = object() if rowcount > 0 else None
    return r


# ---------------------------------------------------------------------------
# 5.1 — Happy-path collection and feature-flag guard
# ---------------------------------------------------------------------------

class TestGoogleNewsHappyPath:
    def test_collect_inserts_news_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Collector fetches GNews API, parses one article, and upserts it into DB."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "true")
        monkeypatch.setenv("NEWS_MAX_ITEMS_PER_ENTITY", "30")
        monkeypatch.setenv("GNEWS_API_KEY", "test-key")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()
        port = _make_port()

        def query_side_effect(model):
            from app.db.models import Chokepoint, Port
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q  # is_tracked filter chains back
            if model is Port:
                mock_q.all.return_value = [port]
            elif model is Chokepoint:
                mock_q.all.return_value = []
            else:
                mock_q.all.return_value = []
            return mock_q

        session.query.side_effect = query_side_effect

        mock_cm = _make_http_client([_make_article()])
        # First execute is the insert, second is the prune DELETE
        insert_result = _make_execute_result(rowcount=1)
        prune_result = _make_execute_result(rowcount=0)
        session.execute.side_effect = [insert_result, prune_result]

        collector = GoogleNewsCollector()

        with patch("httpx.Client", return_value=mock_cm):
            result = collector.collect(session)

        assert result.rows == 1
        assert result.errors == []
        assert session.commit.called

    def test_feature_flag_disabled_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When NEWS_FETCH_ENABLED=false, collect() skips all work and returns rows=0."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "false")
        monkeypatch.setenv("GNEWS_API_KEY", "test-key")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()
        collector = GoogleNewsCollector()

        with patch("httpx.Client") as mock_client_cls:
            result = collector.collect(session)

        assert result.rows == 0
        assert result.errors == []
        mock_client_cls.assert_not_called()
        session.commit.assert_not_called()

    def test_missing_api_key_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When GNEWS_API_KEY is empty, collect() skips and returns error."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "true")
        monkeypatch.setenv("GNEWS_API_KEY", "")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()
        collector = GoogleNewsCollector()

        with patch("httpx.Client") as mock_client_cls:
            result = collector.collect(session)

        assert result.rows == 0
        assert any("GNEWS_API_KEY" in e for e in result.errors)
        mock_client_cls.assert_not_called()

    def test_source_name_is_news(self) -> None:
        """Collector declares source_name='news' for task routing."""
        assert GoogleNewsCollector.source_name == "news"


# ---------------------------------------------------------------------------
# 5.2 — Deduplication: same (entity_type, entity_id, url_hash) only once
# ---------------------------------------------------------------------------

class TestGoogleNewsDedup:
    def test_duplicate_entry_counted_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same URL appearing twice → on_conflict_do_nothing; only first counted."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "true")
        monkeypatch.setenv("NEWS_MAX_ITEMS_PER_ENTITY", "30")
        monkeypatch.setenv("GNEWS_API_KEY", "test-key")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()
        port = _make_port()

        def query_side_effect(model):
            from app.db.models import Chokepoint, Port
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q  # is_tracked filter chains back
            if model is Port:
                mock_q.all.return_value = [port]
            elif model is Chokepoint:
                mock_q.all.return_value = []
            else:
                mock_q.all.return_value = []
            return mock_q

        session.query.side_effect = query_side_effect

        same_url = "https://example.com/news/dup"
        articles = [
            _make_article(url=same_url, title="Headline A"),
            _make_article(url=same_url, title="Headline B"),
        ]
        mock_cm = _make_http_client(articles)

        first_insert = _make_execute_result(rowcount=1)
        second_insert = _make_execute_result(rowcount=0)
        prune_result = _make_execute_result(rowcount=0)
        session.execute.side_effect = [first_insert, second_insert, prune_result]

        collector = GoogleNewsCollector()
        with patch("httpx.Client", return_value=mock_cm):
            result = collector.collect(session)

        assert result.rows == 1
        assert result.errors == []


# ---------------------------------------------------------------------------
# 5.3 — Cross-entity: same URL stored for both port and chokepoint
# ---------------------------------------------------------------------------

class TestGoogleNewsCrossEntity:
    def test_same_url_stored_for_port_and_chokepoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same article URL → separate NewsItem rows for port and chokepoint."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "true")
        monkeypatch.setenv("NEWS_MAX_ITEMS_PER_ENTITY", "30")
        monkeypatch.setenv("GNEWS_API_KEY", "test-key")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()
        port = _make_port()
        cp = _make_chokepoint()

        def query_side_effect(model):
            from app.db.models import Chokepoint, Port
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q  # is_tracked filter chains back
            if model is Port:
                mock_q.all.return_value = [port]
            elif model is Chokepoint:
                mock_q.all.return_value = [cp]
            else:
                mock_q.all.return_value = []
            return mock_q

        session.query.side_effect = query_side_effect

        shared_url = "https://example.com/news/shared"
        mock_cm = _make_http_client([_make_article(url=shared_url)])

        port_insert = _make_execute_result(rowcount=1)
        cp_insert = _make_execute_result(rowcount=1)
        prune_result = _make_execute_result(rowcount=0)
        session.execute.side_effect = [port_insert, cp_insert, prune_result]

        collector = GoogleNewsCollector()
        with patch("httpx.Client", return_value=mock_cm):
            result = collector.collect(session)

        assert result.rows == 2
        assert result.errors == []
        assert session.execute.call_count == 3


# ---------------------------------------------------------------------------
# 5.4 — Pruning rows older than 90 days
# ---------------------------------------------------------------------------

class TestGoogleNewsPruning:
    def test_prune_executes_delete_with_cutoff(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """collect() always executes a DELETE for rows older than 90 days."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "true")
        monkeypatch.setenv("NEWS_MAX_ITEMS_PER_ENTITY", "30")
        monkeypatch.setenv("GNEWS_API_KEY", "test-key")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()

        def query_side_effect(model):
            mock_q = MagicMock()
            mock_q.all.return_value = []
            return mock_q

        session.query.side_effect = query_side_effect

        prune_result = _make_execute_result(rowcount=5)
        session.execute.return_value = prune_result

        collector = GoogleNewsCollector()
        mock_cm = _make_http_client([])
        with patch("httpx.Client", return_value=mock_cm):
            result = collector.collect(session)

        # No entities → client.get never called
        mock_cm.__enter__.return_value.get.assert_not_called()

        assert session.execute.call_count == 1
        call_args = session.execute.call_args
        stmt = call_args[0][0]
        stmt_str = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "DELETE" in stmt_str.upper()
        assert "news_item" in stmt_str.lower()

        assert result.errors == []
        assert session.commit.called

    def test_prune_error_recorded_in_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the prune DELETE raises, the error is captured in result.errors."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "true")
        monkeypatch.setenv("NEWS_MAX_ITEMS_PER_ENTITY", "30")
        monkeypatch.setenv("GNEWS_API_KEY", "test-key")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()

        def query_side_effect(model):
            mock_q = MagicMock()
            mock_q.all.return_value = []
            return mock_q

        session.query.side_effect = query_side_effect
        session.execute.side_effect = RuntimeError("DB connection lost")

        collector = GoogleNewsCollector()
        mock_cm = _make_http_client([])
        with patch("httpx.Client", return_value=mock_cm):
            result = collector.collect(session)

        assert len(result.errors) == 1
        assert "prune error" in result.errors[0]
