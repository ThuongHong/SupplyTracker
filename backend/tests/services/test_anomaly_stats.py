from __future__ import annotations

import math

from app.services.dashboard import _anomaly_stats, _norm_cdf


def _series(values: list[float]) -> list[dict[str, float]]:
    return [{"time": f"2026-05-{i + 1:02d}", "value": v} for i, v in enumerate(values)]


def test_norm_cdf_known_points() -> None:
    assert math.isclose(_norm_cdf(0.0), 0.5, abs_tol=1e-9)
    assert math.isclose(_norm_cdf(1.96), 0.975, abs_tol=1e-3)


def test_insufficient_history_returns_nulls() -> None:
    stats = _anomaly_stats(_series([10, 11, 12]), "port_calls")
    assert stats.z_score is None
    assert stats.p_value is None
    assert stats.baseline_n == 2


def test_flat_series_zero_variance() -> None:
    stats = _anomaly_stats(_series([50.0] * 12), "port_calls")
    assert stats.std == 0.0
    assert stats.z_score is None
    assert stats.anomaly_level == "low"


def test_known_zscore_and_pvalue() -> None:
    # Baseline of nine 100s (std 0) would be zero-variance, so vary slightly.
    baseline = [100, 102, 98, 101, 99, 100, 103, 97, 100]
    # Latest far above baseline → high z-score.
    stats = _anomaly_stats(_series([*baseline, 140.0]), "port_calls")
    assert stats.z_score is not None and stats.z_score > 2.5
    assert stats.anomaly_level == "high"
    assert stats.p_value is not None and 0.0 <= stats.p_value < 0.05
    assert stats.baseline_n == 9


def test_elevated_level_threshold() -> None:
    # mean=60, sample std≈4.16; latest 68 → z≈1.92 (elevated band).
    baseline = [60, 55, 65, 58, 62, 60, 67, 53, 60, 60]
    stats = _anomaly_stats(_series([*baseline, 68.0]), "transit_calls")
    assert stats.z_score is not None and 1.5 <= abs(stats.z_score) < 2.5
    assert stats.anomaly_level == "elevated"
