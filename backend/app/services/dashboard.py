from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import fmean, stdev
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.models import (
    BunkerPrice,
    Chokepoint,
    ChokepointRiskScore,
    DisruptionPropagation,
    EntityRiskForecast,
    FreightIndex,
    Port,
    PortRiskScore,
    PortWatchMetric,
)
from app.schemas.dashboard import (
    AnomalyStats,
    DashboardResponse,
    DashboardStats,
    DisruptionItem,
    EntityInfo,
    EntitySummaryResponse,
)

logger = logging.getLogger(__name__)

_WINDOW_DAYS: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}
_FALLBACK_THROUGHPUT_METRIC = "vessels_in_port"

# PortWatch per-category port-call metrics → cargo-type label for the mix chart.
_PORT_CATEGORY_METRICS: dict[str, str] = {
    "portcalls_container": "container",
    "portcalls_dry_bulk": "dry_bulk",
    "portcalls_general_cargo": "general_cargo",
    "portcalls_roro": "roro",
    "portcalls_tanker": "tanker",
}
_CHOKE_CATEGORY_METRICS: dict[str, str] = {
    "transit_container": "container",
    "transit_dry_bulk": "dry_bulk",
    "transit_general_cargo": "general_cargo",
    "transit_roro": "roro",
    "transit_tanker": "tanker",
}


def _category_mix(
    session: Session, entity_type: str, entity_id: str, mapping: dict[str, str], since: datetime
) -> list[dict[str, Any]]:
    rows = (
        session.query(PortWatchMetric)
        .filter(
            PortWatchMetric.entity_type == entity_type,
            PortWatchMetric.entity_id == entity_id,
            PortWatchMetric.metric_name.in_(list(mapping)),
            PortWatchMetric.observed_at >= since,
        )
        .order_by(PortWatchMetric.observed_at)
        .all()
    )
    mix: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = r.observed_at.isoformat()
        bucket = mix.setdefault(key, {"time": key})
        bucket[mapping[r.metric_name]] = r.metric_value
    return list(mix.values())


def _metric_series(
    session: Session, entity_type: str, entity_id: str, metric: str, since: datetime
) -> list[dict[str, Any]]:
    rows = (
        session.query(PortWatchMetric)
        .filter(
            PortWatchMetric.entity_type == entity_type,
            PortWatchMetric.entity_id == entity_id,
            PortWatchMetric.metric_name == metric,
            PortWatchMetric.observed_at >= since,
        )
        .order_by(PortWatchMetric.observed_at)
        .all()
    )
    return [{"time": r.observed_at.isoformat(), "value": r.metric_value} for r in rows]


def _window_start(window: str) -> datetime:
    days = _WINDOW_DAYS[window]
    return datetime.now(tz=UTC) - timedelta(days=days)


# Throughput metric tested for anomalies / summarized per entity type.
_THROUGHPUT_METRIC: dict[str, str] = {"port": "port_calls", "chokepoint": "transit_calls"}
_MIN_BASELINE = 8


