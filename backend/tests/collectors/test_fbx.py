from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.collectors.fbx_scraper import FBXCollector


def _make_session() -> MagicMock:
    return MagicMock()


_JSON_RESPONSE = [
    {"date": "2024-01-05", "value": "1500.0", "route": "GLOBAL"},
    {"date": "2024-01-04", "value": "1480.0", "route": "GLOBAL"},
]


class TestFBXHappyPath:
    @respx.mock
    def test_collect_json_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FBX_SOURCE_URL", "http://fbx.test/data")
        from app.config import get_settings
        get_settings.cache_clear()

        respx.get("http://fbx.test/data").mock(
            return_value=httpx.Response(
                200,
                json=_JSON_RESPONSE,
                headers={"content-type": "application/json"},
            )
        )
        collector = FBXCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_freight_index") as mock_upsert:
            result = collector.collect(session)

        assert result.rows == 2
        assert mock_upsert.call_count == 2
        call_kwargs = mock_upsert.call_args_list[0][1]
        assert call_kwargs["index_name"] == "FBX_GLOBAL"

    @respx.mock
    def test_collect_csv_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FBX_SOURCE_URL", "http://fbx.test/data.csv")
        from app.config import get_settings
        get_settings.cache_clear()

        csv_body = "date,value,route\n2024-01-05,1500.0,ASIA\n2024-01-04,1480.0,ASIA\n"
        respx.get("http://fbx.test/data.csv").mock(
            return_value=httpx.Response(200, text=csv_body, headers={"content-type": "text/csv"})
        )
        collector = FBXCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_freight_index") as mock_upsert:
            result = collector.collect(session)

        assert result.rows == 2


class TestFBXEmptyUrl:
    def test_empty_url_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FBX_SOURCE_URL", "")
        from app.config import get_settings
        get_settings.cache_clear()

        collector = FBXCollector()
        session = _make_session()

        with respx.mock:
            result = collector.collect(session)

        assert result.rows == 0
        assert not respx.calls
