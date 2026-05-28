"""Unit tests for GoogleNewsCollector."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, call, patch

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
    p.name = name
    return p


def _make_chokepoint(name: str = "Strait of Malacca") -> MagicMock:
    cp = MagicMock()
    cp.name = name
    return cp


def _make_feed_entry(
    url: str = "http://example.com/news/1",
    title: str = "Test headline",
    published_parsed=None,
) -> MagicMock:
    entry = MagicMock()
    entry.link = url
    entry.title = title
    entry.summary = "Summary text"
    entry.published_parsed = published_parsed or time.gmtime()
    source = MagicMock()
    source.title = "Reuters"
    entry.source = source
    return entry


def _make_feed(entries, bozo: bool = False) -> MagicMock:
    feed = MagicMock()
    feed.entries = entries
    feed.bozo = bozo
    return feed


def _make_execute_result(rowcount: int = 1) -> MagicMock:
    r = MagicMock()
    r.rowcount = rowcount
    return r


# ---------------------------------------------------------------------------
# 5.1 — Happy-path collection and feature-flag guard
# ---------------------------------------------------------------------------

class TestGoogleNewsHappyPath:
    def test_collect_inserts_news_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Collector fetches RSS, parses one entry, and upserts it into the DB."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "true")
        monkeypatch.setenv("NEWS_MAX_ITEMS_PER_ENTITY", "30")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()
        port = _make_port()

        def query_side_effect(model):
            from app.db.models import Port, Chokepoint
            mock_q = MagicMock()
            if model is Port:
                mock_q.all.return_value = [port]
            elif model is Chokepoint:
                mock_q.all.return_value = []
            else:
                mock_q.all.return_value = []
            return mock_q

        session.query.side_effect = query_side_effect

        feed = _make_feed([_make_feed_entry()])
        # First execute is the insert, second is the prune DELETE
        insert_result = _make_execute_result(rowcount=1)
        prune_result = _make_execute_result(rowcount=0)
        session.execute.side_effect = [insert_result, prune_result]

        collector = GoogleNewsCollector()

        with patch("feedparser.parse", return_value=feed):
            result = collector.collect(session)

        # One port, one entry → one inserted row
        assert result.rows == 1
        assert result.errors == []
        assert session.commit.called

    def test_feature_flag_disabled_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When NEWS_FETCH_ENABLED=false, collect() skips all work and returns rows=0."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "false")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()
        collector = GoogleNewsCollector()

        with patch("feedparser.parse") as mock_parse:
            result = collector.collect(session)

        assert result.rows == 0
        assert result.errors == []
        mock_parse.assert_not_called()
        session.commit.assert_not_called()

    def test_source_name_is_news(self) -> None:
        """Collector declares source_name='news' for task routing."""
        assert GoogleNewsCollector.source_name == "news"


# ---------------------------------------------------------------------------
# 5.2 — Deduplication: same (entity_type, entity_id, url_hash) only once
# ---------------------------------------------------------------------------

class TestGoogleNewsDedup:
    def test_duplicate_entry_counted_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When the same URL appears twice in the feed, on_conflict_do_nothing
        means the second execute returns rowcount=0; total rows reflect only
        the first successful insert."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "true")
        monkeypatch.setenv("NEWS_MAX_ITEMS_PER_ENTITY", "30")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()
        port = _make_port()

        # Only ports, no chokepoints
        def query_side_effect(model):
            from app.db.models import Port, Chokepoint
            mock_q = MagicMock()
            if model is Port:
                mock_q.all.return_value = [port]
            elif model is Chokepoint:
                mock_q.all.return_value = []
            else:
                mock_q.all.return_value = []
            return mock_q

        session.query.side_effect = query_side_effect

        # Two entries with the same URL → duplicate
        same_url = "http://example.com/news/dup"
        entry1 = _make_feed_entry(url=same_url, title="Headline A")
        entry2 = _make_feed_entry(url=same_url, title="Headline B")
        feed = _make_feed([entry1, entry2])

        # First execute (first unique URL): rowcount=1; second (duplicate): rowcount=0;
        # third execute is the prune DELETE
        first_insert = _make_execute_result(rowcount=1)
        second_insert = _make_execute_result(rowcount=0)
        prune_result = _make_execute_result(rowcount=0)
        session.execute.side_effect = [first_insert, second_insert, prune_result]

        collector = GoogleNewsCollector()
        with patch("feedparser.parse", return_value=feed):
            result = collector.collect(session)

        # Both entries share the same URL hash, so on_conflict_do_nothing means
        # only one is actually counted
        assert result.rows == 1
        assert result.errors == []


# ---------------------------------------------------------------------------
# 5.3 — Cross-entity: same URL stored for both port and chokepoint
# ---------------------------------------------------------------------------

class TestGoogleNewsCrossEntity:
    def test_same_url_stored_for_port_and_chokepoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same article URL produces separate NewsItem rows for a port and a
        chokepoint because (entity_type, entity_id, url_hash) is the unique key."""
        monkeypatch.setenv("NEWS_FETCH_ENABLED", "true")
        monkeypatch.setenv("NEWS_MAX_ITEMS_PER_ENTITY", "30")
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()
        port = _make_port()
        cp = _make_chokepoint()

        def query_side_effect(model):
            from app.db.models import Port, Chokepoint
            mock_q = MagicMock()
            if model is Port:
                mock_q.all.return_value = [port]
            elif model is Chokepoint:
                mock_q.all.return_value = [cp]
            else:
                mock_q.all.return_value = []
            return mock_q

        session.query.side_effect = query_side_effect

        shared_url = "http://example.com/news/shared"
        entry = _make_feed_entry(url=shared_url)
        feed = _make_feed([entry])

        # Two successful inserts (port + chokepoint) then prune
        port_insert = _make_execute_result(rowcount=1)
        cp_insert = _make_execute_result(rowcount=1)
        prune_result = _make_execute_result(rowcount=0)
        session.execute.side_effect = [port_insert, cp_insert, prune_result]

        collector = GoogleNewsCollector()
        with patch("feedparser.parse", return_value=feed):
            result = collector.collect(session)

        assert result.rows == 2
        assert result.errors == []
        # execute called 3 times: once per entity + once for prune
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
        from app.config import get_settings
        get_settings.cache_clear()

        session = _make_session()

        # No entities → only the prune execute is called
        def query_side_effect(model):
            mock_q = MagicMock()
            mock_q.all.return_value = []
            return mock_q

        session.query.side_effect = query_side_effect

        prune_result = _make_execute_result(rowcount=5)
        session.execute.return_value = prune_result

        collector = GoogleNewsCollector()
        with patch("feedparser.parse") as mock_parse:
            result = collector.collect(session)

        # feedparser was never called because there were no entities
        mock_parse.assert_not_called()

        # The prune DELETE must have been executed
        assert session.execute.call_count == 1
        call_args = session.execute.call_args
        # The first positional arg should be a DELETE statement
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
        with patch("feedparser.parse"):
            result = collector.collect(session)

        assert len(result.errors) == 1
        assert "prune error" in result.errors[0]
