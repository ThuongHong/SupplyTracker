"""Backfill dated risk-score history.

Re-runs `score_entity` for each entity across the last N days so that
`RiskFeatureSnapshot` holds a real daily series (one snapshot per day),
which the dashboard uses for the risk trend. PortWatch daily metrics must
already be seeded for the window so baselines resolve.

Usage:
    python -m app.scripts.backfill_risk [days]   # default 30
"""
from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime, timedelta

from app.analysis.scoring import load_components, score_entity
from app.db.models import PortWatchMetric
from app.db.session import get_db

logger = logging.getLogger(__name__)


def backfill(days: int = 30) -> dict[str, int]:
    db_gen = get_db()
    session = next(db_gen)
    try:
        components, _ = load_components()
        entities = (
            session.query(
                PortWatchMetric.entity_type,
                PortWatchMetric.entity_id,
                PortWatchMetric.entity_name,
            )
            .distinct()
            .all()
        )
        today = datetime.now(tz=UTC).date()
        dates = [today - timedelta(days=d) for d in range(days - 1, -1, -1)]

        scored = 0
        errors = 0
        for as_of in dates:
            for entity_type, entity_id, entity_name in entities:
                try:
                    score_entity(
                        session, entity_type, entity_id, entity_name, as_of, components
                    )
                    scored += 1
                except Exception:
                    logger.exception(
                        "backfill score_entity failed %s/%s @ %s",
                        entity_type, entity_id, as_of,
                    )
                    errors += 1
            session.commit()
        return {"days": days, "entities": len(entities), "scored": scored, "errors": errors}
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    logging.basicConfig(level=logging.INFO)
    result = backfill(n)
    print(result)
