"""tasks/schedule.py — Celery-beat schedule for SupplyTracker.

Cadences
--------
- PortWatch refresh    : daily at 05:00 UTC (latest day for TRACKED entities)
- FRED collector       : daily at 06:00 UTC  (economics data updated daily)
- FBX scraper          : daily at 07:00 UTC  (Freightos Baltic Index)
- WCI scraper          : daily at 07:30 UTC  (World Container Index)
- Bunker scraper       : daily at 08:00 UTC  (bunker fuel prices)
- Scoring pipeline     : every hour at :30  (runs after PortWatch collection)
- Forecast pipeline    : daily at 00:00 UTC (AutoETS model daily pass)
- Narrative fill       : daily at 02:00 UTC (LLM narrative for new insights)
"""
from __future__ import annotations

from celery.schedules import crontab

from app.tasks.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # ── Collectors ────────────────────────────────────────────────
    "collect-portwatch-daily": {
        "task": "collect.portwatch",
        # Latest day for tracked entities; PortWatch updates ~weekly so daily
        # is ample. Runs before the hourly scoring pass picks it up.
        "schedule": crontab(hour="5", minute="0"),
        "options": {"queue": "collection"},
    },
    "collect-fred-daily": {
        "task": "collect.fred",
        "schedule": crontab(hour="6", minute="0"),
        "options": {"queue": "collection"},
    },
    "collect-fbx-daily": {
        "task": "collect.fbx",
        "schedule": crontab(hour="7", minute="0"),
        "options": {"queue": "collection"},
    },
    "collect-wci-daily": {
        "task": "collect.wci",
        "schedule": crontab(hour="7", minute="30"),
        "options": {"queue": "collection"},
    },
    "collect-bunker-daily": {
        "task": "collect.bunker",
        "schedule": crontab(hour="8", minute="0"),
        "options": {"queue": "collection"},
    },
    "collect-news-6h": {
        "task": "collect.news",
        "schedule": crontab(minute="15", hour="*/6"),
        "options": {"queue": "collection"},
    },
    # ── Scoring / risk pipeline ────────────────────────────────────
    # Runs 30 min after the top of each hour so PortWatch data is ingested
    "score-pipeline-hourly": {
        "task": "score.run_pipeline",
        "schedule": crontab(minute="30"),
        "options": {"queue": "analysis"},
    },
    # ── Forecasting ────────────────────────────────────────────────
    "forecast-daily-midnight": {
        "task": "forecast.run_forecast",
        "schedule": crontab(hour="0", minute="0"),
        "options": {"queue": "analysis"},
    },
    # ── Narrative fill ─────────────────────────────────────────────
    "narrate-fill-daily": {
        "task": "narrate.fill_narratives",
        "schedule": crontab(hour="2", minute="0"),
        "options": {"queue": "narrate"},
    },
}

celery_app.conf.task_default_queue = "default"
