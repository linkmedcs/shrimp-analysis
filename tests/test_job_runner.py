from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from weighted_knn_genotype.job_runner import JobConfig, run_identification_job
from weighted_knn_genotype.plink_dataset import BimMarker, align_markers


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
REFERENCE_MANIFEST = ROOT / "reference-data" / "panel-v1" / "manifest.json"


class MarkerAlignmentTests(unittest.TestCase):
    def test_exact_complement_and_mismatch_markers(self) -> None:
        reference = [
            BimMarker("1", "exact", "0", 10, "A", "G"),
            BimMarker("1", "flip", "0", 20, "A", "C"),
            BimMarker("1", "bad", "0", 30, "A", "G"),
            BimMarker("1", "missing", "0", 40, "C", "T"),
        ]
        query = [
            BimMarker("1", "exact", "0", 10, "G", "A"),
            BimMarker("1", "flip", "0", 20, "T", "G"),
            BimMarker("1", "bad", "0", 30, "A", "C"),
            BimMarker("1", "extra", "0", 50, "A", "G"),
        ]
        alignment = align_markers(reference, query)
        self.assertEqual(alignment.compatible_ids, ("exact", "flip"))
        self.assertEqual(alignment.flip_ids, ("flip",))
        self.assertEqual(alignment.allele_mismatch_ids, ("bad",))
        self.assertEqual(alignment.missing_query_ids, ("missing",))
        self.assertEqual(alignment.extra_query_ids, ("extra",))
        self.assertEqual(alignment.overlap_ratio, 0.5)


class JobRunnerTests(unittest.TestCase):
    def test_query_id_conflict_is_rejected_before_plink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            query = root / "query"
            Path(f"{query}.bed").write_bytes(b"not-a-real-bed")
            Path(f"{query}.bim").write_text(
                "1\t1:11687793\t0\t11687793\tA\tG\n",
                encoding="utf-8",
            )
            Path(f"{query}.fam").write_text(
                "23GT-N-2 23GT-N-2 0 0 0 -9\n",
                encoding="utf-8",
            )
            result = run_identification_job(
                query,
                root / "job",
                REFERENCE_MANIFEST,
                job_id="JOB-ID-CONFLICT",
            )
            self.assertEqual(result["status"], "rejected")
            self.assertEqual(result["reason_code"], "sample_id_conflict")

    def test_insufficient_marker_overlap_is_rejected_before_plink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            query = root / "query"
            Path(f"{query}.bed").write_bytes(b"not-a-real-bed")
            Path(f"{query}.bim").write_text(
                "1\t1:11687793\t0\t11687793\tA\tG\n",
                encoding="utf-8",
            )
            Path(f"{query}.fam").write_text(
                "QUERY QUERY 0 0 0 -9\n",
                encoding="utf-8",
            )
            result = run_identification_job(
                query,
                root / "job",
                REFERENCE_MANIFEST,
                JobConfig(min_marker_overlap=0.90),
                job_id="JOB-LOW-OVERLAP",
            )
            self.assertEqual(result["status"], "rejected")
            self.assertEqual(result["reason_code"], "insufficient_marker_overlap")

    @unittest.skipUnless(shutil.which("plink"), "PLINK 1.9 is not installed")
    def test_holdout_query_end_to_end(self) -> None:
        expected = json.loads(
            (FIXTURES / "holdout_query.expected.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temporary:
            result = run_identification_job(
                FIXTURES / "holdout_query",
                Path(temporary) / "job",
                REFERENCE_MANIFEST,
                JobConfig(plink_executable=shutil.which("plink") or "plink"),
                job_id="JOB-HOLDOUT-TEST",
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["application_version"], "0.3.0")
            self.assertEqual(result["algorithm_version"], "weighted-knn-0.1.0")
            predictions = {
                row["ID"]: row["predicted_label"] for row in result["assignments"]
            }
            self.assertEqual(predictions, expected)
            self.assertEqual(result["summary"]["final_marker_count"], 503)
            self.assertEqual(result["summary"]["assigned_samples"], 3)


if __name__ == "__main__":
    unittest.main()
