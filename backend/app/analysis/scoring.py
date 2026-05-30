from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.analysis.baselines import (
    compute_baselines,
    compute_robust_z_score,
    summarize_values,
)
from app.db.models import (
    ChokepointRiskScore,
    FreightIndex,
    NewsItem,
    PortRiskScore,
    PortWatchMetric,
    RiskFeatureSnapshot,
)

logger = logging.getLogger(__name__)

# Load config once at module level
_YAML_PATH = Path(__file__).parent / "risk_components.yaml"
_config: dict[str, Any] = yaml.safe_load(_YAML_PATH.read_text())


@dataclass
class ComponentDef:
    name: str
    metric: str
    weight: float
    baseline_window_days: int
    direction: str  # "higher_is_better" | "higher_is_worse"
    entity_types: list[str]
    source: str = "portwatch"  # "portwatch" | "news" | "macro"
    index_name: str | None = None  # for source="macro"


def load_components() -> tuple[list[ComponentDef], dict[str, Any]]:
    """Return (components, config) loaded from risk_components.yaml."""
    components = [
        ComponentDef(
            name=c["name"],
            metric=c["metric"],
            weight=c["weight"],
            baseline_window_days=c["baseline_window_days"],
            direction=c["direction"],
            entity_types=c["entity_types"],
            source=c.get("source", "portwatch"),
            index_name=c.get("index_name"),
        )
        for c in _config["components"]
    ]
    return components, _config


def severity_from_score(score: float, thresholds: list[float]) -> str:
    """Map a score in [0,1] to a severity label using the threshold list.

    thresholds = [low_bound, elevated_bound, high_bound]
    score < thresholds[0]  → "low"
    score < thresholds[1]  → "elevated"
    score < thresholds[2]  → "high"
    score >= thresholds[2] → "critical"
    """
    if score < thresholds[0]:
        return "low"
    if score < thresholds[1]:
        return "elevated"
    if score < thresholds[2]:
        return "high"
    return "critical"


def _get_latest_metric(
    session: Session,
    entity_type: str,
    entity_id: str,
    metric_name: str,
    as_of_date: date,
) -> PortWatchMetric | None:
    """Query the latest PortWatchMetric on or before as_of_date."""
    cutoff = datetime(
        as_of_date.year, as_of_date.month, as_of_date.day, 23, 59, 59, tzinfo=UTC
    )
    return (
        session.query(PortWatchMetric)
        .filter(
            PortWatchMetric.entity_type == entity_type,
            PortWatchMetric.entity_id == entity_id,
            PortWatchMetric.metric_name == metric_name,
            PortWatchMetric.observed_at <= cutoff,
        )
        .order_by(PortWatchMetric.observed_at.desc())
        .first()
    )


def _day_end(as_of_date: date) -> datetime:
    return datetime(
        as_of_date.year, as_of_date.month, as_of_date.day, 23, 59, 59, tzinfo=UTC
    )


