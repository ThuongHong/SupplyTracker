"""tasks/score.py — chained scoring DAG Celery task.

Pipeline (single task, runs steps sequentially in one worker process):

  1. compute baselines   (via score_entity which calls compute_baselines internally)
  2. score entities      (PortRiskScore + RiskFeatureSnapshot per port & chokepoint)
  3. detect events       (RiskStoryEvent rows)
  4. propagate disruption (DisruptionPropagation rows for chokepoint events)
  5. materialize insights (Insight rows for high/medium events)
  6. fill narratives     (queued as a separate task so LLM calls don't block)

Each step uses its own DB session to keep transactions short.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def _get_session():  # type: ignore[return]
    """Open a DB session and return (session, db_gen) for manual lifecycle."""
    from app.db.session import get_db
    db_gen = get_db()
    session = next(db_gen)
    return session, db_gen


def _close_session(db_gen: Any) -> None:
    try:
        next(db_gen)
    except StopIteration:
        pass


# ── step 1+2: score all entities ───────────────────────────────────────────────

def _step_score_entities(as_of: date) -> dict[str, Any]:
    """Score every port and chokepoint that has PortWatchMetric data.

    Returns a mapping of entity_key → snapshot so later steps can detect events.
    """
    from app.analysis.scoring import load_components, score_entity
    from app.db.models import PortWatchMetric

    session, db_gen = _get_session()
    snapshots: list[Any] = []
    try:
        components, _ = load_components()

        # Discover all distinct entities from metric data
        rows = (
            session.query(
                PortWatchMetric.entity_type,
                PortWatchMetric.entity_id,
                PortWatchMetric.entity_name,
            )
            .distinct()
            .all()
        )

        scored = 0
        errors = 0
        for entity_type, entity_id, entity_name in rows:
            try:
                _risk_score, snapshot = score_entity(
                    session,
                    entity_type,
                    entity_id,
                    entity_name,
                    as_of,
                    components,
                )
                snapshots.append(snapshot)
                scored += 1
            except Exception:
                logger.exception(
                    "score_entity failed for %s/%s", entity_type, entity_id
                )
                errors += 1

        session.commit()
        logger.info("step_score_entities: scored=%d errors=%d", scored, errors)
        return {"scored": scored, "errors": errors, "snapshots": snapshots}
    except Exception:
        session.rollback()
        raise
    finally:
        _close_session(db_gen)


# ── step 3+4: detect events + propagate disruptions ───────────────────────────

def _step_detect_and_propagate(snapshots: list[Any]) -> list[Any]:
    """Detect RiskStoryEvents from snapshots and propagate chokepoint disruptions."""
    from app.analysis.events import detect_events
    from app.services.disruption import propagate_chokepoint_event

    session, db_gen = _get_session()
    all_events: list[Any] = []
    try:
        for snapshot in snapshots:
            try:
                events = detect_events(session, snapshot, prev_severity=None)
                all_events.extend(events)

                for event in events:
                    if snapshot.entity_type == "chokepoint":
                        try:
                            propagate_chokepoint_event(session, event)
                        except Exception:
                            logger.exception(
                                "propagate_chokepoint_event failed for event %s",
                                getattr(event, "event_key", "<unknown>"),
                            )
            except Exception:
                logger.exception(
                    "detect_events failed for snapshot entity_id=%s",
                    getattr(snapshot, "entity_id", "<unknown>"),
                )

        session.commit()
        logger.info("step_detect_and_propagate: events=%d", len(all_events))
        return all_events
    except Exception:
        session.rollback()
        raise
    finally:
        _close_session(db_gen)


# ── step 5: materialize insights ──────────────────────────────────────────────

def _step_materialize_insights(events: list[Any]) -> int:
    """Create Insight rows for high/medium-attention events."""
    from app.services.insights import materialize_insights

    session, db_gen = _get_session()
    try:
        insights = materialize_insights(session, events)
        session.commit()
        count = len(insights)
        logger.info("step_materialize_insights: insights=%d", count)
        return count
    except Exception:
        session.rollback()
        raise
    finally:
        _close_session(db_gen)


# ── main pipeline task ─────────────────────────────────────────────────────────

@celery_app.task(name="score.run_pipeline", bind=True, max_retries=1, default_retry_delay=300)
def run_pipeline(self: Any) -> dict[str, Any]:
    """Run the full PortWatch → features → score → events → insights → narrate chain.

    Steps run sequentially within this task so each step can consume results
    from the previous one.  The final narrate step is queued as a separate
    async task to avoid blocking this worker on LLM calls.
    """
    as_of = date.today()
    logger.info("score.run_pipeline starting for as_of=%s", as_of)

    try:
        # Step 1+2: compute baselines + score entities
        score_result = _step_score_entities(as_of)
        snapshots = score_result["snapshots"]

        # Step 3+4: detect events + propagate disruptions
        events = _step_detect_and_propagate(snapshots)

        # Step 5: materialize insights
        insight_count = _step_materialize_insights(events)

        # Step 6: queue narrative fill as a separate task (non-blocking)
        from app.tasks.narrate import fill_narratives
        fill_narratives.delay()

        summary = {
            "as_of": as_of.isoformat(),
            "entities_scored": score_result["scored"],
            "score_errors": score_result["errors"],
            "events_detected": len(events),
            "insights_created": insight_count,
        }
        logger.info("score.run_pipeline done: %s", summary)
        return summary

    except Exception as exc:
        logger.exception("score.run_pipeline failed: %s", exc)
        raise self.retry(exc=exc)
