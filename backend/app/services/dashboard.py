from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import fmean, stdev
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.analysis.macro_correlation import macro_sensitivity
from app.analysis.scoring import is_adverse_deviation
from app.db.models import (
    BunkerPrice,
    Chokepoint,
    DisruptionPropagation,
    EntityRiskForecast,
    EntitySummaryCache,
    FreightIndex,
    Port,
    PortWatchMetric,
    RiskFeatureSnapshot,
)
from app.schemas.dashboard import (
    AnomalyStats,
    DashboardResponse,
    DashboardStats,
    DisruptionItem,
    EntityInfo,
    EntitySummaryResponse,
    MacroCorrelation,
)

logger = logging.getLogger(__name__)

_WINDOW_DAYS: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}
_FALLBACK_THROUGHPUT_METRIC = "vessels_in_port"
_FRED_FREIGHT_PROXY_KEYS: dict[str, tuple[str, int]] = {
    "FRGEXPUSM649NCIS": ("fbx", 10),  # Cass Freight Index: expenditures
    "FRGSHPUSM649NCIS": ("fbx", 20),  # Cass Freight Index: shipments fallback
    "PCU483111483111": ("wci", 10),  # PPI: deep sea freight transportation
}
_FREIGHT_INDEX_EXTRA_LOOKBACK_DAYS = 90

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
    session: Session, entity_type: str, entity_id: str, window: str, force: bool = False
) -> EntitySummaryResponse | None:
    """Per-entity AI summary grounded in throughput trend + z-score anomaly stats.

    Stats/metrics are always recomputed (cheap). The LLM-written sections are
    cached per entity+window and only regenerated when ``force`` is set (sync)
    or no cache exists yet — so normal page loads don't burn LLM calls.
    """
    if entity_type == "port":
        dash = build_port_dashboard(session, entity_id, window)
    else:
        dash = build_chokepoint_dashboard(session, entity_id, window)
    if dash is None:
        return None

    anomalies = _entity_anomalies(_summary_series(session, dash, _window_start(window)))
    # Headline = most anomalous metric (max |z|), not a hardcoded throughput metric.
    stats = (
        anomalies[0][1]
        if anomalies
        else AnomalyStats(metric=_THROUGHPUT_METRIC.get(entity_type))
    )

    cached = (
        session.query(EntitySummaryCache)
        .filter(
            EntitySummaryCache.entity_type == entity_type,
            EntitySummaryCache.entity_id == dash.entity.id,
            EntitySummaryCache.window == window,
        )
        .first()
    )
    if cached is not None and not force:
        sections = {
            "what_happened": cached.what_happened,
            "so_what": cached.so_what,
            "to_do": cached.to_do,
        }
    else:
        sections = _summary_sections(_summary_context(dash, anomalies))
        _upsert_summary_cache(session, entity_type, dash.entity.id, window, sections)

    return EntitySummaryResponse(
        entity=dash.entity,
        window=window,
        narrative=" ".join(
            [sections["what_happened"], sections["so_what"], sections["to_do"]]
        ),
        what_happened=sections["what_happened"],
        so_what=sections["so_what"],
        to_do=sections["to_do"],
        stats=stats,
        metrics=[a[1] for a in anomalies],
    )


def _upsert_summary_cache(
    session: Session,
    entity_type: str,
    entity_id: str,
    window: str,
    sections: dict[str, str],
) -> None:
    """Store (or replace) the generated summary text for this entity+window."""
    stmt = (
        pg_insert(EntitySummaryCache)
        .values(
            entity_type=entity_type,
            entity_id=entity_id,
            window=window,
            what_happened=sections["what_happened"],
            so_what=sections["so_what"],
            to_do=sections["to_do"],
        )
        .on_conflict_do_update(
            index_elements=["entity_type", "entity_id", "window"],
            set_={
                "what_happened": sections["what_happened"],
                "so_what": sections["so_what"],
                "to_do": sections["to_do"],
                "generated_at": func.now(),
            },
        )
    )
    session.execute(stmt)
    session.commit()


# Metrics scanned for the per-entity summary (cheap z-score, no LLM cost).
_SUMMARY_METRICS: dict[str, tuple[str, ...]] = {
    "port": ("port_calls", "import_volume", "export_volume"),
    "chokepoint": ("transit_calls",),
}


