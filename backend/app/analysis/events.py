from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import PortWatchMetric, RiskFeatureSnapshot, RiskStoryEvent

# Severity / attention mappings per event type
_SEVERITY_MAP: dict[str, str] = {
    "z_spike": "high",
    "severity_step_up": "high",
    "severity_step_down": "low",
    "sustained_streak": "elevated",
}

_ATTENTION_MAP: dict[str, str] = {
    "z_spike": "high",
    "severity_step_up": "high",
    "severity_step_down": "low",
    "sustained_streak": "medium",
}

_CONFIDENCE_MAP: dict[str, float] = {
    "z_spike": 0.9,
    "severity_step_up": 0.8,
    "severity_step_down": 0.8,
    "sustained_streak": 0.7,
}

# Severity ordering for step detection
_SEVERITY_ORDER: dict[str, int] = {
    "unknown": 0,
    "low": 1,
    "elevated": 2,
    "high": 3,
    "critical": 4,
}


def _event_key(
    entity_type: str,
    entity_id: str,
    event_date: str,
    event_type: str,
    metric: str = "",
) -> str:
    return f"{entity_type}:{entity_id}:{event_date}:{event_type}:{metric}"


def _upsert_event(session: Session, event_data: dict[str, Any]) -> RiskStoryEvent:
    """Upsert a RiskStoryEvent by event_key and return a detached object."""
    stmt = (
        pg_insert(RiskStoryEvent)
        .values(**event_data)
        .on_conflict_do_update(
            index_elements=["event_key"],
            set_={k: v for k, v in event_data.items() if k != "event_key"},
        )
    )
    session.execute(stmt)
    session.flush()
    # Return a detached object for the caller
    return RiskStoryEvent(**event_data)


def detect_events(
    session: Session,
    snapshot: RiskFeatureSnapshot,
    prev_severity: str | None,
) -> list[RiskStoryEvent]:
    """Detect and upsert RiskStoryEvent rows for the given snapshot.

    Detects:
      - z_spike: |z_30d| >= 2.5 for any metric
      - severity_step_up / severity_step_down: severity rank changed
      - sustained_streak: metric above/below mean for 5+ consecutive days
    """
    events: list[RiskStoryEvent] = []
    now = datetime.now(tz=UTC)
    date_str = snapshot.snapshot_date.isoformat()
    entity_type = snapshot.entity_type
    entity_id = snapshot.entity_id
    entity_name = snapshot.entity_name
    current_severity = snapshot.severity or "unknown"

    z_scores: dict[str, dict[str, float | None]] = snapshot.z_scores or {}
    feature_values: dict[str, float] = snapshot.feature_values or {}
    baseline_values: dict[str, dict[str, Any]] = snapshot.baseline_values or {}

    # --- z_spike events ---
    for metric, zd in z_scores.items():
        z_30 = zd.get("z_30d")
        if z_30 is not None and abs(z_30) >= 2.5:
            observed = feature_values.get(metric)
            bl = baseline_values.get(metric, {})
            expected = bl.get("mean_30d") or bl.get("mean_90d")
            narrative = (
                f"Metric {metric} z-score {z_30:.1f} on {date_str} for {entity_id}"
            )
            key = _event_key(entity_type, entity_id, date_str, "z_spike", metric)
            event_data: dict[str, Any] = {
                "event_key": key,
                "event_time": now,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "event_type": "z_spike",
                "severity": _SEVERITY_MAP["z_spike"],
                "metric": metric,
                "observed": observed,
                "expected": expected,
                "z_score": z_30,
                "percent_change": (
                    ((observed - expected) / abs(expected) * 100)
                    if observed is not None and expected is not None and expected != 0
                    else None
                ),
                "narrative": narrative,
                "confidence": _CONFIDENCE_MAP["z_spike"],
                "attention_level": _ATTENTION_MAP["z_spike"],
            }
            events.append(_upsert_event(session, event_data))

    # --- severity step events ---
    prev_rank = _SEVERITY_ORDER.get(prev_severity or "unknown", 0)
    curr_rank = _SEVERITY_ORDER.get(current_severity, 0)

    if curr_rank > prev_rank and prev_severity is not None:
        event_type = "severity_step_up"
        narrative = (
            f"Severity increased from {prev_severity} to {current_severity} "
            f"on {date_str} for {entity_id}"
        )
        key = _event_key(entity_type, entity_id, date_str, event_type)
        event_data = {
            "event_key": key,
            "event_time": now,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "event_type": event_type,
            "severity": _SEVERITY_MAP[event_type],
            "metric": "",
            "observed": snapshot.risk_score,
            "expected": None,
            "z_score": None,
            "percent_change": None,
            "narrative": narrative,
            "confidence": _CONFIDENCE_MAP[event_type],
            "attention_level": _ATTENTION_MAP[event_type],
        }
        events.append(_upsert_event(session, event_data))

    elif curr_rank < prev_rank and prev_severity is not None:
        event_type = "severity_step_down"
        narrative = (
            f"Severity decreased from {prev_severity} to {current_severity} "
            f"on {date_str} for {entity_id}"
        )
        key = _event_key(entity_type, entity_id, date_str, event_type)
        event_data = {
            "event_key": key,
            "event_time": now,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "event_type": event_type,
            "severity": _SEVERITY_MAP[event_type],
            "metric": "",
            "observed": snapshot.risk_score,
            "expected": None,
            "z_score": None,
            "percent_change": None,
            "narrative": narrative,
            "confidence": _CONFIDENCE_MAP[event_type],
            "attention_level": _ATTENTION_MAP[event_type],
        }
        events.append(_upsert_event(session, event_data))

    # --- sustained_streak events ---
    for metric, bl in baseline_values.items():
        mean_val = bl.get("mean_30d") or bl.get("mean_90d")
        if mean_val is None:
            continue

        # Query last 5 days of PortWatchMetric for this metric
        cutoff_end = datetime(
            snapshot.snapshot_date.year,
            snapshot.snapshot_date.month,
            snapshot.snapshot_date.day,
            23, 59, 59,
            tzinfo=UTC,
        )
        cutoff_start = cutoff_end - timedelta(days=5)
        recent_rows = (
            session.query(PortWatchMetric)
            .filter(
                PortWatchMetric.entity_type == entity_type,
                PortWatchMetric.entity_id == entity_id,
                PortWatchMetric.metric_name == metric,
                PortWatchMetric.observed_at >= cutoff_start,
                PortWatchMetric.observed_at <= cutoff_end,
            )
            .order_by(PortWatchMetric.observed_at.desc())
            .all()
        )

        if len(recent_rows) < 5:
            continue

        recent_values = [r.metric_value for r in recent_rows]
        all_above = all(v > mean_val for v in recent_values)
        all_below = all(v < mean_val for v in recent_values)

        if all_above or all_below:
            direction_label = "above" if all_above else "below"
            narrative = (
                f"Metric {metric} has been {direction_label} its mean for 5+ days "
                f"as of {date_str} for {entity_id}"
            )
            key = _event_key(entity_type, entity_id, date_str, "sustained_streak", metric)
            event_data = {
                "event_key": key,
                "event_time": now,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "event_type": "sustained_streak",
                "severity": _SEVERITY_MAP["sustained_streak"],
                "metric": metric,
                "observed": feature_values.get(metric),
                "expected": mean_val,
                "z_score": z_scores.get(metric, {}).get("z_30d"),
                "percent_change": None,
                "narrative": narrative,
                "confidence": _CONFIDENCE_MAP["sustained_streak"],
                "attention_level": _ATTENTION_MAP["sustained_streak"],
            }
            events.append(_upsert_event(session, event_data))

    return events
