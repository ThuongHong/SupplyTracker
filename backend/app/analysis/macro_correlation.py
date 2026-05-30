"""Per-entity macro sensitivity via lead-lag correlation.

Pure, dependency-free helpers (no DB, no ORM) so they are unit-testable in
isolation. A *series* is ``list[{"time": iso8601, "value": float}]``.

The headline function is :func:`macro_sensitivity`: scan every macro index
against every entity trade metric, run a lead-lag Pearson scan, and return the
strongest few findings as plain-English insight lines.
"""
from __future__ import annotations

import math
from typing import Any

# macro index_name -> display label
_MACRO_LABELS = {"DCOILBRENTEU": "Brent"}
# metric_name -> display label
_METRIC_LABELS = {
    "port_calls": "port calls",
    "import_volume": "import volume",
    "export_volume": "export volume",
    "transit_calls": "transit calls",
}


def _day(point: dict[str, Any]) -> str:
    return str(point["time"])[:10]


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def align(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> tuple[list[float], list[float]]:
    """Inner-join two series on day; return paired x/y in date order.

    Days where either value is missing or non-finite are dropped.
    """
    a_by_day = {_day(p): p["value"] for p in a if _finite(p["value"])}
    b_by_day = {_day(p): p["value"] for p in b if _finite(p["value"])}
    xs: list[float] = []
    ys: list[float] = []
    for day in sorted(a_by_day.keys() & b_by_day.keys()):
        xs.append(float(a_by_day[day]))
        ys.append(float(b_by_day[day]))
    return xs, ys


def pearson(xs: list[float], ys: list[float], min_n: int = 10) -> float | None:
    """Pearson correlation. None if too few points or either side flat."""
    n = len(xs)
    if n < min_n or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    var_x = sum(d * d for d in dx)
    var_y = sum(d * d for d in dy)
    if var_x == 0 or var_y == 0:
        return None
    cov = sum(a * b for a, b in zip(dx, dy, strict=True))
    return cov / math.sqrt(var_x * var_y)


def _shift_days(series: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    """Move each point's day forward by ``days`` (string-date arithmetic via index).

    Implemented by relabelling days through a date offset so alignment matches a
    later metric date. Uses :mod:`datetime` for correctness across month bounds.
    """
    from datetime import date, timedelta

    shifted: list[dict[str, Any]] = []
    for p in series:
        d = date.fromisoformat(_day(p)) + timedelta(days=days)
        shifted.append({"time": d.isoformat(), "value": p["value"]})
    return shifted


def best_lag(
    macro: list[dict[str, Any]],
    metric: list[dict[str, Any]],
    max_lag: int = 14,
    min_overlap: int = 10,
) -> tuple[float, int, int] | None:
    """Find the lag (0..max_lag) where macro best explains metric.

    Macro is shifted *forward* by ``k`` days (macro leads trade by k), aligned with
    metric, and correlated. Returns ``(r, lag_days, n)`` for the k with the largest
    ``|r|`` that meets ``min_overlap``; None if no lag qualifies.
    """
    best: tuple[float, int, int] | None = None
    for k in range(max_lag + 1):
        xs, ys = align(_shift_days(macro, k), metric)
        r = pearson(xs, ys, min_n=min_overlap)
        if r is None:
            continue
        if best is None or abs(r) > abs(best[0]):
            best = (r, k, len(xs))
    return best


def _strength(r: float) -> str:
    a = abs(r)
    if a < 0.3:
        return "weak"
    if a < 0.6:
        return "moderate"
    return "strong"


def _insight(macro_label: str, metric_label: str, r: float, lag: int, n: int) -> str:
    direction = "inverse" if r < 0 else "positive"
    strength = _strength(r)
    if lag == 0:
        lag_part = f"moves with {metric_label}"
    else:
        lag_part = f"leads {metric_label} by {lag}d"
    return (
        f"{macro_label} {lag_part} — {strength} {direction} "
        f"(r={r:+.2f}, n={n})"
    )


def macro_sensitivity(
    macro_series_by_name: dict[str, list[dict[str, Any]]],
    metric_series_by_name: dict[str, list[dict[str, Any]]],
    max_lag: int = 14,
    min_overlap: int = 10,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Scan every (macro, metric) pair, rank by |r|, return the top_k findings."""
    findings: list[dict[str, Any]] = []
    for macro_name, macro_series in macro_series_by_name.items():
        for metric_name, metric_series in metric_series_by_name.items():
            result = best_lag(macro_series, metric_series, max_lag, min_overlap)
            if result is None:
                continue
            r, lag, n = result
            macro_label = _MACRO_LABELS.get(macro_name, macro_name)
            metric_label = _METRIC_LABELS.get(metric_name, metric_name)
            findings.append(
                {
                    "macro": macro_label,
                    "metric": metric_name,
                    "r": round(r, 3),
                    "lag_days": lag,
                    "n": n,
                    "strength": _strength(r),
                    "insight": _insight(macro_label, metric_label, r, lag, n),
                }
            )
    findings.sort(key=lambda f: abs(f["r"]), reverse=True)
    return findings[:top_k]
