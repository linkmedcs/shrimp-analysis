"""RQ task that delegates all scientific work to the Stage 3 Job Runner."""

from __future__ import annotations

import json
from pathlib import Path

from .config import get_settings
from .database import get_session_factory
from .repository import TERMINAL_STATUSES, get_job, set_job_status
from weighted_knn_genotype.job_runner import run_identification_job


def _read_failed_result(job_dir: Path) -> dict | None:
    result_path = job_dir / "output" / "result.json"
    if not result_path.is_file():
        return None
    return json.loads(result_path.read_text(encoding="utf-8"))


def run_identification_task(job_id: str) -> dict:
    settings = get_settings()
    session_factory = get_session_factory()

    with session_factory() as session:
        job = get_job(session, job_id)
        if job is None:
            raise LookupError(f"Identification job does not exist: {job_id}")
        if job.status in TERMINAL_STATUSES and job.result_payload is not None:
            return job.result_payload
        set_job_status(
            session,
            job,
            "running",
            message="Running PLINK quality control and weighted KNN",
        )
        input_mode = (job.input_files or {}).get("mode", "plink")
        if input_mode == "vcf":
            input_records = (job.input_files or {}).get("files", {})
            vcf_name = input_records.get("vcf", {}).get("stored_name", "query.vcf")
            query_vcf = Path(job.upload_dir) / vcf_name
            query_prefix = None
        else:
            query_prefix = Path(job.upload_dir) / "query"
            query_vcf = None
        job_dir = Path(job.job_dir)

    try:
        result = run_identification_job(
            query_prefix,
            job_dir,
            settings.reference_manifest,
            query_vcf=query_vcf,
            job_id=job_id,
        )
    except Exception as error:
        failed_result = _read_failed_result(job_dir)
        with session_factory() as session:
            job = get_job(session, job_id)
            if job is not None:
                set_job_status(
                    session,
                    job,
                    "failed",
                    message=str(error),
                    reason_code="unexpected_error",
                    result_payload=failed_result,
                )
        raise

    with session_factory() as session:
        job = get_job(session, job_id)
        if job is None:
            raise LookupError(f"Identification job disappeared: {job_id}")
        set_job_status(
            session,
            job,
            str(result["status"]),
            message=str(result.get("message", "Identification finished")),
            reason_code=result.get("reason_code"),
            result_payload=result,
        )
    return result
