from __future__ import annotations

import pytest

from app.analysis.macro_correlation import (
    align,
    best_lag,
    macro_sensitivity,
    pearson,
)


def _series(start_day: int, values: list[float]) -> list[dict]:
    """Build a daily {time,value} series starting 2026-01-{start_day}."""
    return [
        {"time": f"2026-01-{start_day + i:02d}T00:00:00+00:00", "value": v}
        for i, v in enumerate(values)
    ]


class TestPearson:
    def test_perfect_positive(self) -> None:
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        assert pearson(xs, ys, min_n=3) == pytest.approx(1.0)

    def test_perfect_negative(self) -> None:
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [10.0, 8.0, 6.0, 4.0, 2.0]
        assert pearson(xs, ys, min_n=3) == pytest.approx(-1.0)

    def test_below_min_n_returns_none(self) -> None:
        assert pearson([1.0, 2.0], [2.0, 4.0], min_n=5) is None

    def test_zero_variance_returns_none(self) -> None:
        assert pearson([3.0, 3.0, 3.0, 3.0], [1.0, 2.0, 3.0, 4.0], min_n=3) is None


class TestAlign:
    def test_intersection_only_in_date_order(self) -> None:
        a = _series(1, [1.0, 2.0, 3.0])  # days 1,2,3
        b = _series(2, [20.0, 30.0, 40.0])  # days 2,3,4
        xs, ys = align(a, b)
        # overlap: day2 (2.0 / 20.0), day3 (3.0 / 30.0)
        assert xs == [2.0, 3.0]
        assert ys == [20.0, 30.0]

    def test_skips_non_finite(self) -> None:
        a = _series(1, [1.0, float("nan"), 3.0])
        b = _series(1, [10.0, 20.0, 30.0])
        xs, ys = align(a, b)
        assert xs == [1.0, 3.0]
        assert ys == [10.0, 30.0]


class TestBestLag:
    def test_recovers_known_lag(self) -> None:
        # metric mirrors macro shifted by 3 days: macro leads metric by 3.
        base = [float(v) for v in [1, 3, 2, 5, 4, 6, 8, 7, 9, 11, 10, 12, 14, 13]]
        macro = _series(1, base)
        metric = _series(4, base)  # metric values start 3 days later
        result = best_lag(macro, metric, max_lag=14, min_overlap=5)
        assert result is not None
        r, lag, n = result
        assert lag == 3
        assert r == pytest.approx(1.0)
        assert n >= 5

    def test_insufficient_overlap_returns_none(self) -> None:
        macro = _series(1, [1.0, 2.0])
        metric = _series(1, [2.0, 4.0])
        assert best_lag(macro, metric, max_lag=14, min_overlap=10) is None


class TestMacroSensitivity:
    def test_ranks_by_abs_r_and_respects_top_k(self) -> None:
        n = 14
        up = _series(1, [float(i) for i in range(n)])
        down = _series(1, [float(n - i) for i in range(n)])
        noise = _series(1, [float((i * 7) % 5) for i in range(n)])

        macro = {"Brent": up}
        metrics = {
            "port_calls": up,  # r = +1
            "import_volume": down,  # r = -1
            "export_volume": noise,  # weaker
        }
        findings = macro_sensitivity(macro, metrics, max_lag=14, top_k=2)
        assert len(findings) == 2
        assert abs(findings[0]["r"]) >= abs(findings[1]["r"])
        # both top findings are strong |r| ~ 1
        assert abs(findings[0]["r"]) == pytest.approx(1.0)

    def test_finding_shape_and_insight(self) -> None:
        n = 14
        up = _series(1, [float(i) for i in range(n)])
        down = _series(1, [float(n - i) for i in range(n)])
        findings = macro_sensitivity({"Brent": up}, {"port_calls": down}, top_k=1)
        f = findings[0]
        assert set(f) == {"macro", "metric", "r", "lag_days", "n", "strength", "insight"}
        assert f["macro"] == "Brent"
        assert f["metric"] == "port_calls"
        assert f["strength"] == "strong"
        assert "port calls" in f["insight"]
        assert "inverse" in f["insight"]

    def test_empty_when_no_overlap(self) -> None:
        macro = {"Brent": _series(1, [1.0, 2.0])}
        metrics = {"port_calls": _series(1, [2.0, 1.0])}
        assert macro_sensitivity(macro, metrics, min_overlap=10) == []

    def test_strength_buckets(self) -> None:
        # weak: |r| < 0.3
        from app.analysis.macro_correlation import _strength

        assert _strength(0.1) == "weak"
        assert _strength(0.45) == "moderate"
        assert _strength(0.8) == "strong"
