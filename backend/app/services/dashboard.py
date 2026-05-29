from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.models import (
    BunkerPrice,
    Chokepoint,
    ChokepointRiskScore,
    ChokepointStatus,
    DisruptionPropagation,
    EntityRiskForecast,
    FreightIndex,
    Port,
    PortCongestion,
    PortRiskScore,
    PortWatchMetric,
)
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardStats,
    DisruptionItem,
    EntityInfo,
)

_WINDOW_DAYS: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}
_FALLBACK_THROUGHPUT_METRIC = "vessels_in_port"


def _window_start(window: str) -> datetime:
    days = _WINDOW_DAYS[window]
    return datetime.now(tz=UTC) - timedelta(days=days)


def _get_default_throughput_metric(session: Session) -> str:
    """Return the most-populated metric_name in port_watch_metric, or fallback."""
    row = (
        session.query(PortWatchMetric.metric_name, func.count().label("cnt"))
        .group_by(PortWatchMetric.metric_name)
        .order_by(desc("cnt"))
        .first()
    )
    return row.metric_name if row else _FALLBACK_THROUGHPUT_METRIC


def _build_indices_chart(session: Session, since: datetime) -> list[dict[str, Any]]:
    """Return pivoted freight-index series with fbx and wci keys."""
    rows = (
        session.query(FreightIndex)
        .filter(FreightIndex.time >= since)
        .order_by(FreightIndex.time)
        .all()
    )
    by_date: dict[str, dict[str, Any]] = defaultdict(dict)
    for r in rows:
        date_str = r.time.date().isoformat()
        by_date[date_str]["time"] = date_str
        name_lower = r.index_name.lower()
        if "fbx" in name_lower:
            by_date[date_str]["fbx"] = r.value
        elif "wci" in name_lower:
            by_date[date_str]["wci"] = r.value
    return sorted(by_date.values(), key=lambda x: x["time"])


def _build_bunker_chart(session: Session, since: datetime) -> list[dict[str, Any]]:
    """Return daily average VLSFO bunker price across all ports."""
    rows = (
        session.query(
            func.date(BunkerPrice.time).label("d"),
            func.avg(BunkerPrice.price_usd_per_ton).label("avg_price"),
        )
        .filter(BunkerPrice.time >= since, BunkerPrice.fuel_type == "VLSFO")
        .group_by(func.date(BunkerPrice.time))
        .order_by(func.date(BunkerPrice.time))
        .all()
    )
    return [{"time": str(r.d), "value": r.avg_price} for r in rows]


def _fbx_pct_7d(session: Session) -> float | None:
    """Compute percentage change in FBX over the last 7 days."""
    since_7d = datetime.now(tz=UTC) - timedelta(days=7)
    latest_row = (
        session.query(FreightIndex)
        .filter(FreightIndex.index_name.ilike("%fbx%"))
        .order_by(desc(FreightIndex.time))
        .first()
    )
    oldest_row = (
        session.query(FreightIndex)
        .filter(FreightIndex.index_name.ilike("%fbx%"), FreightIndex.time >= since_7d)
        .order_by(FreightIndex.time)
        .first()
    )
    if latest_row and oldest_row and oldest_row.value:
        return (latest_row.value - oldest_row.value) / oldest_row.value * 100
    return None


def _serialize_disruption(d: DisruptionPropagation) -> DisruptionItem:
    return DisruptionItem(
        source_entity_id=d.source_entity_id,
        source_entity_name=d.source_entity_name,
        target_entity_id=d.target_entity_id,
        target_entity_name=d.target_entity_name,
        severity=d.severity,
        confidence=d.confidence,
        explanation=d.explanation,
        started_at=d.started_at.isoformat(),
        status=d.status,
    )


