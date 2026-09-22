"""HTTP endpoints for identification task lifecycle management."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse as DownloadResponse
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import Settings, get_settings
from backend.database import get_db
from backend.models import IdentificationJob
from backend.queue import enqueue_identification, get_redis_connection
from backend.repository import get_job, set_job_status
from backend.schemas import FileResponse, HealthResponse, JobResponse


router = APIRouter(prefix="/api")

FILE_MAP = {
    "result": "output/result.json",
    "quality_control": "output/quality_control.json",
    "assignments": "output/knn_assignments.csv",
    "analysis_log": "logs/analysis.log",
}


def generate_job_id() -> str:
    return f"JOB-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:10]}"


def load_reference_summary(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "reference_version": manifest["reference_version"],
        "lifecycle_status": manifest["lifecycle_status"],
        "species": manifest["species"],
        "panel": manifest["panel"],
        "samples": manifest["samples"],
        "algorithm_defaults": manifest["algorithm_defaults"],
    }


async def save_upload(
    upload: UploadFile,
    destination: Path,
    maximum_bytes: int,
) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with destination.open("xb") as handle:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > maximum_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"{upload.filename or destination.name} exceeds "
                            f"the {maximum_bytes}-byte upload limit"
                        ),
                    )
                handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    if total == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{upload.filename or destination.name} is empty",
        )
    return {
        "original_name": upload.filename,
        "stored_name": destination.name,
        "size_bytes": total,
    }


def require_job(session: Session, job_id: str) -> IdentificationJob:
    job = get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Identification job not found")
    return job


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job(
    bed: UploadFile = File(...),
    bim: UploadFile = File(...),
    fam: UploadFile = File(...),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IdentificationJob:
    job_id = generate_job_id()
    upload_dir = (settings.uploads_root / job_id).resolve()
    job_dir = (settings.jobs_root / job_id).resolve()
    upload_dir.mkdir(parents=True, exist_ok=False)
    settings.jobs_root.mkdir(parents=True, exist_ok=True)

    try:
        input_files = {
            "bed": await save_upload(
                bed,
                upload_dir / "query.bed",
                settings.max_upload_bytes_per_file,
            ),
            "bim": await save_upload(
                bim,
                upload_dir / "query.bim",
                settings.max_upload_bytes_per_file,
            ),
            "fam": await save_upload(
                fam,
                upload_dir / "query.fam",
                settings.max_upload_bytes_per_file,
            ),
        }
        reference = load_reference_summary(settings.reference_manifest)
        job = IdentificationJob(
            id=job_id,
            status="queued",
            message="Waiting for an identification worker",
            reference_version=reference["reference_version"],
            job_dir=str(job_dir),
            upload_dir=str(upload_dir),
            input_files=input_files,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        try:
            rq_job = enqueue_identification(job_id)
        except Exception as error:
            set_job_status(
                session,
                job,
                "failed",
                message=f"Unable to enqueue job: {error}",
                reason_code="queue_unavailable",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"job_id": job_id, "message": "Task queue is unavailable"},
            ) from error

        job.rq_job_id = rq_job.id
        job.queued_at = job.created_at
        session.add(job)
        session.commit()
        session.refresh(job)
        return job
    except HTTPException:
        if get_job(session, job_id) is None:
            shutil.rmtree(upload_dir, ignore_errors=True)
        raise
    except Exception:
        session.rollback()
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise


@router.get("/jobs/{job_id}", response_model=JobResponse)
def read_job(job_id: str, session: Session = Depends(get_db)) -> IdentificationJob:
    return require_job(session, job_id)


@router.get("/jobs/{job_id}/result")
def read_job_result(job_id: str, session: Session = Depends(get_db)):
    job = require_job(session, job_id)
    if job.result_payload is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"job_id": job_id, "status": job.status},
        )
    return JSONResponse(content=job.result_payload)


@router.get("/jobs/{job_id}/files", response_model=list[FileResponse])
def list_job_files(
    job_id: str,
    session: Session = Depends(get_db),
) -> list[FileResponse]:
    job = require_job(session, job_id)
    job_root = Path(job.job_dir)
    files = []
    for key, relative_path in FILE_MAP.items():
        path = job_root / relative_path
        if path.is_file():
            files.append(
                FileResponse(
                    key=key,
                    name=path.name,
                    size_bytes=path.stat().st_size,
                    download_url=f"/api/jobs/{job_id}/files/{key}",
                )
            )
    return files


@router.get("/jobs/{job_id}/files/{file_key}")
def download_job_file(
    job_id: str,
    file_key: str,
    session: Session = Depends(get_db),
):
    job = require_job(session, job_id)
    relative_path = FILE_MAP.get(file_key)
    if relative_path is None:
        raise HTTPException(status_code=404, detail="Unknown output file")
    path = Path(job.job_dir) / relative_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Output file is not available")
    return DownloadResponse(path=path, filename=path.name)


@router.get("/reference-panels")
def list_reference_panels(settings: Settings = Depends(get_settings)) -> list[dict]:
    try:
        return [load_reference_summary(settings.reference_manifest)]
    except (OSError, KeyError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Reference manifest is unavailable: {error}",
        ) from error


@router.get("/health", response_model=HealthResponse)
def health(
    session: Session = Depends(get_db),
    redis: Redis = Depends(get_redis_connection),
):
    database_status = "ok"
    redis_status = "ok"
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"
    try:
        redis.ping()
    except Exception:
        redis_status = "error"
    payload = HealthResponse(
        status="ok" if database_status == redis_status == "ok" else "degraded",
        database=database_status,
        redis=redis_status,
    )
    if payload.status != "ok":
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload
