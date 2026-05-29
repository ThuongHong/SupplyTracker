from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import respx

from app.collectors.portwatch import PortWatchCollector
from app.db.models import Chokepoint, Port

# PortWatch queries the IMF ArcGIS FeatureServer. base_url is set to
# http://portwatch.test by tests/collectors/conftest.py.
_PORTS_URL = "http://portwatch.test/Daily_Ports_Data/FeatureServer/0/query"
_CHOKE_URL = "http://portwatch.test/Daily_Chokepoints_Data/FeatureServer/0/query"

_PORT_FEATURES = [
    {"date": "2026-05-22", "portid": "port744", "portname": "Jebel Ali", "portcalls": 3, "import": 21750, "export": 73814},
    {"date": "2026-05-22", "portid": "port1201", "portname": "Singapore", "portcalls": 135, "import": 1229046, "export": 931431},
]
_CHOKE_FEATURES = [
    {"date": "2026-05-24", "portid": "chokepoint1", "portname": "Suez Canal", "n_total": 30, "capacity": 1500000},
]
# 2 ports x 3 metrics + 1 chokepoint x 2 metrics
_EXPECTED_ROWS = 2 * 3 + 1 * 2


def _port(portid: str, name: str) -> MagicMock:
    p = MagicMock()
    p.portid = portid
    p.name = name
    return p


def _cp(cpid: str, name: str) -> MagicMock:
    c = MagicMock()
    c.chokepointid = cpid
    c.name = name
    return c


def _make_session(ports: list, chokepoints: list) -> MagicMock:
    session = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        q.filter.return_value = q  # is_tracked filter chains back
        if model is Port:
            q.all.return_value = ports
        elif model is Chokepoint:
            q.all.return_value = chokepoints
        else:
            q.all.return_value = []
        return q

    session.query.side_effect = query_side_effect
    return session


def _stats_response(maxd: str) -> httpx.Response:
    return httpx.Response(200, json={"features": [{"attributes": {"maxd": maxd}}]})


def _features_response(features: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"features": [{"attributes": a} for a in features]})


def _arcgis_handler(maxd: str, features: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        if "outStatistics" in request.url.params:
            return _stats_response(maxd)
        return _features_response(features)

    return handler


def _mock_arcgis() -> None:
    respx.get(_PORTS_URL).mock(side_effect=_arcgis_handler("2026-05-22", _PORT_FEATURES))
    respx.get(_CHOKE_URL).mock(side_effect=_arcgis_handler("2026-05-24", _CHOKE_FEATURES))


def _tracked_session() -> MagicMock:
    return _make_session(
        ports=[_port("port744", "Jebel Ali"), _port("port1201", "Singapore")],
        chokepoints=[_cp("chokepoint1", "Suez Canal")],
    )


class TestPortWatchDailyRefresh:
    @respx.mock
    def test_collect_returns_row_count(self) -> None:
        _mock_arcgis()
        collector = PortWatchCollector()
        with patch.object(collector, "_upsert_metric"), patch.object(collector, "_upsert_coverage"):
            result = collector.collect(_tracked_session())
        assert result.rows == _EXPECTED_ROWS
        assert result.errors == []

    @respx.mock
    def test_port_metrics_keyed_by_portid(self) -> None:
        _mock_arcgis()
        collector = PortWatchCollector()
        calls: list[dict] = []

        def capture(s: object, **kwargs: object) -> None:
            calls.append(dict(kwargs))

        with patch.object(collector, "_upsert_metric", side_effect=capture), \
             patch.object(collector, "_upsert_coverage"):
            collector.collect(_tracked_session())

        port_ids = {c["entity_id"] for c in calls if c["entity_type"] == "port"}
        assert port_ids == {"port744", "port1201"}  # portid, not locode
        choke_ids = {c["entity_id"] for c in calls if c["entity_type"] == "chokepoint"}
        assert choke_ids == {"suez_canal"}

    @respx.mock
    def test_no_tracked_entities_fetches_nothing(self) -> None:
        # No tracked ports/chokepoints → no ArcGIS data calls, zero rows.
        collector = PortWatchCollector()
        with patch.object(collector, "_upsert_metric"), patch.object(collector, "_upsert_coverage"):
            result = collector.collect(_make_session(ports=[], chokepoints=[]))
        assert result.rows == 0


class TestPortWatch429Backoff:
    @respx.mock
    def test_retries_on_429(self) -> None:
        respx.get(_PORTS_URL).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                _stats_response("2026-05-22"),
                _features_response(_PORT_FEATURES),
            ]
        )
        respx.get(_CHOKE_URL).mock(side_effect=_arcgis_handler("2026-05-24", _CHOKE_FEATURES))
        collector = PortWatchCollector()
        with patch("time.sleep"), patch.object(collector, "_upsert_metric"), \
             patch.object(collector, "_upsert_coverage"):
            result = collector.collect(_tracked_session())
        assert result.rows == _EXPECTED_ROWS


class TestPortWatchPerEntitySync:
    @respx.mock
    def test_sync_port_backfills_window(self) -> None:
        # 91 daily rows for one port → 91 * 3 metrics.
        days = [
            {"date": f"2026-05-{d:02d}", "portid": "port744", "portname": "Jebel Ali",
             "portcalls": 1, "import": 10, "export": 20}
            for d in range(1, 23)
        ]
        respx.get(_PORTS_URL).mock(side_effect=_arcgis_handler("2026-05-22", days))
        collector = PortWatchCollector()
        session = MagicMock()
        with patch.object(collector, "_upsert_metric"), patch.object(collector, "_upsert_coverage"):
            result = collector.sync_port(session, "port744", "Jebel Ali")
        assert result.rows == len(days) * 3
        assert result.errors == []


class TestPortWatchPerEntityIsolation:
    @respx.mock
    def test_one_metric_error_does_not_abort_others(self) -> None:
        _mock_arcgis()
        collector = PortWatchCollector()
        call_count = 0

        def flaky(s: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated DB error")

        with patch.object(collector, "_upsert_metric", side_effect=flaky), \
             patch.object(collector, "_upsert_coverage"):
            result = collector.collect(_tracked_session())

        assert result.rows == _EXPECTED_ROWS - 1
        assert result.errors
