from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import respx

from app.collectors.portwatch import PortWatchCollector

# PortWatch now queries the IMF ArcGIS FeatureServer. base_url is set to
# http://portwatch.test by tests/collectors/conftest.py.
_PORTS_URL = "http://portwatch.test/Daily_Ports_Data/FeatureServer/0/query"
_CHOKE_URL = "http://portwatch.test/Daily_Chokepoints_Data/FeatureServer/0/query"

# Features keyed by portids that exist in the collector's curated map.
_PORT_FEATURES = [
    {
        "date": "2026-05-22", "portid": "port744", "portname": "Jebel Ali",
        "portcalls": 3, "import": 21750, "export": 73814,
    },
    {
        "date": "2026-05-22", "portid": "port1201", "portname": "Singapore",
        "portcalls": 135, "import": 1229046, "export": 931431,
    },
]
_CHOKE_FEATURES = [
    {
        "date": "2026-05-24", "portid": "chokepoint1", "portname": "Suez Canal",
        "n_total": 30, "capacity": 1500000,
    },
]
# 2 ports x 3 metrics + 1 chokepoint x 2 metrics
_EXPECTED_ROWS = 2 * 3 + 1 * 2


def _make_session() -> MagicMock:
    session = MagicMock()
    session.get.return_value = None
    return session


def _stats_response(maxd: str) -> httpx.Response:
    return httpx.Response(200, json={"features": [{"attributes": {"maxd": maxd}}]})


def _features_response(features: list[dict]) -> httpx.Response:
    return httpx.Response(
        200, json={"features": [{"attributes": a} for a in features]}
    )


def _arcgis_handler(maxd: str, features: list[dict]):
    """respx side_effect: max-date query vs. data query disambiguated by params."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "outStatistics" in request.url.params:
            return _stats_response(maxd)
        return _features_response(features)

    return handler


def _mock_arcgis() -> None:
    respx.get(_PORTS_URL).mock(side_effect=_arcgis_handler("2026-05-22", _PORT_FEATURES))
    respx.get(_CHOKE_URL).mock(side_effect=_arcgis_handler("2026-05-24", _CHOKE_FEATURES))


class TestPortWatchHappyPath:
    @respx.mock
    def test_collect_returns_row_count(self) -> None:
        _mock_arcgis()
        collector = PortWatchCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_metric"), \
             patch.object(collector, "_upsert_coverage"):
            result = collector.collect(session)

        assert result.rows == _EXPECTED_ROWS
        assert result.errors == []

    @respx.mock
    def test_collect_calls_upsert_for_each_row(self) -> None:
        _mock_arcgis()
        collector = PortWatchCollector()
        session = _make_session()

        upsert_calls: list[dict] = []

        def capture_upsert(s: object, **kwargs: object) -> None:
            upsert_calls.append(dict(kwargs))

        with patch.object(collector, "_upsert_metric", side_effect=capture_upsert), \
             patch.object(collector, "_upsert_coverage"):
            collector.collect(session)

        assert len(upsert_calls) == _EXPECTED_ROWS
        # Port portids map back to our LOCODEs.
        port_ids = {c["entity_id"] for c in upsert_calls if c["entity_type"] == "port"}
        assert port_ids == {"AEJEA", "SGSIN"}
        choke_ids = {
            c["entity_id"] for c in upsert_calls if c["entity_type"] == "chokepoint"
        }
        assert choke_ids == {"suez_canal"}
        metric_names = {c["metric_name"] for c in upsert_calls}
        assert "port_calls" in metric_names


class TestPortWatchIdempotency:
    @respx.mock
    def test_collect_twice_same_data(self) -> None:
        _mock_arcgis()
        collector = PortWatchCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_metric"), \
             patch.object(collector, "_upsert_coverage"):
            r1 = collector.collect(session)
            r2 = collector.collect(session)

        assert r1.rows == r2.rows == _EXPECTED_ROWS


class TestPortWatch429Backoff:
    @respx.mock
    def test_retries_on_429(self) -> None:
        # First (stats) request 429s, then succeeds; data request follows.
        respx.get(_PORTS_URL).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                _stats_response("2026-05-22"),
                _features_response(_PORT_FEATURES),
            ]
        )
        respx.get(_CHOKE_URL).mock(
            side_effect=_arcgis_handler("2026-05-24", _CHOKE_FEATURES)
        )
        collector = PortWatchCollector()
        session = _make_session()

        with patch("time.sleep"), \
             patch.object(collector, "_upsert_metric"), \
             patch.object(collector, "_upsert_coverage"):
            result = collector.collect(session)

        assert result.rows == _EXPECTED_ROWS


class TestPortWatchPerEntityIsolation:
    @respx.mock
    def test_one_metric_error_does_not_abort_others(self) -> None:
        _mock_arcgis()
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

        assert result.rows == _EXPECTED_ROWS - 1
        assert result.errors
