"""Tests for the daily forecast pass (tasks/forecast.run_forecast)."""
from __future__ import annotations

from collections import namedtuple
from typing import Any

from app.tasks.forecast import run_forecast

_Row = namedtuple("_Row", "entity_type entity_id entity_name metric_name")


class _FakeQuery:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows

    def distinct(self) -> "_FakeQuery":
        return self

    def all(self) -> list[_Row]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows

    def query(self, *args: Any) -> _FakeQuery:
        return _FakeQuery(self._rows)

    def commit(self) -> None:  # pragma: no cover - trivial
        pass

    def rollback(self) -> None:  # pragma: no cover - trivial
        pass


def test_run_forecast_only_forecasts_charted_throughput_metric(monkeypatch) -> None:
    """Only port_calls (port) and transit_calls (chokepoint) get forecasted —
    the other metrics are skipped so the free-tier job stays under its timeout."""
    rows = [
        _Row("port", "port1", "Singapore", "port_calls"),
        _Row("port", "port1", "Singapore", "import_volume"),
        _Row("port", "port1", "Singapore", "export_volume"),
        _Row("chokepoint", "suez_canal", "Suez Canal", "transit_calls"),
        _Row("chokepoint", "suez_canal", "Suez Canal", "transit_tanker"),
    ]

    def fake_get_db():
        yield _FakeSession(rows)

    calls: list[tuple[str, str]] = []

    def fake_generate_forecast(*, entity_type, metric_name, **kwargs):
        calls.append((entity_type, metric_name))

    monkeypatch.setattr("app.db.session.get_db", fake_get_db)
    monkeypatch.setattr(
        "app.analysis.forecasting.generate_forecast", fake_generate_forecast
    )

    summary = run_forecast.apply().get()

    assert calls == [("port", "port_calls"), ("chokepoint", "transit_calls")]
    assert summary["forecasted"] == 2
    assert summary["combinations_attempted"] == 2
    assert summary["errors"] == 0
