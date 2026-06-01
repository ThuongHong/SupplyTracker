"""On-demand risk scoring + forecast for a single entity.

Used by the per-entity sync endpoint so Risk & Forecast populate right after a
user syncs an entity (rather than waiting for the hourly/daily beat). Scoring
writes one risk point at the current time; the trend then grows via the beat.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Metric forecasted per entity type (only metrics PortWatch actually provides).
_FORECAST_METRIC = {"port": "port_calls", "chokepoint": "transit_calls"}


def score_and_forecast_entity(
    session: Session, entity_type: str, entity_id: str, entity_name: str
) -> None:
    """Score the entity at today's as-of and forecast its throughput metric.

    Best-effort: individual failures are logged, not raised, so a sync still
    succeeds even if scoring/forecast can't run.
    """
    from app.analysis.events import detect_events
    from app.analysis.forecasting import generate_forecast
    from app.analysis.scoring import load_components, score_entity
    from app.services.insights import materialize_insights

    snapshot = None
    try:
        components, _ = load_components()
        _, snapshot = score_entity(
            session, entity_type, entity_id, entity_name, date.today(), components
        )
    except Exception:
        logger.exception("scoring failed for %s/%s", entity_type, entity_id)

    # Detect events + materialize insights now so the brief and insights feed
    # reflect a newly tracked entity immediately, without waiting for the hourly
    # scoring pipeline.
    if snapshot is not None:
        try:
            events = detect_events(session, snapshot, prev_severity=None)
            materialize_insights(session, events)
        except Exception:
            logger.exception(
                "event detection failed for %s/%s", entity_type, entity_id
            )

    metric = _FORECAST_METRIC.get(entity_type)
    if metric:
        try:
            generate_forecast(session, entity_type, entity_id, entity_name, metric)
        except Exception:
            logger.exception("forecast failed for %s/%s", entity_type, entity_id)

    session.commit()
