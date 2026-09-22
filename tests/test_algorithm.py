from __future__ import annotations

import csv
import unittest
from pathlib import Path

from weighted_knn_genotype.config import KNNConfig
from weighted_knn_genotype.evaluation import (
    labels_for_matrix,
    leave_one_out,
    predict_unknown_samples,
)
from weighted_knn_genotype.ibs import (
    build_plink19_ibs_command,
    load_ibs_distance_matrix,
    read_metadata,
)
from weighted_knn_genotype.reference import load_reference_manifest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class WeightedKNNTests(unittest.TestCase):
    def setUp(self) -> None:
        self.distances, self.ids = load_ibs_distance_matrix(
            FIXTURES / "tiny.mibs",
            FIXTURES / "tiny.mibs.id",
        )
        metadata = read_metadata(
            FIXTURES / "tiny_metadata.tsv",
            "ID",
            "POP",
        )
        self.labels = labels_for_matrix(self.ids, metadata)

    def test_unknown_queries_do_not_occupy_neighbor_slots(self) -> None:
        config = KNNConfig(k=2, min_known_neighbors=2)
        assignments = predict_unknown_samples(
            self.ids,
            self.distances,
            self.labels,
            config,
            reference_version="test-v1",
        )
        self.assertEqual(assignments["ID"].tolist(), ["U1", "U2"])
        self.assertEqual(assignments["predicted_label"].tolist(), ["Alpha", "Alpha"])
        self.assertEqual(assignments["known_neighbor_count"].tolist(), [2, 2])
        self.assertEqual(assignments["reference_candidate_count"].tolist(), [4, 4])

    def test_leave_one_out_excludes_the_target(self) -> None:
        config = KNNConfig(k=1, min_known_neighbors=1)
        evaluation, summary = leave_one_out(
            self.ids,
            self.distances,
            self.labels,
            config,
            reference_version="test-v1",
        )
        self.assertEqual(len(evaluation), 4)
        self.assertTrue(evaluation["correct"].all())
        self.assertEqual(float(summary.loc[0, "accuracy_on_predicted"]), 1.0)

    def test_reference_manifest_checksums(self) -> None:
        manifest = load_reference_manifest(
            ROOT / "reference-data" / "panel-v1" / "manifest.json"
        )
        self.assertEqual(manifest["reference_version"], "panel-v1")
        self.assertEqual(manifest["lifecycle_status"], "frozen")
        self.assertEqual(manifest["panel"]["marker_policy"], "all_current_markers")
        self.assertEqual(manifest["panel"]["marker_count"], 503)
        self.assertTrue(
            all(".." not in file_info["path"] for file_info in manifest["files"])
        )

    def test_frozen_metadata_is_strict_two_column_tsv(self) -> None:
        metadata_path = (
            ROOT / "reference-data" / "panel-v1" / "metadata" / "labels.tsv"
        )
        with metadata_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle, delimiter="\t"))
        self.assertEqual(rows[0], ["ID", "POP"])
        self.assertTrue(all(len(row) == 2 for row in rows))
        sample_ids = [row[0] for row in rows[1:]]
        self.assertEqual(len(sample_ids), len(set(sample_ids)))

    def test_dockerfile_pins_portable_runtime(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("debian:13.5-slim@sha256:", dockerfile)
        self.assertIn("plink1.9=1.90~b7.7-241022-2", dockerfile)
        self.assertIn("python3-numpy=1:2.2.4+ds-1", dockerfile)
        self.assertIn("python3-pandas=2.2.3+dfsg-9", dockerfile)
        self.assertIn("USER app", dockerfile)

    def test_plink19_command_uses_distance_ibs(self) -> None:
        command = build_plink19_ibs_command(
            Path("reference"),
            Path("output/plink"),
            autosome_count=45,
        )
        self.assertIn("--distance", command)
        distance_index = command.index("--distance")
        self.assertEqual(
            command[distance_index + 1 : distance_index + 3],
            ["square", "ibs"],
        )
        self.assertIn("--chr-set", command)
        self.assertIn("--allow-extra-chr", command)


if __name__ == "__main__":
    unittest.main()
