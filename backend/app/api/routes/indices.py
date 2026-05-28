from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc

from app.api.deps import DbSession
from app.db.models import FreightIndex
from app.schemas.indices import (
    FreightIndexItem,
    FreightIndexListResponse,
    TimeseriesPoint,
    TimeseriesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["indices"])


def _pct_change(new_val: float | None, old_val: float | None) -> float | None:
    if new_val is None or old_val is None or old_val == 0:
        return None
    return round((new_val - old_val) / abs(old_val) * 100, 4)


@router.get("/indices", response_model=FreightIndexListResponse)
def list_indices(db: DbSession) -> FreightIndexListResponse:
    """List all freight indices with latest value and 7d/30d change percentages."""
    # Get distinct index names
    index_names: list[str] = [
        row[0] for row in db.query(FreightIndex.index_name).distinct().all()
    ]

    items: list[FreightIndexItem] = []
    for name in sorted(index_names):
        # Latest entry
        latest = (
            db.query(FreightIndex)
            .filter(FreightIndex.index_name == name)
            .order_by(desc(FreightIndex.time))
            .first()
        )
        if latest is None:
            continue

        latest_val = latest.value
        latest_time = latest.time
        source = latest.source

        # 7 days ago
        cutoff_7d = latest_time - timedelta(days=7)
        row_7d = (
            db.query(FreightIndex)
            .filter(
                FreightIndex.index_name == name,
                FreightIndex.time <= cutoff_7d,
            )
            .order_by(desc(FreightIndex.time))
            .first()
        )
        val_7d = row_7d.value if row_7d else None

        # 30 days ago
        cutoff_30d = latest_time - timedelta(days=30)
        row_30d = (
            db.query(FreightIndex)
            .filter(
                FreightIndex.index_name == name,
                FreightIndex.time <= cutoff_30d,
            )
            .order_by(desc(FreightIndex.time))
            .first()
        )
        val_30d = row_30d.value if row_30d else None

        items.append(
            FreightIndexItem(
                index_name=name,
                source=source,
                latest_value=latest_val,
                latest_time=latest_time,
                change_pct_7d=_pct_change(latest_val, val_7d),
                change_pct_30d=_pct_change(latest_val, val_30d),
            )
        )

    return FreightIndexListResponse(items=items)


@router.get("/indices/{index_name}/timeseries", response_model=TimeseriesResponse)
def get_index_timeseries(index_name: str, db: DbSession) -> TimeseriesResponse:
    """Return full timeseries for a single freight index."""
    rows = (
        db.query(FreightIndex)
        .filter(FreightIndex.index_name == index_name)
        .order_by(FreightIndex.time)
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No timeseries data found for index '{index_name}'",
        )

    points = [TimeseriesPoint(time=r.time, value=r.value) for r in rows]
    return TimeseriesResponse(index_name=index_name, points=points)
