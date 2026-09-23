from __future__ import annotations

import os
import asyncio
from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import Settings, get_settings
from backend.api.routes import create_job, read_job
from backend.database import Base, get_db, reset_database_caches
from backend.main import create_app
from backend.models import IdentificationJob
from backend.tasks import run_identification_task


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_MANIFEST = ROOT / "reference-data" / "panel-v1" / "manifest.json"


class BackendApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.settings = Settings(
            database_url="sqlite+pysqlite:///:memory:",
            redis_url="redis://unused:6379/0",
            jobs_root=self.root / "jobs",
            uploads_root=self.root / "uploads",
            reference_manifest=REFERENCE_MANIFEST,
        )
        self.engine = create_engine(
            self.settings.database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        self.app = create_app()
        self.session = self.session_factory()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.temporary.cleanup()

    @patch("backend.api.routes.enqueue_identification")
    def test_create_and_read_queued_job(self, enqueue) -> None:
        enqueue.return_value = SimpleNamespace(id="rq-test")
        job = asyncio.run(
            create_job(
                bed=UploadFile(filename="sample.bed", file=BytesIO(b"bed")),
                bim=UploadFile(
                    filename="sample.bim",
                    file=BytesIO(b"1\trs1\t0\t1\tA\tG\n"),
                ),
                fam=UploadFile(
                    filename="sample.fam",
                    file=BytesIO(b"F Q1 0 0 0 -9\n"),
                ),
                vcf=None,
                session=self.session,
                settings=self.settings,
            )
        )
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.reference_version, "panel-v1")
        stored = read_job(job.id, self.session)
        self.assertEqual(stored.id, job.id)
        self.assertTrue(
            (self.settings.uploads_root / job.id / "query.bed").is_file()
        )
        route_paths = set(self.app.openapi()["paths"])
        self.assertIn("/api/jobs", route_paths)
        self.assertIn("/api/jobs/{job_id}/result", route_paths)

    @patch("backend.api.routes.enqueue_identification")
    def test_create_vcf_job(self, enqueue) -> None:
        enqueue.return_value = SimpleNamespace(id="rq-vcf-test")
        job = asyncio.run(
            create_job(
                bed=None,
                bim=None,
                fam=None,
                vcf=UploadFile(filename="query.vcf.gz", file=BytesIO(b"vcf")),
                session=self.session,
                settings=self.settings,
            )
        )
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.input_files["mode"], "vcf")
        self.assertEqual(job.input_files["files"]["vcf"]["stored_name"], "query.vcf.gz")
        self.assertTrue(
            (self.settings.uploads_root / job.id / "query.vcf.gz").is_file()
        )


class BackendWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database_path = self.root / "worker.sqlite"
        os.environ["SHRIMP_DATABASE_URL"] = (
            f"sqlite+pysqlite:///{self.database_path}"
        )
        os.environ["SHRIMP_JOBS_ROOT"] = str(self.root / "jobs")
        os.environ["SHRIMP_UPLOADS_ROOT"] = str(self.root / "uploads")
        os.environ["SHRIMP_REFERENCE_MANIFEST"] = str(REFERENCE_MANIFEST)
        get_settings.cache_clear()
        reset_database_caches()

        engine = create_engine(os.environ["SHRIMP_DATABASE_URL"])
        Base.metadata.create_all(engine)
        upload_dir = self.root / "uploads" / "JOB-WORKER-TEST"
        upload_dir.mkdir(parents=True)
        for suffix in ("bed", "bim", "fam"):
            (upload_dir / f"query.{suffix}").write_text(suffix, encoding="utf-8")
        with Session(engine) as session:
            session.add(
                IdentificationJob(
                    id="JOB-WORKER-TEST",
                    status="queued",
                    message="queued",
                    reference_version="panel-v1",
                    job_dir=str(self.root / "jobs" / "JOB-WORKER-TEST"),
                    upload_dir=str(upload_dir),
                    input_files={},
                )
            )
            session.commit()
        engine.dispose()

    def tearDown(self) -> None:
        reset_database_caches()
        get_settings.cache_clear()
        for key in (
            "SHRIMP_DATABASE_URL",
            "SHRIMP_JOBS_ROOT",
            "SHRIMP_UPLOADS_ROOT",
            "SHRIMP_REFERENCE_MANIFEST",
        ):
            os.environ.pop(key, None)
        self.temporary.cleanup()

    @patch("backend.tasks.run_identification_job")
    def test_worker_persists_completed_result(self, run_job) -> None:
        run_job.return_value = {
            "job_id": "JOB-WORKER-TEST",
            "status": "completed",
            "reference_version": "panel-v1",
            "application_version": "0.3.0",
            "algorithm_version": "weighted-knn-0.1.0",
            "summary": {"assigned_samples": 1},
            "assignments": [{"ID": "Q1", "predicted_label": "GT"}],
        }
        result = run_identification_task("JOB-WORKER-TEST")
        self.assertEqual(result["status"], "completed")

        engine = create_engine(os.environ["SHRIMP_DATABASE_URL"])
        with Session(engine) as session:
            job = session.get(IdentificationJob, "JOB-WORKER-TEST")
            self.assertIsNotNone(job)
            self.assertEqual(job.status, "completed")
            self.assertEqual(job.summary["assigned_samples"], 1)
            self.assertEqual(job.application_version, "0.3.0")
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
