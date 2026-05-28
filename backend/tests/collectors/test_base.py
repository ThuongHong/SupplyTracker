from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.collectors.base import BaseCollector, CollectionResult, _compute_freshness


class _ConcreteCollector(BaseCollector):
    source_name = "test_source"

    def __init__(self, rows_to_return: int = 0) -> None:
        self._rows = rows_to_return

    def collect(self, session: object) -> int:
        return self._rows


class TestRetryRequest:
    def _make_collector(self) -> _ConcreteCollector:
        return _ConcreteCollector()

    @respx.mock
    def test_succeeds_on_first_attempt(self) -> None:
        collector = self._make_collector()
        respx.get("http://example.test/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        with httpx.Client() as client:
            resp = collector._retry_request(client, "GET", "http://example.test/data")
        assert resp.status_code == 200

    @respx.mock
    def test_retries_on_429_with_retry_after(self) -> None:
        collector = self._make_collector()
        route = respx.get("http://example.test/data")
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"ok": True}),
        ]
        with patch("time.sleep") as mock_sleep:
            with httpx.Client() as client:
                resp = collector._retry_request(
                    client, "GET", "http://example.test/data", max_retries=3, base_delay=1.0
                )
        assert resp.status_code == 200
        mock_sleep.assert_called_once_with(0.0)

    @respx.mock
    def test_raises_after_max_retries_on_persistent_429(self) -> None:
        collector = self._make_collector()
        respx.get("http://example.test/data").mock(
            return_value=httpx.Response(429, headers={"Retry-After": "0"})
        )
        with patch("time.sleep"):
            with httpx.Client() as client:
                with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
                    collector._retry_request(
                        client, "GET", "http://example.test/data", max_retries=3
                    )

    @respx.mock
    def test_exponential_backoff_timing(self) -> None:
        collector = self._make_collector()
        respx.get("http://example.test/data").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json={}),
            ]
        )
        sleep_calls: list[float] = []
        with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with httpx.Client() as client:
                resp = collector._retry_request(
                    client, "GET", "http://example.test/data", max_retries=3, base_delay=1.0
                )
        assert resp.status_code == 200
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == 0.0
        assert sleep_calls[1] == 0.0

    @respx.mock
    def test_request_error_retries_then_raises(self) -> None:
        collector = self._make_collector()
        respx.get("http://example.test/data").mock(
            side_effect=httpx.ConnectError("refused")
        )
        with patch("time.sleep"):
            with httpx.Client() as client:
                with pytest.raises((RuntimeError, httpx.RequestError)):
                    collector._retry_request(
                        client, "GET", "http://example.test/data", max_retries=2
                    )


class TestComputeFreshness:
    def test_fresh_under_24h(self) -> None:
        now = datetime.now(timezone.utc)
        observed = now - timedelta(hours=12)
        assert _compute_freshness(observed, now) == "fresh"

    def test_stale_24_to_48h(self) -> None:
        now = datetime.now(timezone.utc)
        observed = now - timedelta(hours=36)
        assert _compute_freshness(observed, now) == "stale"

    def test_missing_over_48h(self) -> None:
        now = datetime.now(timezone.utc)
        observed = now - timedelta(hours=72)
        assert _compute_freshness(observed, now) == "missing"


class TestUpsertCoverage:
    def _make_session_mock(self) -> MagicMock:
        session = MagicMock()
        session.get.return_value = None
        return session

    def test_upsert_coverage_calls_execute(self) -> None:
        collector = _ConcreteCollector()
        session = self._make_session_mock()
        now = datetime.now(timezone.utc)
        collector._upsert_coverage(session, "port", "P001", "Test Port", "portwatch", now)
        session.execute.assert_called_once()

    def test_upsert_coverage_computes_expected_and_missing(self) -> None:
        collector = _ConcreteCollector()
        session = MagicMock()

        first_observed = datetime.now(timezone.utc) - timedelta(days=10)
        existing = MagicMock()
        existing.first_observed_at = first_observed
        existing.observed_rows = 5
        session.get.return_value = existing

        now = datetime.now(timezone.utc)
        collector._upsert_coverage(session, "port", "P001", "Test Port", "portwatch", now)

        assert existing.expected_days == 10
        assert existing.missing_days == 5

    def test_upsert_coverage_missing_days_not_negative(self) -> None:
        collector = _ConcreteCollector()
        session = MagicMock()

        first_observed = datetime.now(timezone.utc) - timedelta(days=5)
        existing = MagicMock()
        existing.first_observed_at = first_observed
        existing.observed_rows = 10
        session.get.return_value = existing

        now = datetime.now(timezone.utc)
        collector._upsert_coverage(session, "port", "P001", "Test Port", "portwatch", now)

        assert existing.missing_days == 0
