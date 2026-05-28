from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class RiskScoreListItem(BaseModel):
    entity_type: str
    entity_id: str
    entity_name: str
    score: float | None
    severity: str
    freshness_status: str
    as_of: datetime
    time: datetime

    model_config = {"from_attributes": True}


class RiskScoresListResponse(BaseModel):
    items: list[RiskScoreListItem]


class SnapshotSummary(BaseModel):
    snapshot_date: date
    feature_values: dict[str, Any]
    baseline_values: dict[str, Any]
    z_scores: dict[str, Any]
    deltas: dict[str, Any]
    missing_features: list[str] | None
    driver_metadata: dict[str, Any] | None

    model_config = {"from_attributes": True}


class RiskScoreDetail(BaseModel):
    entity_type: str
    entity_id: str
    entity_name: str
    score: float | None
    severity: str
    component_scores: dict[str, Any]
    missing_components: list[str] | None
    reasons: list[str] | None
    source_metrics: dict[str, Any] | None
    freshness_status: str
    as_of: datetime
    time: datetime
    snapshot: SnapshotSummary | None = None

    model_config = {"from_attributes": True}


class ForecastPrediction(BaseModel):
    date: str
    predicted_score: float
    lower_bound: float | None = None
    upper_bound: float | None = None


class ForecastResponse(BaseModel):
    forecast_key: str
    entity_type: str
    entity_id: str
    entity_name: str
    horizon_days: int
    predictions: list[dict[str, Any]]
    confidence: float
    train_window_start: date | None
    train_window_end: date | None
    data_sufficiency_status: str
    unavailable_reason: str | None
    key_drivers: list[str] | None
    metrics: dict[str, Any]
    model_name: str
    feature_schema_version: str
    created_at: datetime
    stale: bool = False

    model_config = {"from_attributes": True}
