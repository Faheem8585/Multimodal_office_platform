"""Celery application for background processing (OCR, parsing, embedding).

Redis is broker and result backend. Heavy/slow work (ingestion) runs here so
API requests stay fast and we get retries-with-backoff and concurrency control
for free.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "office_platform",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,  # redeliver if a worker dies mid-task
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # fair dispatch for long tasks
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)
