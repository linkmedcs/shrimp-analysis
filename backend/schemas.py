"""Public API response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    message: str
    reason_code: str | None
    reference_version: str
    application_version: str | None
    algorithm_version: str | None
    summary: dict[str, Any] | None
    input_files: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


class FileResponse(BaseModel):
    key: str
    name: str
    size_bytes: int
    download_url: str


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
