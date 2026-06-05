from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from app.services.dashboard import _build_indices_chart


class _Query:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def filter(self, *args: Any) -> _Query:
        return self

    def order_by(self, *args: Any) -> _Query:
        return self

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _Session:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def query(self, *args: Any) -> _Query:
        return _Query(self._rows)


def _row(day: int, index_name: str, value: float) -> SimpleNamespace:
    return SimpleNamespace(
        time=datetime(2026, 1, day, tzinfo=UTC),
        index_name=index_name,
        value=value,
    )


def test_indices_chart_maps_fred_freight_proxies_to_existing_series_keys() -> None:
    rows = [
        _row(1, "DCOILBRENTEU", 80.0),
        _row(1, "FRGEXPUSM649NCIS", 130.0),
        _row(1, "FRGSHPUSM649NCIS", 90.0),
        _row(1, "PCU483111483111", 240.0),
        _row(2, "FRGSHPUSM649NCIS", 91.0),
    ]

    session = cast(Any, _Session(rows))
    chart = _build_indices_chart(session, datetime(2026, 1, 1, tzinfo=UTC))

    assert chart == [
        {"time": "2026-01-01", "fbx": 130.0, "wci": 240.0},
        {"time": "2026-01-02", "fbx": 91.0},
    ]
