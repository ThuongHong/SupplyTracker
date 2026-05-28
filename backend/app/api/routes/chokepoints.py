from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import Date as SaDate
from sqlalchemy import cast, desc, func, select

from app.api.deps import DbSession
from app.db.models import Chokepoint, ChokepointRiskScore, PortWatchMetric, RiskFeatureSnapshot
from app.schemas.chokepoints import (
    ChokepointBreakdownDay,
    ChokepointBreakdownResponse,
    ChokepointDetail,
    ChokepointListItem,
    ChokepointMetricsResponse,
    ChokepointsResponse,
)
from app.schemas.ports import MetricPoint, RiskSnapshotEmbed

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chokepoints"])

_BREAKDOWN_DAYS = 50
_METRICS_DAYS = 90


def _latest_chokepoint_severity(db: DbSession, entity_id: str) -> str | None:
    row = (
        db.query(ChokepointRiskScore.severity)
        .filter(ChokepointRiskScore.entity_id == entity_id)
        .order_by(desc(ChokepointRiskScore.as_of))
        .first()
    )
    return row[0] if row else None


def _bulk_latest_chokepoint_scores(
    db: DbSession, entity_ids: list[str]
) -> dict[str, tuple[str | None, float | None]]:
    """Return {entity_id: (severity, score)} for the latest score of each given entity_id.

    Replaces N individual queries with 2 queries (max-time subquery + join).
    """
    if not entity_ids:
        return {}

    max_time_sq = (
        select(
            ChokepointRiskScore.entity_id,
            func.max(ChokepointRiskScore.as_of).label("max_as_of"),
        )
        .where(ChokepointRiskScore.entity_id.in_(entity_ids))
        .group_by(ChokepointRiskScore.entity_id)
        .subquery()
    )
    rows = (
        db.query(ChokepointRiskScore)
        .join(
            max_time_sq,
            (ChokepointRiskScore.entity_id == max_time_sq.c.entity_id)
            & (ChokepointRiskScore.as_of == max_time_sq.c.max_as_of),
        )
        .all()
    )
    return {r.entity_id: (r.severity, r.score) for r in rows}


def _chokepoint_entity_id(cp: Chokepoint) -> str:
    return cp.name


def _geom_to_polygon_coords(geom: Any) -> list[list[float]] | None:
    if geom is None:
        return None
    try:
        from geoalchemy2.shape import to_shape
        shape = to_shape(geom)
        coords = list(shape.exterior.coords)
        return [[c[0], c[1]] for c in coords]
    except Exception:  # noqa: BLE001
        return None


def _geom_centroid(geom: Any) -> tuple[float, float] | None:
    """Return (lon, lat) centroid of a polygon WKBElement."""
    if geom is None:
        return None
    try:
        from geoalchemy2.shape import to_shape
        shape = to_shape(geom)
        return shape.centroid.x, shape.centroid.y
    except Exception:  # noqa: BLE001
        return None


def _latest_cp_snapshot(db: Any, entity_id: str) -> RiskSnapshotEmbed | None:
    snap = (
        db.query(RiskFeatureSnapshot)
        .filter(
            RiskFeatureSnapshot.entity_type == "chokepoint",
            RiskFeatureSnapshot.entity_id == entity_id,
        )
        .order_by(desc(RiskFeatureSnapshot.snapshot_date))
        .first()
    )
    if snap is None:
        return None
    return RiskSnapshotEmbed(
        composite_score=snap.risk_score,
        trend=None,
        components={k: float(v) for k, v in (snap.feature_values or {}).items()},
        updated_at=snap.snapshot_date.isoformat() if snap.snapshot_date else None,
    )


@router.get("/chokepoints", response_model=ChokepointsResponse)
def list_chokepoints(
    db: DbSession,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    severity: str | None = Query(None),
) -> ChokepointsResponse:
    """List chokepoints with optional severity filter, paginated."""
    base_q = db.query(Chokepoint)

    if severity is not None:
        latest_sq = (
            db.query(
                ChokepointRiskScore.entity_id,
                func.max(ChokepointRiskScore.as_of).label("max_as_of"),
            )
            .group_by(ChokepointRiskScore.entity_id)
            .subquery()
        )
        latest_alias = (
            db.query(ChokepointRiskScore)
            .join(
                latest_sq,
                (ChokepointRiskScore.entity_id == latest_sq.c.entity_id)
                & (ChokepointRiskScore.as_of == latest_sq.c.max_as_of),
            )
            .subquery()
        )
        matching_ids: list[str] = [
            row[0]
            for row in db.query(latest_alias.c.entity_id).filter(
                latest_alias.c.severity == severity
            )
        ]
        from sqlalchemy import String as SaString
        base_q = base_q.filter(
            cast(Chokepoint.id, SaString).in_(matching_ids)
        )

    total: int = base_q.count()
    chokepoints = base_q.offset(offset).limit(limit).all()

    # Batch-fetch latest severity for the current page (2 queries instead of N+1)
    entity_ids = [_chokepoint_entity_id(cp) for cp in chokepoints]
    score_map = _bulk_latest_chokepoint_scores(db, entity_ids)

    items: list[ChokepointListItem] = []
    for cp in chokepoints:
        entity_id = _chokepoint_entity_id(cp)
        sev, _score = score_map.get(entity_id, (None, None))
        items.append(
            ChokepointListItem(id=cp.id, name=cp.name, severity=sev)
        )

    return ChokepointsResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/chokepoints/{chokepoint_id}/metrics", response_model=ChokepointMetricsResponse)
