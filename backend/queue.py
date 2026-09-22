"""Redis Queue connection and enqueue helpers."""

from __future__ import annotations

from redis import Redis
from rq import Queue

from .config import get_settings


def get_redis_connection() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def get_queue() -> Queue:
    settings = get_settings()
    return Queue(settings.queue_name, connection=get_redis_connection())


def enqueue_identification(job_id: str):
    settings = get_settings()
    return get_queue().enqueue(
        "backend.tasks.run_identification_task",
        job_id,
        job_id=f"identify-{job_id}",
        job_timeout=settings.job_timeout_seconds,
        result_ttl=settings.result_ttl_seconds,
        failure_ttl=settings.result_ttl_seconds,
    )

