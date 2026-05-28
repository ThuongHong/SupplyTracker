from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import desc, func

from app.api.deps import DbSession
from app.db.models import (
    ChokepointRiskScore,
    EntityRiskForecast,
    PortRiskScore,
    RiskFeatureSnapshot,
)
from app.schemas.risk import (
    ForecastResponse,
    RiskScoreDetail,
    RiskScoreListItem,
    RiskScoresListResponse,
    SnapshotSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["risk"])

_FORECAST_STALE_HOURS = 25


def _get_latest_scores(db: DbSession) -> list[RiskScoreListItem]:
    """Return the latest risk score row per entity across both port and chokepoint tables."""
    results: list[RiskScoreListItem] = []

    # Port risk scores — latest per entity_id
    port_subq = (
        db.query(
            PortRiskScore.entity_id,
            func.max(PortRiskScore.as_of).label("max_as_of"),
        )
        .group_by(PortRiskScore.entity_id)
        .subquery()
    )
    port_rows = (
        db.query(PortRiskScore)
        .join(
            port_subq,
            (PortRiskScore.entity_id == port_subq.c.entity_id)
            & (PortRiskScore.as_of == port_subq.c.max_as_of),
        )
        .all()
    )
    for row in port_rows:
        results.append(
            RiskScoreListItem(
                entity_type="port",
                entity_id=row.entity_id,
                entity_name=row.entity_name,
                score=row.score,
                severity=row.severity,
                freshness_status=row.freshness_status,
                as_of=row.as_of,
                time=row.time,
            )
        )

    # Chokepoint risk scores — latest per entity_id
    cp_subq = (
        db.query(
            ChokepointRiskScore.entity_id,
            func.max(ChokepointRiskScore.as_of).label("max_as_of"),
        )
        .group_by(ChokepointRiskScore.entity_id)
        .subquery()
    )
    cp_rows = (
        db.query(ChokepointRiskScore)
        .join(
            cp_subq,
            (ChokepointRiskScore.entity_id == cp_subq.c.entity_id)
            & (ChokepointRiskScore.as_of == cp_subq.c.max_as_of),
        )
        .all()
    )
    for cp_row in cp_rows:
        results.append(
            RiskScoreListItem(
                entity_type="chokepoint",
                entity_id=cp_row.entity_id,
                entity_name=cp_row.entity_name,
                score=cp_row.score,
                severity=cp_row.severity,
                freshness_status=cp_row.freshness_status,
                as_of=cp_row.as_of,
                time=cp_row.time,
            )
        )

    # Sort by severity desc, then score desc
    _severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "minimal": 4}
    results.sort(
        key=lambda x: (_severity_order.get(x.severity, 99), -(x.score or 0))
    )
    return results


@router.get("/risk/scores", response_model=RiskScoresListResponse)
def list_risk_scores(db: DbSession) -> RiskScoresListResponse:
    """List the latest risk score per entity (ports + chokepoints)."""
    items = _get_latest_scores(db)
    return RiskScoresListResponse(items=items)


@router.get("/risk/scores/{entity_ref}", response_model=RiskScoreDetail)
def get_risk_score(
    db: DbSession,
    entity_ref: str = Path(description="Format: entity_type:entity_id e.g. port:SGSIN"),
) -> RiskScoreDetail:
    """Return the latest risk score + matching RiskFeatureSnapshot for an entity."""
    if ":" not in entity_ref:
        raise HTTPException(
            status_code=422,
            detail="entity_ref must be in format 'entity_type:entity_id'",
        )
    entity_type, entity_id = entity_ref.split(":", 1)

    row: PortRiskScore | ChokepointRiskScore | None = None
    if entity_type == "port":
        row = (
            db.query(PortRiskScore)
            .filter(PortRiskScore.entity_id == entity_id)
            .order_by(desc(PortRiskScore.as_of))
            .first()
        )
    elif entity_type == "chokepoint":
        row = (
            db.query(ChokepointRiskScore)
            .filter(ChokepointRiskScore.entity_id == entity_id)
            .order_by(desc(ChokepointRiskScore.as_of))
            .first()
        )
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown entity_type '{entity_type}'. Must be 'port' or 'chokepoint'.",
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No risk score found for {entity_ref}",
        )

    # Fetch latest snapshot
    snapshot_row = (
        db.query(RiskFeatureSnapshot)
        .filter(
            RiskFeatureSnapshot.entity_type == entity_type,
            RiskFeatureSnapshot.entity_id == entity_id,
        )
        .order_by(desc(RiskFeatureSnapshot.snapshot_date))
        .first()
    )

    snapshot: SnapshotSummary | None = None
    if snapshot_row:
        snapshot = SnapshotSummary(
            snapshot_date=snapshot_row.snapshot_date,
            feature_values=snapshot_row.feature_values,
            baseline_values=snapshot_row.baseline_values,
            z_scores=snapshot_row.z_scores,
            deltas=snapshot_row.deltas,
            missing_features=snapshot_row.missing_features,
            driver_metadata=snapshot_row.driver_metadata,
        )

    return RiskScoreDetail(
        entity_type=entity_type,
        entity_id=row.entity_id,
        entity_name=row.entity_name,
        score=row.score,
        severity=row.severity,
        component_scores=row.component_scores,
        missing_components=row.missing_components,
        reasons=row.reasons,
        source_metrics=row.source_metrics,
        freshness_status=row.freshness_status,
        as_of=row.as_of,
        time=row.time,
        snapshot=snapshot,
    )


@router.get("/risk/forecasts/{entity_ref}", response_model=ForecastResponse)
def get_risk_forecast(
    db: DbSession,
    entity_ref: str = Path(description="Format: entity_type:entity_id e.g. port:SGSIN"),
) -> ForecastResponse:
    """Return forecast detail for an entity, with staleness flag if older than 25h."""
    if ":" not in entity_ref:
        raise HTTPException(
            status_code=422,
            detail="entity_ref must be in format 'entity_type:entity_id'",
        )
    entity_type, entity_id = entity_ref.split(":", 1)

    forecast = (
        db.query(EntityRiskForecast)
        .filter(
            EntityRiskForecast.entity_type == entity_type,
            EntityRiskForecast.entity_id == entity_id,
        )
        .order_by(desc(EntityRiskForecast.created_at))
        .first()
    )

    if forecast is None:
        raise HTTPException(
            status_code=404,
            detail=f"No forecast found for {entity_ref}",
        )

    # Staleness gate: if created_at is older than 25h
    now_utc = datetime.now(tz=UTC)
    forecast_created = forecast.created_at
    if forecast_created.tzinfo is None:
        forecast_created = forecast_created.replace(tzinfo=UTC)
    stale = (now_utc - forecast_created) > timedelta(hours=_FORECAST_STALE_HOURS)

    return ForecastResponse(
        forecast_key=forecast.forecast_key,
        entity_type=forecast.entity_type,
        entity_id=forecast.entity_id,
        entity_name=forecast.entity_name,
        horizon_days=forecast.horizon_days,
        predictions=forecast.predictions,
        confidence=forecast.confidence,
        train_window_start=forecast.train_window_start,
        train_window_end=forecast.train_window_end,
        data_sufficiency_status=forecast.data_sufficiency_status,
        unavailable_reason=forecast.unavailable_reason,
        key_drivers=forecast.key_drivers,
        metrics=forecast.metrics,
        model_name=forecast.model_name,
        feature_schema_version=forecast.feature_schema_version,
        created_at=forecast.created_at,
        stale=stale,
    )
