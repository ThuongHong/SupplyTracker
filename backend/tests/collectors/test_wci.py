from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.collectors.wci_scraper import WCICollector


def _make_session() -> MagicMock:
    return MagicMock()


_JSON_RESPONSE = [
    {"date": "2024-01-05", "value": "2000.0"},
    {"date": "2024-01-04", "value": "1980.0"},
]


class TestWCIHappyPath:
    @respx.mock
    def test_collect_json_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WCI_SOURCE_URL", "http://wci.test/data")
        from app.config import get_settings
        get_settings.cache_clear()

        respx.get("http://wci.test/data").mock(
            return_value=httpx.Response(
                200,
                json=_JSON_RESPONSE,
                headers={"content-type": "application/json"},
            )
        )
        collector = WCICollector()
        session = _make_session()

        with patch.object(collector, "_upsert_freight_index") as mock_upsert:
            result = collector.collect(session)

        assert result == 2
        assert mock_upsert.call_count == 2
        call_kwargs = mock_upsert.call_args_list[0][1]
        assert call_kwargs["value"] == 2000.0

    @respx.mock
    def test_collect_csv_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WCI_SOURCE_URL", "http://wci.test/data.csv")
        from app.config import get_settings
        get_settings.cache_clear()

        csv_body = "date,value\n2024-01-05,2000.0\n2024-01-04,1980.0\n"
        respx.get("http://wci.test/data.csv").mock(
            return_value=httpx.Response(200, text=csv_body, headers={"content-type": "text/csv"})
        )
        collector = WCICollector()
        session = _make_session()

        with patch.object(collector, "_upsert_freight_index") as mock_upsert:
            result = collector.collect(session)

        assert result == 2


class TestWCIEmptyUrl:
    def test_empty_url_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WCI_SOURCE_URL", "")
        from app.config import get_settings
        get_settings.cache_clear()

        collector = WCICollector()
        session = _make_session()

        with respx.mock:
            result = collector.collect(session)

        assert result == 0
        assert not respx.calls
