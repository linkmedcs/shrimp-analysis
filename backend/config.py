"""Environment-backed configuration for the API and worker."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings shared by the API, migration and worker processes."""

    model_config = SettingsConfigDict(
        env_prefix="SHRIMP_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://shrimp:shrimp@postgres:5432/shrimp"
    )
    redis_url: str = "redis://redis:6379/0"
    queue_name: str = "identification"
    jobs_root: Path = Path("/data/jobs")
    uploads_root: Path = Path("/data/uploads")
    reference_manifest: Path = Path(
        "/app/reference-data/panel-v1/manifest.json"
    )
    max_upload_bytes_per_file: int = 100 * 1024 * 1024
    job_timeout_seconds: int = 60 * 60
    result_ttl_seconds: int = 7 * 24 * 60 * 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