def build_port_dashboard(
    session: Session, port_id: str, window: str
) -> DashboardResponse | None:
    """Build dashboard payload for a port. Returns None if port not found."""
    port = session.query(Port).filter(Port.portid == port_id).first()
    if port is None:
        port = session.query(Port).filter(Port.locode == port_id).first()
    if port is None:
        port = session.query(Port).filter(Port.name == port_id).first()
    if port is None:
        return None

    since = _window_start(window)
    throughput_metric = _get_default_throughput_metric(session)

    # --- Congestion charts ---
    congestion_rows = (
        session.query(PortCongestion)
        .filter(PortCongestion.port_id == port.id, PortCongestion.time >= since)
        .order_by(PortCongestion.time)
        .all()
    )
    vessel_mix = [
        {
            "time": r.time.isoformat(),
            "anchored": r.anchored_count,
            "moored": r.moored_count,
            "underway": r.underway_count,
        }
        for r in congestion_rows
    ]
    dwell_hours = [
        {"time": r.time.isoformat(), "value": r.avg_dwell_hours}
        for r in congestion_rows
        if r.avg_dwell_hours is not None
    ]

    # --- Throughput (PortWatchMetric) ---
    throughput_rows = (
        session.query(PortWatchMetric)
        .filter(
            PortWatchMetric.entity_type == "port",
            PortWatchMetric.entity_id == port.portid,
            PortWatchMetric.metric_name == throughput_metric,
            PortWatchMetric.observed_at >= since,
        )
        .order_by(PortWatchMetric.observed_at)
        .all()
    )
    throughput = [
        {"time": r.observed_at.isoformat(), "value": r.metric_value}
        for r in throughput_rows
    ]

    # --- Risk trend ---
    risk_rows = (
        session.query(PortRiskScore)
        .filter(
            PortRiskScore.entity_id == (port.locode or port.name),
            PortRiskScore.time >= since,
        )
        .order_by(PortRiskScore.time)
        .all()
    )
    risk_trend = [
        {"time": r.time.isoformat(), "value": r.score}
        for r in risk_rows
        if r.score is not None
    ]

    # --- Forecast ---
    forecast_row = (
        session.query(EntityRiskForecast)
        .filter(
            EntityRiskForecast.entity_type == "port",
            EntityRiskForecast.entity_id == (port.locode or port.name),
        )
        .order_by(desc(EntityRiskForecast.created_at))
        .first()
    )
    forecast: list[dict[str, Any]] = []
    if forecast_row and forecast_row.predictions:
        forecast = [
            {
                "time": pred["date"],
                "value": pred["predicted_score"],
                "lo": pred.get("lower_bound", 0),
                "hi": pred.get("upper_bound", 0),
            }
            for pred in forecast_row.predictions
        ]

    # --- Indices and bunker ---
    indices = _build_indices_chart(session, since)
    bunker = _build_bunker_chart(session, since)

    # --- Stats ---
    risk_latest: float | None = risk_rows[-1].score if risk_rows else None
    scores = [r.score for r in risk_rows if r.score is not None]
    risk_30d_mean = sum(scores) / len(scores) if scores else None
    risk_30d_max = max(scores) if scores else None

    latest_cong = congestion_rows[-1] if congestion_rows else None
    dwell_latest = latest_cong.avg_dwell_hours if latest_cong else None
    vessel_count_latest = latest_cong.total_in_area if latest_cong else None

    # --- Disruptions (port is downstream target) ---
    disruption_rows = (
        session.query(DisruptionPropagation)
        .filter(DisruptionPropagation.target_entity_id == (port.locode or port.name))
        .order_by(desc(DisruptionPropagation.started_at))
        .all()
    )
    disruptions = [_serialize_disruption(d) for d in disruption_rows]

    return DashboardResponse(
        entity=EntityInfo(type="port", id=port.locode or port.name, name=port.name),
        window=window,
        charts={
            "vessel_mix": vessel_mix,
            "dwell_hours": dwell_hours,
            "throughput": throughput,
            "risk_trend": risk_trend,
            "forecast": forecast,
            "indices": indices,
            "bunker": bunker,
        },
        stats=DashboardStats(
            risk_latest=risk_latest,
            risk_30d_mean=risk_30d_mean,
            risk_30d_max=risk_30d_max,
            dwell_latest=dwell_latest,
            vessel_count_latest=vessel_count_latest,
            fbx_pct_7d=_fbx_pct_7d(session),
        ),
        disruptions=disruptions,
    )


