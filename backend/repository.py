"""Small repository layer for explicit task-state transitions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .models import IdentificationJob


TERMINAL_STATUSES = {"completed", "rejected", "failed"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_job(session: Session, job_id: str) -> IdentificationJob | None:
    return session.get(IdentificationJob, job_id)


def set_job_status(
    session: Session,
    job: IdentificationJob,
    status: str,
    *,
    message: str = "",
    reason_code: str | None = None,
    result_payload: dict[str, Any] | None = None,
) -> IdentificationJob:
    now = utc_now()
    job.status = status
    job.message = message
    job.reason_code = reason_code
    job.updated_at = now
    if status == "queued" and job.queued_at is None:
        job.queued_at = now
    if status == "running" and job.started_at is None:
        job.started_at = now
    if status in TERMINAL_STATUSES:
        job.finished_at = now
    if result_payload is not None:
        job.result_payload = result_payload
        job.summary = result_payload.get("summary")
        job.application_version = result_payload.get("application_version")
        job.algorithm_version = result_payload.get("algorithm_version")
    session.add(job)
    session.commit()
    session.refresh(job)
    return job

