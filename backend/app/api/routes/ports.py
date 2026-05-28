from __future__ import annotations

import logging
import struct
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select

from app.api.deps import DbSession
from app.db.models import Port, PortRiskScore, PortWatchMetric, RiskFeatureSnapshot
from app.schemas.ports import (
    MetricPoint,
    PortDetail,
    PortListItem,
    PortMetricsResponse,
    PortsResponse,
    RiskSnapshotEmbed,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ports"])

_METRICS_DAYS = 90


def _latest_severity(db: Any, entity_id: str) -> str | None:
    row = (
        db.query(PortRiskScore.severity)
        .filter(PortRiskScore.entity_id == entity_id)
        .order_by(desc(PortRiskScore.as_of))
        .first()
    )
    return row[0] if row else None


def _bulk_latest_scores(db: Any, entity_ids: list[str]) -> dict[str, tuple[str | None, float | None]]:
    if not entity_ids:
        return {}

    max_time_sq = (
        select(
            PortRiskScore.entity_id,
            func.max(PortRiskScore.as_of).label("max_as_of"),
        )
        .where(PortRiskScore.entity_id.in_(entity_ids))
        .group_by(PortRiskScore.entity_id)
        .subquery()
    )
    rows = (
        db.query(PortRiskScore)
        .join(
            max_time_sq,
            (PortRiskScore.entity_id == max_time_sq.c.entity_id)
            & (PortRiskScore.as_of == max_time_sq.c.max_as_of),
        )
        .all()
    )
    return {r.entity_id: (r.severity, r.score) for r in rows}


def _port_entity_id(port: Port) -> str:
    return port.locode or str(port.id)


def _geom_to_coords(geom: Any) -> tuple[float, float] | None:
    """Return (lon, lat) from a WKBElement. Tries shapely first, falls back to EWKB decode."""
    if geom is None:
        return None
    try:
        from geoalchemy2.shape import to_shape
        shape = to_shape(geom)
        return shape.x, shape.y
    except Exception:  # noqa: BLE001
        pass
    try:
        raw = geom.desc
        if isinstance(raw, str):
            raw = bytes.fromhex(raw)
        bo = "<" if raw[0] == 1 else ">"
        type_code = struct.unpack_from(bo + "I", raw, 1)[0]
        has_srid = bool(type_code & 0x20000000)
        offset = 5 + (4 if has_srid else 0)
        lon, lat = struct.unpack_from(bo + "dd", raw, offset)
        return lon, lat
    except Exception:  # noqa: BLE001
        return None


def _latest_snapshot(db: Any, entity_id: str) -> RiskSnapshotEmbed | None:
    snap = (
        db.query(RiskFeatureSnapshot)
        .filter(
            RiskFeatureSnapshot.entity_type == "port",
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


@router.get("/ports", response_model=PortsResponse)
def list_ports(
    db: DbSession,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    severity: str | None = Query(None),
) -> PortsResponse:
    """List ports with optional severity filter, paginated."""
    base_q = db.query(Port)

    if severity is not None:
        latest_score_sq = (
            db.query(
                PortRiskScore.entity_id,
                func.max(PortRiskScore.as_of).label("max_as_of"),
            )
            .group_by(PortRiskScore.entity_id)
            .subquery()
        )
        latest_score_alias = (
            db.query(PortRiskScore)
            .join(
                latest_score_sq,
                (PortRiskScore.entity_id == latest_score_sq.c.entity_id)
                & (PortRiskScore.as_of == latest_score_sq.c.max_as_of),
            )
            .subquery()
        )
        matching_ids: list[str] = [
            row[0]
            for row in db.query(latest_score_alias.c.entity_id).filter(
                latest_score_alias.c.severity == severity
            )
        ]
        from sqlalchemy import String as SaString
        from sqlalchemy import cast, or_
        base_q = base_q.filter(
            or_(
                Port.locode.in_(matching_ids),
                cast(Port.id, SaString).in_(matching_ids),
            )
        )

    total: int = base_q.count()
    ports = base_q.offset(offset).limit(limit).all()

    entity_ids = [_port_entity_id(p) for p in ports]
    score_map = _bulk_latest_scores(db, entity_ids)

    items: list[PortListItem] = []
    for p in ports:
        entity_id = _port_entity_id(p)
        sev, _score = score_map.get(entity_id, (None, None))
        items.append(
            PortListItem(
                id=p.id,
                locode=p.locode,
                name=p.name,
                country=p.country,
                region=p.region,
                severity=sev,
            )
        )

    return PortsResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/ports/{port_id}/metrics", response_model=PortMetricsResponse)
def get_port_metrics(
    port_id: int,
    db: DbSession,
    days: int = Query(_METRICS_DAYS, ge=7, le=365),
) -> PortMetricsResponse:
    """Return per-metric timeseries for a port over the last N days."""
    port = db.query(Port).filter(Port.id == port_id).first()
    if port is None:
        raise HTTPException(status_code=404, detail=f"Port {port_id} not found")

    entity_id = _port_entity_id(port)
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)

    rows = (
        db.query(PortWatchMetric.metric_name, PortWatchMetric.observed_at, PortWatchMetric.metric_value)
        .filter(
            PortWatchMetric.entity_type == "port",
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

    return PortMetricsResponse(entity_id=entity_id, metrics=metrics)


@router.get("/ports/{port_id}", response_model=PortDetail)
def get_port(port_id: int, db: DbSession) -> PortDetail:
    """Return full detail for a single port."""
    port = db.query(Port).filter(Port.id == port_id).first()
    if port is None:
        raise HTTPException(status_code=404, detail=f"Port {port_id} not found")

    entity_id = _port_entity_id(port)
    sev = _latest_severity(db, entity_id)
    coords = _geom_to_coords(port.geom)
    lon, lat = (coords[0], coords[1]) if coords else (None, None)

    score_row = (
        db.query(PortRiskScore.score, PortRiskScore.as_of)
        .filter(PortRiskScore.entity_id == entity_id)
        .order_by(desc(PortRiskScore.as_of))
        .first()
    )
    risk_score = float(score_row[0]) if score_row and score_row[0] is not None else None
    updated_at = score_row[1].isoformat() if score_row and score_row[1] else None

    snapshot = _latest_snapshot(db, entity_id)

    return PortDetail(
        id=port.id,
        locode=port.locode,
        unlocode=port.locode,
        name=port.name,
        country=port.country,
        region=port.region,
        radius_km=port.radius_km,
        twenty_ft_eq_units_year=port.twenty_ft_eq_units_year,
        coordinates=[lon, lat] if lon is not None else None,
        lat=lat,
        lon=lon,
        severity=sev,
        risk_score=risk_score,
        risk_snapshot=snapshot,
        updated_at=updated_at,
    )
