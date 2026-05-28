"""tasks/collect.py — per-collector Celery tasks + collect_all chord.

Individual tasks
----------------
collect_portwatch, collect_fred, collect_fbx, collect_wci, collect_bunker

Chord
-----
collect_all()  →  group(all individual tasks) | _on_collect_all_done callback
"""
from __future__ import annotations

import logging
from typing import Any

from celery import chord, group

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# ── helper ────────────────────────────────────────────────────────────────────

def _run_collector(collector_cls: type) -> dict[str, Any]:
    """Instantiate *collector_cls*, open a DB session, run, and return summary."""
    from app.db.session import get_db

    collector = collector_cls()
    db_gen = get_db()
    session = next(db_gen)
    try:
        result = collector.run(session)
        return {
            "source": collector.source_name,
            "rows": result.rows,
            "errors": result.errors,
        }
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


# ── individual collector tasks ─────────────────────────────────────────────────

@celery_app.task(name="collect.portwatch", bind=True, max_retries=3, default_retry_delay=60)
def collect_portwatch(self: Any) -> dict[str, Any]:
    """Collect data from the PortWatch API."""
    try:
        from app.collectors.portwatch import PortWatchCollector
        return _run_collector(PortWatchCollector)
    except Exception as exc:
        logger.error("collect_portwatch failed, retrying: %s", exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(name="collect.fred", bind=True, max_retries=3, default_retry_delay=120)
def collect_fred(self: Any) -> dict[str, Any]:
    """Collect FRED economic indicators."""
    try:
        from app.collectors.fred import FREDCollector
        return _run_collector(FREDCollector)
    except Exception as exc:
        logger.error("collect_fred failed, retrying: %s", exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(name="collect.fbx", bind=True, max_retries=3, default_retry_delay=120)
def collect_fbx(self: Any) -> dict[str, Any]:
    """Scrape Freightos Baltic Index (FBX)."""
    try:
        from app.collectors.fbx_scraper import FBXCollector
        return _run_collector(FBXCollector)
    except Exception as exc:
        logger.error("collect_fbx failed, retrying: %s", exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(name="collect.wci", bind=True, max_retries=3, default_retry_delay=120)
def collect_wci(self: Any) -> dict[str, Any]:
    """Scrape World Container Index (WCI)."""
    try:
        from app.collectors.wci_scraper import WCICollector
        return _run_collector(WCICollector)
    except Exception as exc:
        logger.error("collect_wci failed, retrying: %s", exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(name="collect.bunker", bind=True, max_retries=3, default_retry_delay=120)
def collect_bunker(self: Any) -> dict[str, Any]:
    """Scrape bunker fuel prices."""
    try:
        from app.collectors.bunker_scraper import BunkerCollector
        return _run_collector(BunkerCollector)
    except Exception as exc:
        logger.error("collect_bunker failed, retrying: %s", exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(name="collect.news", bind=True, max_retries=3, default_retry_delay=120)
def collect_news(self: Any) -> dict[str, Any]:
    """Collect Google News items per port and chokepoint."""
    try:
        from app.collectors.google_news import GoogleNewsCollector
        return _run_collector(GoogleNewsCollector)
    except Exception as exc:
        logger.error("collect_news failed, retrying: %s", exc)
        raise self.retry(exc=exc) from exc


# ── chord callback ─────────────────────────────────────────────────────────────

@celery_app.task(name="collect._on_collect_all_done")
def _on_collect_all_done(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Chord callback — aggregates individual collector results."""
    total_rows = sum(r.get("rows", 0) for r in results if isinstance(r, dict))
    total_errors = sum(len(r.get("errors", [])) for r in results if isinstance(r, dict))
    summary = {
        "collectors": len(results),
        "total_rows": total_rows,
        "total_errors": total_errors,
        "results": results,
    }
    logger.info(
        "collect_all finished: collectors=%d rows=%d errors=%d",
        summary["collectors"],
        summary["total_rows"],
        summary["total_errors"],
    )
    return summary


# ── collect_all chord ─────────────────────────────────────────────────────────

@celery_app.task(name="collect.collect_all")
def collect_all() -> str:
    """Launch all collectors in parallel (group) and aggregate via chord callback.

    Returns the task ID (str) of the chord so callers can poll status via
    AsyncResult(id) without serialisation errors in the result backend.
    """
    individual = group(
        collect_portwatch.s(),
        collect_fred.s(),
        collect_fbx.s(),
        collect_wci.s(),
        collect_bunker.s(),
        collect_news.s(),
    )
    pipeline = chord(individual, _on_collect_all_done.s())
    result = pipeline.delay()
    return str(result.id)
