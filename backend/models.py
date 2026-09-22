"""Persistent task records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IdentificationJob(Base):
    __tablename__ = "identification_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(80))
    reference_version: Mapped[str] = mapped_column(String(80), nullable=False)
    application_version: Mapped[str | None] = mapped_column(String(40))
    algorithm_version: Mapped[str | None] = mapped_column(String(80))
    rq_job_id: Mapped[str | None] = mapped_column(String(100), unique=True)

    job_dir: Mapped[str] = mapped_column(Text, nullable=False)
    upload_dir: Mapped[str] = mapped_column(Text, nullable=False)
    input_files: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

