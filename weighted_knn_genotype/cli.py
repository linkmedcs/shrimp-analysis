"""Command-line entry point for weighted KNN identification."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import ALGORITHM_VERSION
from .config import DEFAULT_UNKNOWN_LABELS, KNNConfig
from .evaluation import labels_for_matrix, leave_one_out, predict_unknown_samples
from .ibs import generate_plink19_ibs, load_ibs_distance_matrix, read_metadata
from .reference import load_reference_manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assign shrimp samples with IBS distance-weighted KNN.",
        epilog="For a complete new-sample workflow, use: "
        "weighted-knn-genotype run-job --help",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ibs-matrix", type=Path, help="Existing PLINK .mibs file.")
    source.add_argument(
        "--plink-prefix",
        type=Path,
        help="PLINK .bed/.bim/.fam prefix; PLINK 1.9 is required.",
    )
    parser.add_argument("--ids", type=Path, help="PLINK .mibs.id file.")
    parser.add_argument("--ids-column", type=int, default=0)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--id-column", default="ID")
    parser.add_argument("--label-column", default="POP")
    parser.add_argument("--metadata-sep", default=None)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--min-known-neighbors", type=int, default=3)
    parser.add_argument("--epsilon", type=float, default=1e-6)
    parser.add_argument("--weight-power", type=float, default=1.0)
    parser.add_argument("--unknown-label", action="append", dest="unknown_labels")
    parser.add_argument("--loo", action="store_true")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("weighted_knn_results")
    )
    parser.add_argument("--plink-executable", default="plink")
    parser.add_argument(
        "--autosome-count",
        type=int,
        default=None,
        help="Non-human autosome count passed to PLINK --chr-set.",
    )
    parser.add_argument("--no-allow-extra-chr", action="store_true")
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument("--skip-reference-verification", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    unknown_labels = set(DEFAULT_UNKNOWN_LABELS)
    unknown_labels.update(args.unknown_labels or ())
    config = KNNConfig(
        k=args.k,
        min_known_neighbors=args.min_known_neighbors,
        epsilon=args.epsilon,
        weight_power=args.weight_power,
        unknown_labels=frozenset(unknown_labels),
    )
    config.validate()
    if args.ids_column < 0:
        raise ValueError("--ids-column cannot be negative")

    reference_version = "unversioned"
    if args.reference_manifest:
        manifest = load_reference_manifest(
            args.reference_manifest,
            verify=not args.skip_reference_verification,
        )
        reference_version = str(manifest["reference_version"])
    algorithm_version = ALGORITHM_VERSION
    metadata = read_metadata(
        args.metadata,
        args.id_column,
        args.label_column,
        args.metadata_sep,
    )

    temporary_directory = None
    try:
        if args.ibs_matrix:
            if args.ids is None:
                raise ValueError("--ids is required with --ibs-matrix")
            matrix_path, ids_path = args.ibs_matrix, args.ids
        else:
            temporary_directory = tempfile.TemporaryDirectory(prefix="shrimp_knn_")
            output_prefix = Path(temporary_directory.name) / "plink"
            matrix_path, ids_path = generate_plink19_ibs(
                args.plink_prefix,
                output_prefix,
                executable=args.plink_executable,
                autosome_count=args.autosome_count,
                allow_extra_chr=not args.no_allow_extra_chr,
            )

        distances, matrix_ids = load_ibs_distance_matrix(
            matrix_path, ids_path, ids_column=args.ids_column
        )
        missing_metadata = [
            sample_id for sample_id in matrix_ids if sample_id not in metadata.index
        ]
        if missing_metadata:
            print(
                f"Warning: {len(missing_metadata)} matrix samples have no metadata row; "
                "they are treated as unknown queries.",
                file=sys.stderr,
            )

        labels = labels_for_matrix(matrix_ids, metadata)
        assignments = predict_unknown_samples(
            matrix_ids,
            distances,
            labels,
            config,
            reference_version=reference_version,
            algorithm_version=algorithm_version,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        assignments.to_csv(args.output_dir / "knn_assignments.csv", index=False)

        if args.loo:
            evaluation, summary = leave_one_out(
                matrix_ids,
                distances,
                labels,
                config,
                reference_version=reference_version,
                algorithm_version=algorithm_version,
            )
            evaluation.to_csv(args.output_dir / "loo_evaluation.csv", index=False)
            summary.to_csv(args.output_dir / "loo_summary.csv", index=False)

        print(f"Wrote results to: {args.output_dir.resolve()}")
        print(
            f"Samples: {len(matrix_ids)}; unknown assignments: {len(assignments)}; "
            f"reference version: {reference_version}"
        )
        return 0
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "run-job":
        from .job_cli import main as job_main

        job_main(sys.argv[2:])
        return
    try:
        raise SystemExit(run(parse_args(sys.argv[1:])))
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
