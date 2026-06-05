"""Shared fixtures for task tests."""
from __future__ import annotations

import os

import pytest

# Set required environment variables BEFORE any app module is imported — task
# modules import `app.tasks.celery_app`, which calls `get_settings()` at import.
_REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/testdb",
    "REDIS_URL": "redis://localhost:6379/0",
    "CELERY_BROKER_URL": "redis://localhost:6379/1",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/2",
    "PORTWATCH_BASE_URL": "https://portwatch.imf.org/api",
    "DASHSCOPE_BASE_URL": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "DASHSCOPE_API_KEY": "test-api-key",
    "SMTP_HOST": "localhost",
    "SMTP_PORT": "1025",
    "VITE_API_BASE_URL": "http://localhost:8000",
    "SYNC_BEARER_TOKEN": "test-secret-token",
}

for _key, _val in _REQUIRED_ENV.items():
    os.environ.setdefault(_key, _val)


from app.config import Settings, get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key, val in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, val)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