def _news_pressure_z(
    session: Session,
    entity_type: str,
    entity_id: str,
    as_of_date: date,
    window_days: int,
    n_buckets: int = 8,
) -> float | None:
    """Robust z-score of the latest window's news volume vs prior windows.

    A surge in news coverage relative to its own trailing baseline pushes risk
    up (direction is handled by the caller). Returns None when there is not
    enough history to form a baseline.
    """
    try:
        end = _day_end(as_of_date)
        start = end - timedelta(days=window_days * (n_buckets + 1))
        rows = (
            session.query(NewsItem.published_at)
            .filter(
                NewsItem.entity_type == entity_type,
                NewsItem.entity_id == entity_id,
                NewsItem.published_at >= start,
                NewsItem.published_at <= end,
            )
            .all()
        )
        times = [r[0] for r in rows]
        if not times:
            return None
        buckets = [0] * (n_buckets + 1)
        for t in times:
            days_ago = (end - t).total_seconds() / 86400.0
            idx = int(days_ago // window_days)
            if 0 <= idx <= n_buckets:
                buckets[idx] += 1
        latest = float(buckets[0])
        baseline = [float(b) for b in buckets[1:]]
        summ = summarize_values(baseline)
        return compute_robust_z_score(latest, summ["median"], summ["mad"])
    except Exception:
        logger.info("news_pressure unavailable for %s/%s", entity_type, entity_id)
        return None


def _macro_stress_z(
    session: Session,
    index_name: str | None,
    as_of_date: date,
    window_days: int,
) -> float | None:
    """Robust z-score of the latest freight-index value vs its trailing window.

    Global overlay: every entity gets the same macro contribution. Rising
    freight rates signal system-wide stress. Returns None when data is sparse.
    """
    try:
        if not index_name:
            return None
        end = _day_end(as_of_date)
        start = end - timedelta(days=window_days)
        rows = (
            session.query(FreightIndex)
            .filter(
                FreightIndex.index_name == index_name,
                FreightIndex.time >= start,
                FreightIndex.time <= end,
            )
            .order_by(FreightIndex.time.asc())
            .all()
        )
        values = [r.value for r in rows]
        if len(values) < 2:
            return None
        summ = summarize_values(values)
        return compute_robust_z_score(values[-1], summ["median"], summ["mad"])
    except Exception:
        logger.info("macro_stress unavailable for index %s", index_name)
        return None


def score_entity(
    session: Session,
    entity_type: str,
    entity_id: str,
    entity_name: str,
    as_of_date: date,
    components: list[ComponentDef],
) -> tuple[PortRiskScore | ChokepointRiskScore, RiskFeatureSnapshot]:
    """Score an entity and persist PortRiskScore/ChokepointRiskScore and RiskFeatureSnapshot.

    Returns (risk_score_row, snapshot_row).
    """
    thresholds: list[float] = _config["severity_thresholds"]
    max_missing: float = _config["max_missing_fraction"]

    # Filter components applicable to this entity_type
    applicable = [c for c in components if entity_type in c.entity_types]
    total_components = len(applicable)

    feature_values: dict[str, float] = {}
    baseline_values: dict[str, dict[str, Any]] = {}
    z_scores: dict[str, dict[str, float | None]] = {}
    component_scores: dict[str, float] = {}
    missing_components: list[str] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for comp in applicable:
        # Each branch produces a robust z-score (median/MAD) for the component,
        # or None when data is too sparse to score it.
        z_for_score: float | None = None

        if comp.source == "portwatch":
            row = _get_latest_metric(
                session, entity_type, entity_id, comp.metric, as_of_date
            )
            if row is None:
                missing_components.append(comp.name)
                continue

            value = row.metric_value
            feature_values[comp.metric] = value

            # 30-day baseline (canonical window)
            bl_30 = compute_baselines(
                session, entity_type, entity_id, as_of_date, comp.metric, comp.baseline_window_days
            )
            # 90-day baseline for the snapshot's z_scores dict (informational)
            bl_90 = compute_baselines(
                session, entity_type, entity_id, as_of_date, comp.metric, 90
            )

            baseline_values[comp.metric] = {
                f"median_{comp.baseline_window_days}d": bl_30["median"],
                f"mad_{comp.baseline_window_days}d": bl_30["mad"],
                "count_30d": bl_30["count"],
                "median_90d": bl_90["median"],
                "mad_90d": bl_90["mad"],
                "count_90d": bl_90["count"],
            }

            z_30 = compute_robust_z_score(value, bl_30["median"], bl_30["mad"])
            z_90 = compute_robust_z_score(value, bl_90["median"], bl_90["mad"])
            z_scores[comp.metric] = {"z_30d": z_30, "z_90d": z_90}

            # Use z_30 for scoring; if unavailable fall back to z_90
            z_for_score = z_30 if z_30 is not None else z_90

        elif comp.source == "news":
            z_for_score = _news_pressure_z(
                session, entity_type, entity_id, as_of_date, comp.baseline_window_days
            )
            if z_for_score is not None:
                z_scores[comp.metric] = {"z_30d": z_for_score, "z_90d": None}

        elif comp.source == "macro":
            z_for_score = _macro_stress_z(
                session, comp.index_name, as_of_date, comp.baseline_window_days
            )
            if z_for_score is not None:
                z_scores[comp.metric] = {"z_30d": z_for_score, "z_90d": None}

        # Treat any component without a usable z-score as missing rather than
        # scoring it as a neutral z=0.
        if z_for_score is None:
            missing_components.append(comp.name)
            continue

        # Negate z for "higher_is_better" so high value = lower risk
        if comp.direction == "higher_is_better":
            z_for_score = -z_for_score

        # Clip to [-3, 3] and normalize to [0, 1]
        z_clipped = max(-3.0, min(3.0, z_for_score))
        normalized = (z_clipped + 3.0) / 6.0

        component_scores[comp.name] = normalized
        weighted_sum += normalized * comp.weight
        weight_total += comp.weight

    # Check missing fraction
    missing_count = len(missing_components)
    missing_fraction = missing_count / total_components if total_components > 0 else 1.0

    reasons: list[str] = []
    if missing_fraction > max_missing or weight_total == 0:
        severity = "unknown"
        final_score: float | None = None
        # Fix #2: set reasons when insufficient
        reasons = ["insufficient_components"]
    else:
        # Normalize by actual weight covered
        final_score = weighted_sum / weight_total
        severity = severity_from_score(final_score, thresholds)

    # Fix #1: build driver_metadata with active thresholds and weights
    driver_metadata: dict[str, Any] = {
        "thresholds": thresholds,
        "schema_version": _config["schema_version"],
        "baseline_method": _config.get("baseline_method", "robust_median_mad"),
        "component_weights": {c.name: c.weight for c in applicable},
        "component_sources": {c.name: c.source for c in applicable},
    }

    now = datetime.now(tz=UTC)
    as_of_dt = datetime(as_of_date.year, as_of_date.month, as_of_date.day, tzinfo=UTC)
    freshness_status = "ok" if missing_fraction == 0 else ("degraded" if missing_fraction <= max_missing else "insufficient")

    # Upsert RiskFeatureSnapshot
    snap_stmt = (
        pg_insert(RiskFeatureSnapshot)
        .values(
            snapshot_date=as_of_date,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            risk_score=final_score,
            severity=severity,
            feature_values=feature_values,
            baseline_values=baseline_values,
            z_scores=z_scores,
            deltas={},
            missing_features=missing_components,
            driver_metadata=driver_metadata,
            feature_schema_version=_config["schema_version"],
        )
        .on_conflict_do_update(
            index_elements=["snapshot_date", "entity_type", "entity_id"],
            set_={
                "entity_name": entity_name,
                "risk_score": final_score,
                "severity": severity,
                "feature_values": feature_values,
                "baseline_values": baseline_values,
                "z_scores": z_scores,
                "missing_features": missing_components,
                "driver_metadata": driver_metadata,
                "feature_schema_version": _config["schema_version"],
            },
        )
        .returning(RiskFeatureSnapshot)
    )
    snap_result = session.execute(snap_stmt)
    session.flush()
    snap_result.fetchone()

    # Build a detached RiskFeatureSnapshot for return
    snapshot = RiskFeatureSnapshot(
        snapshot_date=as_of_date,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        risk_score=final_score,
        severity=severity,
        feature_values=feature_values,
        baseline_values=baseline_values,
        z_scores=z_scores,
        deltas={},
        missing_features=missing_components,
        driver_metadata=driver_metadata,
        feature_schema_version=_config["schema_version"],
    )

    # Upsert risk score row
    score_common = dict(
        entity_id=entity_id,
        entity_name=entity_name,
        score=final_score,
        severity=severity,
        component_scores=component_scores,
        missing_components=missing_components,
        reasons=reasons,
        freshness_status=freshness_status,
        as_of=as_of_dt,
    )

    risk_score_obj: PortRiskScore | ChokepointRiskScore
    if entity_type == "port":
        stmt = (
            pg_insert(PortRiskScore)
            .values(time=now, **score_common)
            .on_conflict_do_update(
                index_elements=["time", "entity_id"],
                set_=score_common,
            )
        )
        session.execute(stmt)
        session.flush()
        risk_score_obj = PortRiskScore(time=now, **score_common)
    else:
        stmt = (
            pg_insert(ChokepointRiskScore)
            .values(time=now, **score_common)
            .on_conflict_do_update(
                index_elements=["time", "entity_id"],
                set_=score_common,
            )
        )
        session.execute(stmt)
        session.flush()
        risk_score_obj = ChokepointRiskScore(time=now, **score_common)

    return risk_score_obj, snapshot