def build_chokepoint_dashboard(
    session: Session, cp_id: str, window: str
) -> DashboardResponse | None:
    """Build dashboard payload for a chokepoint. Returns None if not found."""
    all_cps = session.query(Chokepoint).all()
    cp = next(
        (c for c in all_cps if c.name.lower().replace(" ", "_") == cp_id),
        None,
    )
    if cp is None:
        return None

    since = _window_start(window)

    # --- ChokepointStatus charts ---
    status_rows = (
        session.query(ChokepointStatus)
        .filter(
            ChokepointStatus.chokepoint_id == cp.id,
            ChokepointStatus.time >= since,
        )
        .order_by(ChokepointStatus.time)
        .all()
    )
    vessel_count_chart = [
        {"time": r.time.isoformat(), "value": r.vessel_count}
        for r in status_rows
    ]
    median_speed_chart = [
        {"time": r.time.isoformat(), "value": r.median_speed}
        for r in status_rows
        if r.median_speed is not None
    ]

    # --- Risk trend (ChokepointRiskScore) ---
    risk_rows = (
        session.query(ChokepointRiskScore)
        .filter(
            ChokepointRiskScore.entity_id == cp_id,
            ChokepointRiskScore.time >= since,
        )
        .order_by(ChokepointRiskScore.time)
        .all()
    )
    risk_trend = [
        {"time": r.time.isoformat(), "value": r.score}
        for r in risk_rows
        if r.score is not None
    ]

    # --- Forecast ---
    forecast_row = (
        session.query(EntityRiskForecast)
        .filter(
            EntityRiskForecast.entity_type == "chokepoint",
            EntityRiskForecast.entity_id == cp_id,
        )
        .order_by(desc(EntityRiskForecast.created_at))
        .first()
    )
    forecast: list[dict[str, Any]] = []
    if forecast_row and forecast_row.predictions:
        forecast = [
            {
                "time": pred["date"],
                "value": pred["predicted_score"],
                "lo": pred.get("lower_bound", 0),
                "hi": pred.get("upper_bound", 0),
            }
            for pred in forecast_row.predictions
        ]

    # --- Indices and bunker ---
    indices = _build_indices_chart(session, since)
    bunker = _build_bunker_chart(session, since)

    # --- Stats ---
    risk_latest: float | None = risk_rows[-1].score if risk_rows else None
    scores = [r.score for r in risk_rows if r.score is not None]
    risk_30d_mean = sum(scores) / len(scores) if scores else None
    risk_30d_max = max(scores) if scores else None

    latest_status = status_rows[-1] if status_rows else None
    vessel_count_latest = latest_status.vessel_count if latest_status else None

    # --- Disruptions (chokepoint is the source) ---
    disruption_rows = (
        session.query(DisruptionPropagation)
        .filter(DisruptionPropagation.source_entity_id == cp_id)
        .order_by(desc(DisruptionPropagation.started_at))
        .all()
    )
    disruptions = [_serialize_disruption(d) for d in disruption_rows]

    return DashboardResponse(
        entity=EntityInfo(type="chokepoint", id=cp_id, name=cp.name),
        window=window,
        charts={
            "vessel_count": vessel_count_chart,
            "median_speed": median_speed_chart,
            "risk_trend": risk_trend,
            "forecast": forecast,
            "indices": indices,
            "bunker": bunker,
        },
        stats=DashboardStats(
            risk_latest=risk_latest,
            risk_30d_mean=risk_30d_mean,
            risk_30d_max=risk_30d_max,
            vessel_count_latest=vessel_count_latest,
            fbx_pct_7d=_fbx_pct_7d(session),
        ),
        disruptions=disruptions,
    )
