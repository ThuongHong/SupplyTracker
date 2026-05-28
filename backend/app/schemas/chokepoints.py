from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel

from app.schemas.ports import MetricPoint, RiskSnapshotEmbed


class ChokepointListItem(BaseModel):
    id: int
    name: str
    severity: str | None = None

    model_config = {"from_attributes": True}


class ChokepointDetail(BaseModel):
    id: int
    name: str
    severity: str | None = None
    coordinates: list[list[float]] | None = None
    lat: float | None = None
    lon: float | None = None
    risk_score: float | None = None
    risk_snapshot: RiskSnapshotEmbed | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class ChokepointMetricsResponse(BaseModel):
    entity_id: str
    metrics: dict[str, list[MetricPoint]]


class ChokepointsResponse(BaseModel):
    items: list[ChokepointListItem]
    total: int
    limit: int
    offset: int
    has_more: bool


class ChokepointBreakdownDay(BaseModel):
    date: date
    total: int
    categories: dict[str, Any]


class ChokepointBreakdownResponse(BaseModel):
    chokepoint_id: int
    name: str
    days: list[ChokepointBreakdownDay]
