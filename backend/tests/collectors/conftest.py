from __future__ import annotations

import pytest

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _collector_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused:unused@localhost/unused")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    monkeypatch.setenv("PORTWATCH_BASE_URL", "http://portwatch.test")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "http://dashscope.test")
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("VITE_API_BASE_URL", "http://localhost:5173")
    yield
    get_settings.cache_clear()
