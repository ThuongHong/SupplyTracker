from __future__ import annotations

import pytest

from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Prevent any developer's local backend/.env from leaking into tests.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
