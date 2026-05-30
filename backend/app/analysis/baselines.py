from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import PortWatchMetric


def compute_baselines(
    session: Session,
    entity_type: str,
    entity_id: str,
    as_of_date: date,
    metric_name: str,
    window_days: int,
) -> dict[str, float | None]:
    """Query PortWatchMetric for window_days before as_of_date and return mean/stdev/count.

    Returns {"mean": float | None, "stdev": float | None, "count": int}.
    mean and stdev are None when no data is present.
    """
    window_start = datetime(
        as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=UTC
    ) - timedelta(days=window_days)
    window_end = datetime(
        as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=UTC
    )

    rows = (
        session.query(PortWatchMetric)
        .filter(
            PortWatchMetric.entity_type == entity_type,
            PortWatchMetric.entity_id == entity_id,
            PortWatchMetric.metric_name == metric_name,
            PortWatchMetric.observed_at >= window_start,
            PortWatchMetric.observed_at < window_end,
        )
        .all()
    )

    values = [r.metric_value for r in rows]
    return summarize_values(values)


def summarize_values(values: list[float]) -> dict[str, float | None]:
    """Return mean/stdev plus robust median/MAD summary stats for a value list.

    Robust stats (median, MAD) are spike-resistant and preferred for scoring;
    mean/stdev are retained for backward compatibility and reporting.
    """
    count = len(values)

    if count == 0:
        return {"mean": None, "stdev": None, "count": 0, "median": None, "mad": None}

    mean = sum(values) / count
    if count == 1:
        stdev = None
    else:
        variance = sum((v - mean) ** 2 for v in values) / (count - 1)
        stdev = math.sqrt(variance)

    median = _median(values)
    if count == 1:
        mad = None
    else:
        mad = _median([abs(v - median) for v in values])

    return {
        "mean": mean,
        "stdev": stdev,
        "count": count,
        "median": median,
        "mad": mad,
    }


def _median(values: list[float]) -> float:
    """Median of a non-empty list."""
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def compute_z_score(value: float, mean: float, stdev: float | None) -> float | None:
    """Return (value - mean) / stdev, or None if stdev is None or zero."""
    if stdev is None or stdev == 0.0:
        return None
    return (value - mean) / stdev


# Scale factor making MAD a consistent estimator of stdev for normal data.
_MAD_TO_STDEV = 1.4826


def compute_robust_z_score(
    value: float, median: float | None, mad: float | None
) -> float | None:
    """Robust z-score: (value - median) / (1.4826 * MAD).

    Returns None when median/MAD are unavailable or MAD is zero. The 1.4826
    factor rescales MAD so the result is comparable to a classic z-score.
    """
    if median is None or mad is None or mad == 0.0:
        return None
    return (value - median) / (_MAD_TO_STDEV * mad)