def get_chokepoint_metrics(
    chokepoint_id: int,
    db: DbSession,
    days: int = Query(_METRICS_DAYS, ge=7, le=365),
) -> ChokepointMetricsResponse:
    """Return per-metric timeseries for a chokepoint over the last N days."""
    cp = db.query(Chokepoint).filter(Chokepoint.id == chokepoint_id).first()
    if cp is None:
        raise HTTPException(status_code=404, detail=f"Chokepoint {chokepoint_id} not found")

    entity_id = _chokepoint_entity_id(cp)
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)

    rows = (
        db.query(PortWatchMetric.metric_name, PortWatchMetric.observed_at, PortWatchMetric.metric_value)
        .filter(
            PortWatchMetric.entity_type == "chokepoint",
            PortWatchMetric.entity_id == entity_id,
            PortWatchMetric.observed_at >= cutoff,
        )
        .order_by(PortWatchMetric.metric_name, PortWatchMetric.observed_at)
        .all()
    )

    metrics: dict[str, list[MetricPoint]] = {}
    for metric_name, observed_at, value in rows:
        if metric_name not in metrics:
            metrics[metric_name] = []
        ts = observed_at.isoformat() if hasattr(observed_at, "isoformat") else str(observed_at)
        metrics[metric_name].append(MetricPoint(time=ts, value=float(value)))

    return ChokepointMetricsResponse(entity_id=entity_id, metrics=metrics)


@router.get("/chokepoints/{chokepoint_id}", response_model=ChokepointDetail)
def get_chokepoint(chokepoint_id: int, db: DbSession) -> ChokepointDetail:
    """Return full detail for a single chokepoint."""
    cp = db.query(Chokepoint).filter(Chokepoint.id == chokepoint_id).first()
    if cp is None:
        raise HTTPException(status_code=404, detail=f"Chokepoint {chokepoint_id} not found")

    entity_id = _chokepoint_entity_id(cp)
    sev = _latest_chokepoint_severity(db, entity_id)
    coords = _geom_to_polygon_coords(cp.geom)
    centroid = _geom_centroid(cp.geom)
    lon, lat = (centroid[0], centroid[1]) if centroid else (None, None)

    score_row = (
        db.query(ChokepointRiskScore.score, ChokepointRiskScore.as_of)
        .filter(ChokepointRiskScore.entity_id == entity_id)
        .order_by(desc(ChokepointRiskScore.as_of))
        .first()
    )
    risk_score = float(score_row[0]) if score_row and score_row[0] is not None else None
    updated_at = score_row[1].isoformat() if score_row and score_row[1] else None

    snapshot = _latest_cp_snapshot(db, entity_id)

    return ChokepointDetail(
        id=cp.id,
        name=cp.name,
        severity=sev,
        coordinates=coords,
        lat=lat,
        lon=lon,
        risk_score=risk_score,
        risk_snapshot=snapshot,
        updated_at=updated_at,
    )


@router.get("/chokepoints/{chokepoint_id}/breakdown", response_model=ChokepointBreakdownResponse)
def get_chokepoint_breakdown(chokepoint_id: int, db: DbSession) -> ChokepointBreakdownResponse:
    """Return up to 50 daily per-category metric counts for a chokepoint."""
    cp = db.query(Chokepoint).filter(Chokepoint.id == chokepoint_id).first()
    if cp is None:
        raise HTTPException(status_code=404, detail=f"Chokepoint {chokepoint_id} not found")

    entity_id = _chokepoint_entity_id(cp)

    # Query PortWatchMetric where entity_type="chokepoint" and entity_id matches
    # Limit to the last _BREAKDOWN_DAYS days at the DB level to avoid a full-table scan
    cutoff = datetime.now(tz=UTC) - timedelta(days=_BREAKDOWN_DAYS)

    # Group by date (cast observed_at to date) and metric_name (category)
    rows = (
        db.query(
            cast(PortWatchMetric.observed_at, SaDate).label("obs_date"),
            PortWatchMetric.metric_name,
            func.count().label("cnt"),
        )
        .filter(
            PortWatchMetric.entity_type == "chokepoint",
            PortWatchMetric.entity_id == entity_id,
            PortWatchMetric.observed_at >= cutoff,
        )
        .group_by(
            cast(PortWatchMetric.observed_at, SaDate),
            PortWatchMetric.metric_name,
        )
        .order_by(desc(cast(PortWatchMetric.observed_at, SaDate)))
        .all()
    )

    # Aggregate by date — collect up to _BREAKDOWN_DAYS unique dates
    date_map: dict[Any, Any] = defaultdict(lambda: defaultdict(int))
    dates_seen: list[Any] = []

    for obs_date, metric_name, cnt in rows:
        if obs_date not in date_map:
            if len(dates_seen) >= _BREAKDOWN_DAYS:
                continue
            dates_seen.append(obs_date)
        date_map[obs_date][metric_name] += cnt

    days: list[ChokepointBreakdownDay] = []
    for d in sorted(dates_seen, reverse=True):
        cats = dict(date_map[d])
        days.append(
            ChokepointBreakdownDay(
                date=d,
                total=sum(cats.values()),
                categories=cats,
            )
        )

    return ChokepointBreakdownResponse(
        chokepoint_id=cp.id,
        name=cp.name,
        days=days,
    )
