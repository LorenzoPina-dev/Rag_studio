"""Celery application foundation for asynchronous/background execution."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "rag_studio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

# Scalable defaults; tune per environment/deployment.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        "app.workers.tasks.execute_pipeline": {"queue": "executions"},
        "app.workers.tasks.execute_node": {"queue": "executions"},
    },
)


def get_celery_app() -> Celery:
    return celery_app