def _norm_cdf(x: float) -> float:
    """Standard-normal CDF via erf (no SciPy dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _anomaly_stats(series: list[dict[str, Any]], metric: str | None = None) -> AnomalyStats:
    """Z-score hypothesis test of the latest point against its trailing baseline.

    The latest value is excluded from the baseline so it is tested against history.
    Returns null fields when there is too little history or zero variance.
    """
    if len(series) < _MIN_BASELINE + 1:
        return AnomalyStats(metric=metric, baseline_n=max(len(series) - 1, 0))

    values = [float(p["value"]) for p in series]
    latest = values[-1]
    baseline = values[:-1]
    mean = fmean(baseline)
    std = stdev(baseline)  # sample std; len(baseline) >= 8

    if std <= 0:
        return AnomalyStats(
            metric=metric, latest=round(latest, 2), mean=round(mean, 2),
            std=0.0, baseline_n=len(baseline), anomaly_level="low",
        )

    z = (latest - mean) / std
    p = 2.0 * (1.0 - _norm_cdf(abs(z)))
    az = abs(z)
    level = "high" if az >= 2.5 else "elevated" if az >= 1.5 else "low"

    return AnomalyStats(
        metric=metric,
        latest=round(latest, 2),
        mean=round(mean, 2),
        std=round(std, 4),
        z_score=round(z, 3),
        p_value=round(p, 4),
        anomaly_level=level,
        baseline_n=len(baseline),
    )


def build_entity_summary(
    session: Session, entity_type: str, entity_id: str, window: str
) -> EntitySummaryResponse | None:
    """Per-entity AI summary grounded in throughput trend + z-score anomaly stats."""
    if entity_type == "port":
        dash = build_port_dashboard(session, entity_id, window)
    else:
        dash = build_chokepoint_dashboard(session, entity_id, window)
    if dash is None:
        return None

    stats = dash.stats.anomaly or AnomalyStats(metric=_THROUGHPUT_METRIC.get(entity_type))
    narrative = _summary_narrative(dash.entity.name, window, stats, dash.stats.risk_latest)
    return EntitySummaryResponse(
        entity=dash.entity, window=window, narrative=narrative, stats=stats
    )


def _summary_narrative(
    name: str, window: str, stats: AnomalyStats, risk_latest: float | None
) -> str:
    """LLM summary of one entity's throughput/anomaly picture, with a fallback."""

    def _fallback() -> str:
        if stats.z_score is None:
            return (
                f"Not enough recent throughput history for {name} to run a "
                f"probability estimate over the last {window}."
            )
        direction = "above" if stats.z_score >= 0 else "below"
        parts = [
            f"Over the last {window}, {name}'s latest throughput ({stats.metric}) "
            f"sits {abs(stats.z_score):.2f}σ {direction} its trailing mean "
            f"(z={stats.z_score:.2f}, p={stats.p_value:.3f}; {stats.anomaly_level} anomaly likelihood)."
        ]
        if risk_latest is not None:
            parts.append(f"Latest composite risk score is {risk_latest:.2f}.")
        return " ".join(parts)

    try:
        from app.llm.client import LLMResponse, chat_completion

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a maritime supply-chain analyst. In 2-3 sentences, "
                    "summarize one entity's throughput situation from the given "
                    "z-score statistics. Be factual and concise; do not invent numbers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Entity: {name}. Window: {window}. Metric: {stats.metric}. "
                    f"latest={stats.latest}, mean={stats.mean}, std={stats.std}, "
                    f"z_score={stats.z_score}, p_value={stats.p_value}, "
                    f"anomaly_level={stats.anomaly_level}, risk_latest={risk_latest}."
                ),
            },
        ]
        resp = chat_completion(messages)
        if isinstance(resp, LLMResponse) and resp.content.strip():
            return resp.content.strip()
    except Exception:
        logger.info("Entity summary LLM unavailable; using data-driven fallback.")
    return _fallback()


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
    throughput_metric = "port_calls"

    # --- Vessel mix: PortWatch per-category port calls (real data) ---
    cat_rows = (
        session.query(PortWatchMetric)
        .filter(
            PortWatchMetric.entity_type == "port",
            PortWatchMetric.entity_id == port.portid,
            PortWatchMetric.metric_name.in_(list(_PORT_CATEGORY_METRICS)),
            PortWatchMetric.observed_at >= since,
        )
        .order_by(PortWatchMetric.observed_at)
        .all()
    )
    _mix: dict[str, dict[str, Any]] = {}
    for r in cat_rows:
        key = r.observed_at.isoformat()
        bucket = _mix.setdefault(key, {"time": key})
        bucket[_PORT_CATEGORY_METRICS[r.metric_name]] = r.metric_value
    vessel_mix = list(_mix.values())
    # PortWatch provides no dwell-time data; the card is removed in the UI.
    dwell_hours: list[dict[str, Any]] = []

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
            PortRiskScore.entity_id == port.portid,
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

    # --- Forecast (throughput = port_calls) ---
    forecast_row = (
        session.query(EntityRiskForecast)
        .filter(
            EntityRiskForecast.entity_type == "port",
            EntityRiskForecast.entity_id == port.portid,
            EntityRiskForecast.forecast_key.like("%:port_calls:%"),
        )
        .order_by(desc(EntityRiskForecast.created_at))
        .first()
    )
    forecast: list[dict[str, Any]] = []
    if forecast_row and forecast_row.predictions:
        forecast = [
            {
                "time": pred["date"],
                "value": pred.get("value", pred.get("predicted_score", 0)),
                "lo": pred.get("low", pred.get("lower_bound", 0)),
                "hi": pred.get("high", pred.get("upper_bound", 0)),
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

    # No dwell data from PortWatch; "vessels" proxied by latest total port calls.
    dwell_latest = None
    vessel_count_latest = int(float(throughput[-1]["value"])) if throughput else None  # type: ignore[arg-type]

    # --- Disruptions (port is downstream target) ---
    disruption_rows = (
        session.query(DisruptionPropagation)
        .filter(DisruptionPropagation.target_entity_id == port.portid)
        .order_by(desc(DisruptionPropagation.started_at))
        .all()
    )
    disruptions = [_serialize_disruption(d) for d in disruption_rows]

    return DashboardResponse(
        entity=EntityInfo(type="port", id=port.portid, name=port.name),
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
            anomaly=_anomaly_stats(throughput, throughput_metric),
        ),
        disruptions=disruptions,
    )


def build_chokepoint_dashboard(
    session: Session, cp_id: str, window: str
) -> DashboardResponse | None:
    """Build dashboard payload for a chokepoint. Returns None if not found."""
    # Accept either the chokepointid (e.g. "chokepoint6") or the name slug.
    cp = session.query(Chokepoint).filter(Chokepoint.chokepointid == cp_id).first()
    if cp is None:
        all_cps = session.query(Chokepoint).all()
        cp = next(
            (c for c in all_cps if c.name.lower().replace(" ", "_") == cp_id), None
        )
    if cp is None:
        return None

    # Metrics / risk / forecast are keyed by the name slug (collector convention).
    slug = cp.name.lower().replace(" ", "_")
    since = _window_start(window)

    # --- Transit volume + cargo-type mix (real PortWatch data) ---
    transit_volume = _metric_series(session, "chokepoint", slug, "transit_calls", since)
    vessel_mix = _category_mix(session, "chokepoint", slug, _CHOKE_CATEGORY_METRICS, since)

    # --- Risk trend (ChokepointRiskScore) ---
    risk_rows = (
        session.query(ChokepointRiskScore)
        .filter(
            ChokepointRiskScore.entity_id == slug,
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
            EntityRiskForecast.entity_id == slug,
            EntityRiskForecast.forecast_key.like("%:transit_calls:%"),
        )
        .order_by(desc(EntityRiskForecast.created_at))
        .first()
    )
    forecast: list[dict[str, Any]] = []
    if forecast_row and forecast_row.predictions:
        forecast = [
            {
                "time": pred["date"],
                "value": pred.get("value", pred.get("predicted_score", 0)),
                "lo": pred.get("low", pred.get("lower_bound", 0)),
                "hi": pred.get("high", pred.get("upper_bound", 0)),
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

    vessel_count_latest = (
        int(float(transit_volume[-1]["value"])) if transit_volume else None
    )

    # --- Disruptions (chokepoint is the source) ---
    disruption_rows = (
        session.query(DisruptionPropagation)
        .filter(DisruptionPropagation.source_entity_id == slug)
        .order_by(desc(DisruptionPropagation.started_at))
        .all()
    )
    disruptions = [_serialize_disruption(d) for d in disruption_rows]

    return DashboardResponse(
        entity=EntityInfo(type="chokepoint", id=cp.chokepointid, name=cp.name),
        window=window,
        charts={
            "transit_volume": transit_volume,
            "vessel_mix": vessel_mix,
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
            anomaly=_anomaly_stats(transit_volume, "transit_calls"),
        ),
        disruptions=disruptions,
    )
