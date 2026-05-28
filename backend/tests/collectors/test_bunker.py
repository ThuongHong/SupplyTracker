from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.collectors.bunker_scraper import BunkerCollector, _BUNKER_URL_TEMPLATE


def _make_session() -> MagicMock:
    return MagicMock()


_BUNKER_RESPONSE = [
    {"date": "2024-01-05", "price": "650.0"},
    {"date": "2024-01-04", "price": "648.0"},
]


class TestBunkerHappyPath:
    @respx.mock
    def test_collect_upserts_rows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUNKER_PORTS", "SGSIN,NLRTM")
        monkeypatch.setenv("BUNKER_FUEL_TYPES", "VLSFO")
        from app.config import get_settings
        get_settings.cache_clear()

        for port in ["SGSIN", "NLRTM"]:
            url = _BUNKER_URL_TEMPLATE.format(port_code=port, fuel_type="VLSFO")
            respx.get(url).mock(
                return_value=httpx.Response(200, json=_BUNKER_RESPONSE)
            )

        collector = BunkerCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_bunker_price") as mock_upsert:
            result = collector.collect(session)

        assert result.rows == 4
        assert mock_upsert.call_count == 4

    @respx.mock
    def test_collect_multiple_fuel_types(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUNKER_PORTS", "SGSIN")
        monkeypatch.setenv("BUNKER_FUEL_TYPES", "VLSFO,IFO380")
        from app.config import get_settings
        get_settings.cache_clear()

        for fuel in ["VLSFO", "IFO380"]:
            url = _BUNKER_URL_TEMPLATE.format(port_code="SGSIN", fuel_type=fuel)
            respx.get(url).mock(
                return_value=httpx.Response(200, json=_BUNKER_RESPONSE)
            )

        collector = BunkerCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_bunker_price") as mock_upsert:
            result = collector.collect(session)

        assert result.rows == 4
        assert mock_upsert.call_count == 4


class TestBunkerEmptyPorts:
    def test_empty_ports_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUNKER_PORTS", "")
        monkeypatch.setenv("BUNKER_FUEL_TYPES", "VLSFO")
        from app.config import get_settings
        get_settings.cache_clear()

        collector = BunkerCollector()
        session = _make_session()

        with respx.mock:
            result = collector.collect(session)

        assert result.rows == 0
        assert not respx.calls


class TestBunkerPerPairIsolation:
    @respx.mock
    def test_one_failing_pair_does_not_abort_others(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BUNKER_PORTS", "SGSIN,NLRTM")
        monkeypatch.setenv("BUNKER_FUEL_TYPES", "VLSFO")
        from app.config import get_settings
        get_settings.cache_clear()

        url_sgsin = _BUNKER_URL_TEMPLATE.format(port_code="SGSIN", fuel_type="VLSFO")
        url_nlrtm = _BUNKER_URL_TEMPLATE.format(port_code="NLRTM", fuel_type="VLSFO")

        respx.get(url_sgsin).mock(side_effect=httpx.ConnectError("refused"))
        respx.get(url_nlrtm).mock(return_value=httpx.Response(200, json=_BUNKER_RESPONSE))

        collector = BunkerCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_bunker_price") as mock_upsert:
            result = collector.collect(session)

        assert result.rows == 2
        assert mock_upsert.call_count == 2
