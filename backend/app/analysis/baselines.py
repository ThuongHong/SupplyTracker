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
    count = len(values)

    if count == 0:
        return {"mean": None, "stdev": None, "count": 0}

    mean = sum(values) / count
    if count == 1:
        stdev = None
    else:
        variance = sum((v - mean) ** 2 for v in values) / (count - 1)
        stdev = math.sqrt(variance)

    return {"mean": mean, "stdev": stdev, "count": count}


def compute_z_score(value: float, mean: float, stdev: float | None) -> float | None:
    """Return (value - mean) / stdev, or None if stdev is None or zero."""
    if stdev is None or stdev == 0.0:
        return None
    return (value - mean) / stdev