def _summary_series(
    session: Session, dash: DashboardResponse, since: datetime
) -> dict[str, list[dict[str, Any]]]:
    """Per-metric time series for every metric we summarize for this entity."""
    entity_type = dash.entity.type
    # Port metrics are keyed by portid (== entity.id); chokepoint metrics by slug.
    if entity_type == "chokepoint":
        entity_key = dash.entity.name.lower().replace(" ", "_")
    else:
        entity_key = dash.entity.id
    metrics = _SUMMARY_METRICS.get(entity_type, ())
    return {
        m: _metric_series(session, entity_type, entity_key, m, since) for m in metrics
    }


def _entity_anomalies(
    series_by_metric: dict[str, list[dict[str, Any]]],
) -> list[tuple[str, AnomalyStats, float | None]]:
    """Z-score anomaly + window pct-change per metric, ranked by |z| descending."""
    out: list[tuple[str, AnomalyStats, float | None]] = []
    for metric, series in series_by_metric.items():
        out.append((metric, _anomaly_stats(series, metric), _pct_change(series)))
    out.sort(
        key=lambda t: abs(t[1].z_score) if t[1].z_score is not None else -1.0,
        reverse=True,
    )
    return out


def _summary_context(
    dash: DashboardResponse,
    anomalies: list[tuple[str, AnomalyStats, float | None]],
) -> dict[str, Any]:
    """Assemble the full data picture fed to the entity-summary LLM + fallback.

    Headline stats come from the most anomalous metric (anomalies[0]); other
    notable metrics are condensed to terse one-liners to keep LLM tokens low.
    """
    if anomalies:
        metric, stats, pct = anomalies[0]
    else:
        metric, stats, pct = None, AnomalyStats(), None

    # Favorability of the headline deviation: a surge in a higher_is_better metric
    # (e.g. throughput up) is favorable, not a disruption.
    favorability: str | None = None
    if metric and stats.z_score is not None:
        favorability = (
            "adverse" if is_adverse_deviation(metric, stats.z_score) else "favorable"
        )

    # Terse digest of OTHER elevated/high metrics (cap 3) — cheap to tokenize.
    notable = [
        f"{m}: z={s.z_score:.2f} ({s.anomaly_level}, "
        f"{'adverse' if is_adverse_deviation(m, s.z_score) else 'favorable'})"
        for m, s, _ in anomalies[1:]
        if s.z_score is not None and s.anomaly_level in ("elevated", "high")
    ][:3]

    return {
        "name": dash.entity.name,
        "entity_type": dash.entity.type,
        "window": dash.window,
        "metric": metric,
        "latest": stats.latest,
        "mean": stats.mean,
        "std": stats.std,
        "z_score": stats.z_score,
        "p_value": stats.p_value,
        "anomaly_level": stats.anomaly_level,
        "favorability": favorability,
        "throughput_pct_change": pct,
        "metric_anomalies": notable,
        "risk_latest": dash.stats.risk_latest,
        "risk_30d_mean": dash.stats.risk_30d_mean,
        "risk_30d_max": dash.stats.risk_30d_max,
        "vessel_count_latest": dash.stats.vessel_count_latest,
        "macro_insights": [m.insight for m in dash.macro_sensitivity],
        "disruptions": [f"{d.severity}: {d.explanation}" for d in dash.disruptions],
    }


def _pct_change(series: list[dict[str, Any]]) -> float | None:
    if len(series) < 2:
        return None
    try:
        first = float(series[0]["value"])
        last = float(series[-1]["value"])
    except (KeyError, TypeError, ValueError):
        return None
    if not first:
        return None
    return round((last - first) / first * 100, 1)


