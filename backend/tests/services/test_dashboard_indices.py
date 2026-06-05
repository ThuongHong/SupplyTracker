from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from app.services.dashboard import _build_indices_chart


class _Query:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def filter(self, *args: Any) -> _Query:
        for expr in args:
            threshold = getattr(getattr(expr, "right", None), "value", None)
            if isinstance(threshold, datetime):
                self._rows = [row for row in self._rows if row.time >= threshold]
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


def _dated_row(
    year: int, month: int, day: int, index_name: str, value: float
) -> SimpleNamespace:
    return SimpleNamespace(
        time=datetime(year, month, day, tzinfo=UTC),
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


def test_indices_chart_keeps_monthly_fred_proxy_data_for_short_windows() -> None:
    rows = [
        _dated_row(2026, 4, 1, "FRGEXPUSM649NCIS", 130.0),
        _dated_row(2026, 4, 1, "PCU483111483111", 240.0),
    ]

    session = cast(Any, _Session(rows))
    chart = _build_indices_chart(session, datetime(2026, 5, 6, tzinfo=UTC))

    assert chart == [{"time": "2026-04-01", "fbx": 130.0, "wci": 240.0}]


def _instant_row(when: datetime, index_name: str, value: float) -> SimpleNamespace:
    return SimpleNamespace(time=when, index_name=index_name, value=value)


def test_indices_chart_floor_keeps_a_full_year_for_short_windows() -> None:
    """A short UI window still surfaces ~12 months of monthly freight data."""
    now = datetime.now(tz=UTC)
    rows = [
        _instant_row(now - timedelta(days=300), "FRGEXPUSM649NCIS", 120.0),
        _instant_row(now - timedelta(days=30), "FRGEXPUSM649NCIS", 130.0),
    ]

    session = cast(Any, _Session(rows))
    # 30-day window — without the year floor only the recent point would show.
    chart = _build_indices_chart(session, now - timedelta(days=30))

    assert [c["fbx"] for c in chart] == [120.0, 130.0]


def test_indices_chart_floor_excludes_data_older_than_a_year() -> None:
    now = datetime.now(tz=UTC)
    rows = [
        _instant_row(now - timedelta(days=400), "FRGEXPUSM649NCIS", 120.0),
        _instant_row(now - timedelta(days=30), "FRGEXPUSM649NCIS", 130.0),
    ]

    session = cast(Any, _Session(rows))
    chart = _build_indices_chart(session, now - timedelta(days=30))

    assert [c["fbx"] for c in chart] == [130.0]
