from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel


class ChokepointListItem(BaseModel):
    id: int
    name: str
    severity: str | None = None

    model_config = {"from_attributes": True}


class ChokepointDetail(BaseModel):
    id: int
    name: str
    severity: str | None = None
    coordinates: list[list[float]] | None = None  # polygon coords [[lon, lat], ...]

    model_config = {"from_attributes": True}


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
