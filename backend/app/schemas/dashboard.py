from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EntityInfo(BaseModel):
    type: str
    id: str
    name: str


class DashboardStats(BaseModel):
    risk_latest: float | None = None
    risk_30d_mean: float | None = None
    risk_30d_max: float | None = None
    dwell_latest: float | None = None
    vessel_count_latest: int | None = None
    fbx_pct_7d: float | None = None


class DisruptionItem(BaseModel):
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    severity: str
    confidence: float
    explanation: str
    started_at: str
    status: str


class DashboardResponse(BaseModel):
    entity: EntityInfo
    window: str
    charts: dict[str, list[dict[str, Any]]]
    stats: DashboardStats
    disruptions: list[DisruptionItem]
