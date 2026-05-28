from __future__ import annotations

from celery import Celery

from app.config import get_settings


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "supplytracker",
        broker=str(settings.celery_broker_url),
        backend=str(settings.celery_result_backend),
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