def _summary_sections(ctx: dict[str, Any]) -> dict[str, str]:
    """Structured entity summary (what happened / so what / to do) with a fallback."""
    name = ctx["name"]
    window = ctx["window"]

    def _fallback() -> dict[str, str]:
        macro = ctx["macro_insights"][0] if ctx["macro_insights"] else None
        disruptions = ctx["disruptions"]
        if ctx["z_score"] is None:
            return {
                "what_happened": (
                    f"Not enough recent throughput history for {name} to run a "
                    f"probability estimate over the last {window}."
                ),
                "so_what": (
                    "Without a baseline we cannot judge whether activity is normal "
                    "or anomalous."
                ),
                "to_do": (
                    "Sync more history for this entity, then re-check the anomaly view."
                ),
            }
        z = ctx["z_score"]
        direction = "above" if z >= 0 else "below"
        pct = ctx["throughput_pct_change"]
        trend_clause = (
            f" Throughput is {'up' if pct >= 0 else 'down'} {abs(pct):.1f}% over the window."
            if pct is not None
            else ""
        )
        risk_clause = (
            f" Latest composite risk score is {ctx['risk_latest']:.2f}."
            if ctx["risk_latest"] is not None
            else ""
        )
        macro_clause = f" Macro link: {macro}." if macro else ""
        disruption_clause = (
            f" Linked disruptions: {'; '.join(disruptions)}." if disruptions else ""
        )
        notable = ctx["metric_anomalies"]
        notable_clause = (
            f" Other metrics also off-baseline: {'; '.join(notable)}." if notable else ""
        )
        favorability = ctx.get("favorability")
        adverse = favorability != "favorable"
        elevated = ctx["anomaly_level"] in ("elevated", "high")
        if favorability == "favorable":
            so_what = (
                f"This {abs(z):.2f}σ move is favorable (above baseline in a "
                f"beneficial direction), not a disruption."
            )
        else:
            so_what = f"This is a {ctx['anomaly_level']} anomaly likelihood."
        return {
            "what_happened": (
                f"Over the last {window}, {name}'s most anomalous metric ({ctx['metric']}) "
                f"sits {abs(z):.2f}σ {direction} its trailing mean "
                f"(z={z:.2f}, p={ctx['p_value']:.3f})." + trend_clause + notable_clause
            ),
            "so_what": (so_what + risk_clause + macro_clause + disruption_clause),
            "to_do": (
                "Watch related news and downstream entities for disruption signals; "
                "consider flagging this entity for closer monitoring."
                if (elevated and adverse) or disruptions
                else "No action needed; activity is within or above its normal range."
            ),
        }

    try:
        import json

        from app.llm.client import LLMResponse, chat_completion

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a maritime supply-chain analyst writing a briefing for a "
                    "logistics manager. The headline metric is the entity's most "
                    "anomalous one (`metric`); `metric_anomalies` lists other metrics "
                    "also off-baseline. IMPORTANT: respect `favorability` — an "
                    "'adverse' deviation raises risk (e.g. throughput dropping, freight "
                    "stress rising), while a 'favorable' one is beneficial (e.g. port "
                    "calls or transit volume surging above baseline). Never describe a "
                    "favorable surge as a disruption or crisis; frame it as positive "
                    "and keep the risk language proportionate to the composite risk "
                    "score. Using ALL the provided evidence (the headline "
                    "z-score anomaly + trend, other anomalous metrics, composite risk "
                    "score, macro-index lead-lag correlations, and linked disruptions), "
                    "return a JSON object with exactly three string keys:\n"
                    '  "what_happened": 1-2 sentences on the headline metric situation '
                    "and trend, citing its z-score and percent change; mention other "
                    "off-baseline metrics if present.\n"
                    '  "so_what": 1-2 sentences explaining why it matters — connect the '
                    "anomaly to the macro correlation and any linked disruption, and to "
                    "the risk score.\n"
                    '  "to_do": 1 concrete, specific recommended action for the manager.\n'
                    "Be factual and concise; cite the given numbers, do not invent any. "
                    "If a piece of evidence is absent, ignore it silently. "
                    "Return only the JSON object."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(ctx, default=str),
            },
        ]
        resp = chat_completion(messages)
        if isinstance(resp, LLMResponse) and resp.content.strip():
            parsed = json.loads(resp.content.strip())
            return {
                "what_happened": str(parsed["what_happened"]).strip(),
                "so_what": str(parsed["so_what"]).strip(),
                "to_do": str(parsed["to_do"]).strip(),
            }
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


