from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.analysis.baselines import compute_baselines, compute_z_score


def _make_metric_row(value: float, observed_at: datetime) -> MagicMock:
    row = MagicMock()
    row.metric_value = value
    row.observed_at = observed_at
    return row


def _make_session_returning(rows: list[MagicMock]) -> MagicMock:
    """Build a MagicMock session whose query chain returns `rows`."""
    session = MagicMock()
    (
        session.query.return_value
        .filter.return_value
        .all.return_value
    ) = rows
    return session


class TestComputeBaselines:
    def test_returns_none_when_no_data(self) -> None:
        session = _make_session_returning([])
        result = compute_baselines(session, "port", "P001", date(2024, 1, 15), "port_calls", 30)
        assert result == {"mean": None, "stdev": None, "count": 0}

    def test_single_row_returns_mean_no_stdev(self) -> None:
        rows = [_make_metric_row(42.0, datetime(2024, 1, 10, tzinfo=timezone.utc))]
        session = _make_session_returning(rows)
        result = compute_baselines(session, "port", "P001", date(2024, 1, 15), "port_calls", 30)
        assert result["mean"] == pytest.approx(42.0)
        assert result["stdev"] is None
        assert result["count"] == 1

    def test_multiple_rows_compute_mean_and_stdev(self) -> None:
        values = [10.0, 20.0, 30.0]
        rows = [
            _make_metric_row(v, datetime(2024, 1, i + 1, tzinfo=timezone.utc))
            for i, v in enumerate(values)
        ]
        session = _make_session_returning(rows)
        result = compute_baselines(session, "port", "P001", date(2024, 2, 1), "port_calls", 30)
        assert result["mean"] == pytest.approx(20.0)
        assert result["stdev"] is not None
        assert result["stdev"] == pytest.approx(10.0)  # sample stdev of [10,20,30]
        assert result["count"] == 3

    def test_mean_computed_correctly_for_two_values(self) -> None:
        rows = [
            _make_metric_row(5.0, datetime(2024, 1, 1, tzinfo=timezone.utc)),
            _make_metric_row(15.0, datetime(2024, 1, 2, tzinfo=timezone.utc)),
        ]
        session = _make_session_returning(rows)
        result = compute_baselines(session, "port", "P001", date(2024, 1, 31), "dwell_hours", 30)
        assert result["mean"] == pytest.approx(10.0)
        assert result["count"] == 2


class TestComputeZScore:
    def test_positive_z_score(self) -> None:
        z = compute_z_score(15.0, 10.0, 5.0)
        assert z == pytest.approx(1.0)

    def test_negative_z_score(self) -> None:
        z = compute_z_score(5.0, 10.0, 5.0)
        assert z == pytest.approx(-1.0)

    def test_zero_stdev_returns_none(self) -> None:
        z = compute_z_score(10.0, 10.0, 0.0)
        assert z is None

    def test_none_stdev_returns_none(self) -> None:
        z = compute_z_score(10.0, 10.0, None)
        assert z is None

    def test_z_score_exact_mean_is_zero(self) -> None:
        z = compute_z_score(10.0, 10.0, 2.0)
        assert z == pytest.approx(0.0)
