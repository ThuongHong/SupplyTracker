from __future__ import annotations

from celery import Celery

from app.config import get_settings

# Task modules holding @celery_app.task definitions. Listed explicitly because
# the tasks live in named modules (collect.py, score.py, …), not the default
# `app.tasks.tasks` that autodiscover_tasks would look for — without this the
# worker registers zero tasks and raises KeyError on every received message.
_TASK_MODULES = [
    "app.tasks.collect",
    "app.tasks.score",
    "app.tasks.forecast",
    "app.tasks.narrate",
]


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "supplytracker",
        broker=str(settings.celery_broker_url),
        backend=str(settings.celery_result_backend),
        include=_TASK_MODULES,
    )
    app.config_from_object(
        {
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
            "timezone": "UTC",
            "enable_utc": True,
        }
    )
    return app


celery_app = make_celery()

# Importing schedule registers celery_app.conf.beat_schedule for celery-beat.
from app.tasks import schedule as _schedule  # noqa: E402,F401
