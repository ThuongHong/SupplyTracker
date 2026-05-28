from __future__ import annotations

from pydantic import BaseModel


class RiskSnapshotEmbed(BaseModel):
    composite_score: float | None = None
    trend: str | None = None
    components: dict[str, float] = {}
    updated_at: str | None = None


class MetricPoint(BaseModel):
    time: str
    value: float


class PortMetricsResponse(BaseModel):
    entity_id: str
    metrics: dict[str, list[MetricPoint]]


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
    coordinates: list[float] | None = None
    lat: float | None = None
    lon: float | None = None
    severity: str | None = None
    risk_score: float | None = None
    risk_snapshot: RiskSnapshotEmbed | None = None
    updated_at: str | None = None
    unlocode: str | None = None

    model_config = {"from_attributes": True}


class PortsResponse(BaseModel):
    items: list[PortListItem]
    total: int
    limit: int
    offset: int
    has_more: bool
