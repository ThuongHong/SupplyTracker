from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FreightIndexItem(BaseModel):
    index_name: str
    source: str
    latest_value: float | None
    latest_time: datetime | None
    change_pct_7d: float | None
    change_pct_30d: float | None


class FreightIndexListResponse(BaseModel):
    items: list[FreightIndexItem]


class TimeseriesPoint(BaseModel):
    time: datetime
    value: float


class TimeseriesResponse(BaseModel):
    index_name: str
    points: list[TimeseriesPoint]
