from __future__ import annotations

from pydantic import BaseModel


class PortListItem(BaseModel):
    id: int
    locode: str | None
    name: str
    country: str
    region: str | None
    severity: str | None = None

    model_config = {"from_attributes": True}


class PortDetail(BaseModel):
    id: int
    locode: str | None
    name: str
    country: str
    region: str | None
    radius_km: float
    twenty_ft_eq_units_year: int | None
    coordinates: list[float] | None = None  # [lon, lat]
    severity: str | None = None

    model_config = {"from_attributes": True}


class PortsResponse(BaseModel):
    items: list[PortListItem]
    total: int
    limit: int
    offset: int
    has_more: bool
