from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import respx

from app.collectors.catalog import CatalogCollector, _circle_polygon_wkt

_PORTS_URL = "http://portwatch.test/PortWatch_ports_database/FeatureServer/0/query"
_CHOKE_URL = "http://portwatch.test/PortWatch_chokepoints_database/FeatureServer/0/query"


def _feature(attrs: dict) -> dict:
    return {"attributes": attrs}


def _page(features: list[dict], more: bool) -> httpx.Response:
    return httpx.Response(
        200, json={"features": features, "exceededTransferLimit": more}
    )


def _make_session() -> MagicMock:
    s = MagicMock()
    s.get.return_value = None
    return s


class TestCircleGeometry:
    def test_ring_is_closed(self) -> None:
        wkt = _circle_polygon_wkt(103.0, 1.5)
        coords = wkt[len("POLYGON((") : -2].split(", ")
        assert coords[0] == coords[-1]  # exact closure, no float drift


class TestCatalogPaging:
    @respx.mock
    def test_ports_paging_across_pages(self) -> None:
        # Page 1 signals more; page 2 ends. Chokepoints empty.
        respx.get(_PORTS_URL).mock(
            side_effect=[
                _page(
                    [
                        _feature({"portid": "port1", "portname": "A", "country": "X", "lat": 1.0, "lon": 2.0}),
                        _feature({"portid": "port2", "portname": "B", "country": "Y", "lat": 3.0, "lon": 4.0}),
                    ],
                    more=True,
                ),
                _page(
                    [_feature({"portid": "port3", "portname": "C", "country": "Z", "lat": 5.0, "lon": 6.0})],
                    more=False,
                ),
            ]
        )
        respx.get(_CHOKE_URL).mock(return_value=_page([], more=False))

        session = _make_session()
        result = CatalogCollector().collect(session)

        assert result.rows == 3  # 3 ports across 2 pages, 0 chokepoints
        assert result.errors == []
        # 3 port upserts executed
        assert session.execute.call_count == 3

    @respx.mock
    def test_skips_features_missing_coords(self) -> None:
        respx.get(_PORTS_URL).mock(
            return_value=_page(
                [
                    _feature({"portid": "port1", "portname": "A", "country": "X", "lat": None, "lon": 2.0}),
                    _feature({"portid": "port2", "portname": "B", "country": "Y", "lat": 3.0, "lon": 4.0}),
                ],
                more=False,
            )
        )
        respx.get(_CHOKE_URL).mock(return_value=_page([], more=False))

        result = CatalogCollector().collect(_make_session())
        assert result.rows == 1  # port1 skipped (no lat)


class TestCatalogChokepoints:
    @respx.mock
    def test_chokepoint_synthesizes_polygon(self) -> None:
        respx.get(_PORTS_URL).mock(return_value=_page([], more=False))
        respx.get(_CHOKE_URL).mock(
            return_value=_page(
                [_feature({"portid": "chokepoint1", "portname": "Suez Canal", "lat": 30.0, "lon": 32.0})],
                more=False,
            )
        )
        session = _make_session()
        result = CatalogCollector().collect(session)

        assert result.rows == 1
        assert result.errors == []