def _freight_chart_key(index_name: str) -> tuple[str, int] | None:
    name_lower = index_name.lower()
    if "fbx" in name_lower:
        return ("fbx", 0)
    if "wci" in name_lower:
        return ("wci", 0)
    return _FRED_FREIGHT_PROXY_KEYS.get(index_name.upper())


def _build_indices_chart(session: Session, since: datetime) -> list[dict[str, Any]]:
    """Return pivoted freight-index series with fbx and wci-compatible keys."""
    # FRED freight proxies are monthly and can lag daily PortWatch windows by
    # more than 30 days, so the market chart needs a longer macro lookback.
    query_since = since - timedelta(days=_FREIGHT_INDEX_EXTRA_LOOKBACK_DAYS)
    rows = (
        session.query(FreightIndex)
        .filter(FreightIndex.time >= query_since)
        .order_by(FreightIndex.time)
        .all()
    )
    by_date: dict[str, dict[str, Any]] = defaultdict(dict)
    by_date_priority: dict[str, dict[str, int]] = defaultdict(dict)
    for r in rows:
        chart_key = _freight_chart_key(r.index_name)
        if chart_key is None:
            continue
        key, priority = chart_key
        date_str = r.time.date().isoformat()
        by_date[date_str]["time"] = date_str
        existing_priority = by_date_priority[date_str].get(key)
        if existing_priority is None or priority < existing_priority:
            by_date[date_str][key] = r.value
            by_date_priority[date_str][key] = priority
    return sorted(by_date.values(), key=lambda x: x["time"])


def _risk_series(
    session: Session, entity_type: str, entity_id: str, since: datetime
) -> list[dict[str, Any]]:
    """Dated risk-score history from RiskFeatureSnapshot (one point per day)."""
    rows = (
        session.query(RiskFeatureSnapshot)
        .filter(
            RiskFeatureSnapshot.entity_type == entity_type,
            RiskFeatureSnapshot.entity_id == entity_id,
            RiskFeatureSnapshot.snapshot_date >= since.date(),
        )
        .order_by(RiskFeatureSnapshot.snapshot_date)
        .all()
    )
    return [
        {"time": r.snapshot_date.isoformat(), "value": r.risk_score}
        for r in rows
        if r.risk_score is not None
    ]


def _macro_series_by_name(
    session: Session, since: datetime
) -> dict[str, list[dict[str, Any]]]:
    """Each freight index as its own {time,value} series (for correlation)."""
    rows = (
        session.query(FreightIndex)
        .filter(FreightIndex.time >= since)
        .order_by(FreightIndex.time)
        .all()
    )
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[r.index_name].append({"time": r.time.isoformat(), "value": r.value})
    return dict(out)


def _macro_findings(
    macro_by_name: dict[str, list[dict[str, Any]]],
    metrics_by_name: dict[str, list[dict[str, Any]]],
) -> list[MacroCorrelation]:
    """Compute top macro↔metric lead-lag correlations as schema objects."""
    findings = macro_sensitivity(macro_by_name, metrics_by_name)
    return [MacroCorrelation(**f) for f in findings]


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

    # --- Risk trend (dated daily history) ---
    risk_trend = _risk_series(session, "port", port.portid, since)

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

    # --- Macro sensitivity (lead-lag of this port's trade vs macro indices) ---
    port_metrics = {
        m: _metric_series(session, "port", port.portid, m, since)
        for m in ("port_calls", "import_volume", "export_volume")
    }
    macro_sens = _macro_findings(_macro_series_by_name(session, since), port_metrics)

    # --- Stats ---
    scores = [p["value"] for p in risk_trend]
    risk_latest: float | None = scores[-1] if scores else None
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
        macro_sensitivity=macro_sens,
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

    # --- Risk trend (dated daily history) ---
    risk_trend = _risk_series(session, "chokepoint", slug, since)

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

    # --- Macro sensitivity (lead-lag of transit volume vs macro indices) ---
    macro_sens = _macro_findings(
        _macro_series_by_name(session, since), {"transit_calls": transit_volume}
    )

    # --- Stats ---
    scores = [p["value"] for p in risk_trend]
    risk_latest: float | None = scores[-1] if scores else None
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
        macro_sensitivity=macro_sens,
    )
