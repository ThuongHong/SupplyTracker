from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from app.collectors.fred import FREDCollector, _FRED_BASE


def _make_session() -> MagicMock:
    session = MagicMock()
    return session


_FRED_RESPONSE = {
    "observations": [
        {"date": "2024-01-05", "value": "75.3"},
        {"date": "2024-01-04", "value": "74.1"},
        {"date": "2024-01-03", "value": "73.8"},
        {"date": "2024-01-02", "value": "."},
        {"date": "2024-01-01", "value": "72.5"},
    ]
}


class TestFREDHappyPath:
    @respx.mock
    def test_collect_upserts_valid_observations(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FRED_API_KEY", "test_key_123")
        monkeypatch.setenv("FRED_SERIES", "BDIY,FBX")

        from app.config import get_settings
        get_settings.cache_clear()

        respx.get(_FRED_BASE).mock(return_value=httpx.Response(200, json=_FRED_RESPONSE))

        collector = FREDCollector()
        session = _make_session()

        with patch.object(collector, "_upsert_freight_index") as mock_upsert:
            result = collector.collect(session)

        assert mock_upsert.call_count == 8
        assert result.rows == 8

    @respx.mock
    def test_skips_dot_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FRED_API_KEY", "test_key_123")
        monkeypatch.setenv("FRED_SERIES", "BDIY")

        from app.config import get_settings
        get_settings.cache_clear()

        respx.get(_FRED_BASE).mock(return_value=httpx.Response(200, json=_FRED_RESPONSE))

        collector = FREDCollector()
        session = _make_session()

        call_dates: list[str] = []

        def capture(s: object, *, time: object, **kwargs: object) -> None:
            call_dates.append(str(time))

        with patch.object(collector, "_upsert_freight_index", side_effect=capture):
            result = collector.collect(session)

        assert result.rows == 4
        assert not any("2024-01-02" in d for d in call_dates)


class TestFREDMissingKey:
    def test_empty_api_key_raises_no_http(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FRED_API_KEY", "")
        monkeypatch.setenv("FRED_SERIES", "BDIY")

        from app.config import get_settings
        get_settings.cache_clear()

        collector = FREDCollector()
        session = _make_session()

        with respx.mock:
            with pytest.raises(ValueError, match="FRED API key not configured"):
                collector.collect(session)

        assert not respx.calls
