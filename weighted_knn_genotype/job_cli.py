"""Command-line interface for end-to-end identification jobs."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .config import KNNConfig
from .job_runner import JobConfig, run_identification_job


def default_reference_manifest() -> Path:
    reference_root = Path(
        os.environ.get("SHRIMP_REFERENCE_DIR", "reference-data/panel-v1")
    )
    return reference_root / "manifest.json"


def generate_job_id() -> str:
    date = datetime.now().strftime("%Y%m%d")
    return f"JOB-{date}-{uuid.uuid4().hex[:8]}"


def parse_job_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="weighted-knn-genotype run-job",
        description="Validate, merge, and identify new PLINK samples.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--query-prefix",
        type=Path,
        help="PLINK query prefix containing .bed/.bim/.fam.",
    )
    source.add_argument(
        "--input-dir",
        type=Path,
        help="Directory containing query.bed/query.bim/query.fam.",
    )
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--job-dir", type=Path)
    destination.add_argument("--jobs-root", type=Path, default=Path("jobs"))
    parser.add_argument("--job-id")
    parser.add_argument(
        "--reference-manifest",
        type=Path,
        default=default_reference_manifest(),
    )
    parser.add_argument("--min-marker-overlap", type=float, default=0.90)
    parser.add_argument("--max-sample-missingness", type=float, default=0.20)
    parser.add_argument("--max-query-samples", type=int, default=100)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--min-known-neighbors", type=int, default=3)
    parser.add_argument("--epsilon", type=float, default=1e-6)
    parser.add_argument("--weight-power", type=float, default=1.0)
    parser.add_argument("--plink-executable", default="plink")
    parser.add_argument("--autosome-count", type=int, default=None)
    parser.add_argument("--no-allow-extra-chr", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    try:
        args = parse_job_args(argv)
        job_id = args.job_id or generate_job_id()
        query_prefix = args.query_prefix or (args.input_dir / "query")
        job_dir = args.job_dir or (args.jobs_root / job_id)
        config = JobConfig(
            knn=KNNConfig(
                k=args.k,
                min_known_neighbors=args.min_known_neighbors,
                epsilon=args.epsilon,
                weight_power=args.weight_power,
            ),
            min_marker_overlap=args.min_marker_overlap,
            max_sample_missingness=args.max_sample_missingness,
            max_query_samples=args.max_query_samples,
            plink_executable=args.plink_executable,
            autosome_count=args.autosome_count,
            allow_extra_chr=not args.no_allow_extra_chr,
        )
        result = run_identification_job(
            query_prefix,
            job_dir,
            args.reference_manifest,
            config,
            job_id=job_id,
        )
        print(f"Job directory: {job_dir.resolve()}")
        print(f"Job status: {result['status']}")
        if result["status"] == "completed":
            print(
                f"Assigned samples: {result['summary']['assigned_samples']}; "
                f"reference: {result['reference_version']}"
            )
            raise SystemExit(0)
        print(f"Reason: {result.get('reason_code', 'unknown')}", file=sys.stderr)
        raise SystemExit(3)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
