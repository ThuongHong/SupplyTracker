from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select

from app.api.deps import DbSession
from app.db.models import Port, PortRiskScore
from app.schemas.ports import PortDetail, PortListItem, PortsResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ports"])


def _latest_severity(db: Any, entity_id: str) -> str | None:
    """Return the most recent severity label for a port entity_id."""
    row = (
        db.query(PortRiskScore.severity)
        .filter(PortRiskScore.entity_id == entity_id)
        .order_by(desc(PortRiskScore.as_of))
        .first()
    )
    return row[0] if row else None


def _bulk_latest_scores(db: Any, entity_ids: list[str]) -> dict[str, tuple[str | None, float | None]]:
    """Return {entity_id: (severity, score)} for the latest score of each given entity_id.

    Replaces N individual queries with 2 queries (max-time subquery + join).
    """
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
    """Derive the entity_id used in risk scores for a port."""
    return port.locode or str(port.id)


def _geom_to_coords(geom: Any) -> list[float] | None:
    """Convert a GeoAlchemy2 WKBElement to [lon, lat]."""
    if geom is None:
        return None
    try:
        from geoalchemy2.shape import to_shape  # type: ignore[import-untyped]
        shape = to_shape(geom)
        return [shape.x, shape.y]
    except Exception:  # noqa: BLE001
        return None


@router.get("/ports", response_model=PortsResponse)
def list_ports(
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    severity: str | None = Query(None),
) -> PortsResponse:
    """List ports with optional severity filter, paginated."""
    # Base query: join latest risk score severity if filtering by severity
    base_q = db.query(Port)

    if severity is not None:
        # Sub-select: latest score per entity_id
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
        # We need to filter ports whose entity_id maps to severity
        # Collect matching entity_ids first
        matching_ids: list[str] = [
            row[0]
            for row in db.query(latest_score_alias.c.entity_id).filter(
                latest_score_alias.c.severity == severity
            )
        ]
        # Map entity_ids back to port ids: entity_id = locode or str(id)
        # Filter by locode match OR numeric id match
        from sqlalchemy import cast, or_
        from sqlalchemy import String as SaString
        base_q = base_q.filter(
            or_(
                Port.locode.in_(matching_ids),
                cast(Port.id, SaString).in_(matching_ids),
            )
        )

    total: int = base_q.count()
    ports = base_q.offset(offset).limit(limit).all()

    # Batch-fetch latest severity for the current page (2 queries instead of N+1)
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


@router.get("/ports/{port_id}", response_model=PortDetail)
def get_port(port_id: int, db: DbSession) -> PortDetail:
    """Return full detail for a single port."""
    port = db.query(Port).filter(Port.id == port_id).first()
    if port is None:
        raise HTTPException(status_code=404, detail=f"Port {port_id} not found")

    entity_id = _port_entity_id(port)
    sev = _latest_severity(db, entity_id)
    coords = _geom_to_coords(port.geom)

    return PortDetail(
        id=port.id,
        locode=port.locode,
        name=port.name,
        country=port.country,
        region=port.region,
        radius_km=port.radius_km,
        twenty_ft_eq_units_year=port.twenty_ft_eq_units_year,
        coordinates=coords,
        severity=sev,
    )
