from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EntityInfo(BaseModel):
    type: str
    id: str
    name: str


class AnomalyStats(BaseModel):
    """Probability-hypothesis stats for the throughput metric (z-score test)."""

    metric: str | None = None
    latest: float | None = None
    mean: float | None = None
    std: float | None = None
    z_score: float | None = None
    p_value: float | None = None
    anomaly_level: str | None = None  # low | elevated | high
    baseline_n: int | None = None


class DashboardStats(BaseModel):
    risk_latest: float | None = None
    risk_30d_mean: float | None = None
    risk_30d_max: float | None = None
    dwell_latest: float | None = None
    vessel_count_latest: int | None = None
    fbx_pct_7d: float | None = None
    anomaly: AnomalyStats | None = None


class MacroCorrelation(BaseModel):
    """Lead-lag correlation between a macro index and an entity trade metric."""

    macro: str
    metric: str
    r: float
    lag_days: int
    n: int
    strength: str  # weak | moderate | strong
    insight: str


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
    macro_sensitivity: list[MacroCorrelation] = []


class EntitySummaryResponse(BaseModel):
    entity: EntityInfo
    window: str
    narrative: str
    what_happened: str
    so_what: str
    to_do: str
    stats: AnomalyStats  # headline (most anomalous) metric
    metrics: list[AnomalyStats] = []  # all summarized metrics, ranked by |z|
