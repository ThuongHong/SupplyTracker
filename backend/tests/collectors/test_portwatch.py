from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.collectors.portwatch import PortWatchCollector


def _make_session() -> MagicMock:
    session = MagicMock()
    session.query.return_value.count.return_value = 1
    session.get.return_value = None
    return session


_METRIC_ROWS = [
    {
        "entity_type": "port",
        "entity_id": "P001",
        "entity_name": "Port Alpha",
        "metric_name": "vessel_count",
        "value": 42.0,
        "unit": "vessels",
        "source_entity_id": None,
        "metadata": None,
    },
    {
        "entity_type": "port",
        "entity_id": "P002",
        "entity_name": "Port Beta",
        "metric_name": "vessel_count",
        "value": 17.0,
        "unit": "vessels",
        "source_entity_id": None,
        "metadata": None,
    },
]


class TestPortWatchHappyPath:
    @respx.mock
    def test_collect_returns_row_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        respx.get("http://portwatch.test/metrics").mock(
            return_value=httpx.Response(200, json=_METRIC_ROWS)
        )
        collector = PortWatchCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_metric") as mock_upsert, \
             patch.object(collector, "_upsert_coverage"):
            mock_upsert.return_value = None
            result = collector.collect(session)

        assert result.rows == 2

    @respx.mock
    def test_collect_calls_upsert_for_each_row(self) -> None:
        respx.get("http://portwatch.test/metrics").mock(
            return_value=httpx.Response(200, json=_METRIC_ROWS)
        )
        collector = PortWatchCollector()
        session = _make_session()

        upsert_calls: list[dict] = []

        def capture_upsert(s: object, **kwargs: object) -> None:
            upsert_calls.append(dict(kwargs))

        with patch.object(collector, "_upsert_metric", side_effect=capture_upsert), \
             patch.object(collector, "_upsert_coverage"):
            collector.collect(session)

        assert len(upsert_calls) == 2
        assert upsert_calls[0]["entity_id"] == "P001"
        assert upsert_calls[1]["entity_id"] == "P002"


class TestPortWatchIdempotency:
    @respx.mock
    def test_collect_twice_same_data(self) -> None:
        respx.get("http://portwatch.test/metrics").mock(
            return_value=httpx.Response(200, json=_METRIC_ROWS)
        )
        collector = PortWatchCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_metric"), \
             patch.object(collector, "_upsert_coverage"):
            r1 = collector.collect(session)

        respx.get("http://portwatch.test/metrics").mock(
            return_value=httpx.Response(200, json=_METRIC_ROWS)
        )
        with patch.object(collector, "_upsert_metric"), \
             patch.object(collector, "_upsert_coverage"):
            r2 = collector.collect(session)

        assert r1.rows == r2.rows == 2


class TestPortWatch429Backoff:
    @respx.mock
    def test_retries_on_429(self) -> None:
        route = respx.get("http://portwatch.test/metrics")
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=_METRIC_ROWS),
        ]
        collector = PortWatchCollector()
        session = _make_session()

        with patch("time.sleep"), \
             patch.object(collector, "_upsert_metric"), \
             patch.object(collector, "_upsert_coverage"):
            result = collector.collect(session)

        assert result.rows == 2


class TestPortWatchPerEntityIsolation:
    @respx.mock
    def test_one_entity_error_does_not_abort_others(self) -> None:
        rows = list(_METRIC_ROWS)
        respx.get("http://portwatch.test/metrics").mock(
            return_value=httpx.Response(200, json=rows)
        )
        collector = PortWatchCollector()
        session = _make_session()

        call_count = 0

        def flaky_upsert(s: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated DB error")

        with patch.object(collector, "_upsert_metric", side_effect=flaky_upsert), \
             patch.object(collector, "_upsert_coverage"):
            result = collector.collect(session)

        assert result.rows == 1
        assert result.errors
