"""tasks/forecast.py — daily AutoETS forecast pass.

Queries all distinct (entity_type, entity_id, entity_name, metric_name)
combinations from PortWatchMetric and runs generate_forecast() for each.
Designed to run once per day at midnight UTC.
"""
from __future__ import annotations

import logging
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="forecast.run_forecast", bind=True, max_retries=1, default_retry_delay=600)
def run_forecast(self: Any) -> dict[str, Any]:
    """Run the AutoETS forecasting pipeline for all tracked entities and metrics.

    For each distinct (entity_type, entity_id, metric_name) combination found
    in PortWatchMetric, fits an AutoETS model and upserts an EntityRiskForecast
    row with a 14-day horizon.
    """
    from app.analysis.forecasting import generate_forecast
    from app.db.models import PortWatchMetric
    from app.db.session import get_db

    db_gen = get_db()
    session = next(db_gen)
    forecasted = 0
    errors = 0

    try:
        # Discover all distinct entity + metric combinations
        combinations = (
            session.query(
                PortWatchMetric.entity_type,
                PortWatchMetric.entity_id,
                PortWatchMetric.entity_name,
                PortWatchMetric.metric_name,
            )
            .distinct()
            .all()
        )

        logger.info(
            "forecast.run_forecast: found %d entity-metric combinations",
            len(combinations),
        )

        for entity_type, entity_id, entity_name, metric_name in combinations:
            try:
                generate_forecast(
                    session=session,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    metric_name=metric_name,
                    horizon_days=14,
                )
                session.commit()
                forecasted += 1
            except Exception:
                logger.exception(
                    "generate_forecast failed for %s/%s metric=%s",
                    entity_type,
                    entity_id,
                    metric_name,
                )
                session.rollback()
                errors += 1

        summary = {
            "combinations_attempted": len(combinations),
            "forecasted": forecasted,
            "errors": errors,
        }
        logger.info("forecast.run_forecast done: %s", summary)
        return summary

    except Exception as exc:
        logger.exception("forecast.run_forecast fatal error: %s", exc)
        session.rollback()
        raise self.retry(exc=exc) from exc
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
