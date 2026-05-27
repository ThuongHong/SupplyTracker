"""Tests for app.config — offline, no DB required."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the minimum required env vars for Settings to instantiate."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/testdb")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    monkeypatch.setenv("PORTWATCH_BASE_URL", "https://portwatch.imf.org/api")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("VITE_API_BASE_URL", "http://localhost:8000")


def test_get_settings_returns_settings_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings() should return a Settings instance when env is valid."""
    _base_env(monkeypatch)
    # Clear lru_cache so monkeypatched env is picked up
    get_settings.cache_clear()
    s = get_settings()
    assert isinstance(s, Settings)
    get_settings.cache_clear()


def test_cors_origins_parsed_from_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """CORS_ORIGINS env var (comma-separated) should be parsed into a list."""
    _base_env(monkeypatch)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    get_settings.cache_clear()
    s = get_settings()
    assert s.cors_origins == ["http://localhost:5173", "http://localhost:3000"]
    get_settings.cache_clear()


def test_fred_series_parsed_from_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """FRED_SERIES env var (comma-separated) should be parsed into a list."""
    _base_env(monkeypatch)
    monkeypatch.setenv("FRED_SERIES", "DCOILBRENTEU,DCOILWTICO,DGS10")
    get_settings.cache_clear()
    s = get_settings()
    assert s.fred_series == ["DCOILBRENTEU", "DCOILWTICO", "DGS10"]
    get_settings.cache_clear()


def test_bunker_fields_parsed_from_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """BUNKER_PORTS and BUNKER_FUEL_TYPES should parse CSV into lists."""
    _base_env(monkeypatch)
    monkeypatch.setenv("BUNKER_PORTS", "SGSIN,AEFJR,NLRTM")
    monkeypatch.setenv("BUNKER_FUEL_TYPES", "VLSFO,MGO")
    get_settings.cache_clear()
    s = get_settings()
    assert s.bunker_ports == ["SGSIN", "AEFJR", "NLRTM"]
    assert s.bunker_fuel_types == ["VLSFO", "MGO"]
    get_settings.cache_clear()


def test_invalid_environment_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "prod")  # not a valid Literal value
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_missing_required_field_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()
