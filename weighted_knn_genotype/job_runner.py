"""End-to-end PLINK job runner for new germplasm samples."""

from __future__ import annotations

import csv
import json
import math
import shutil
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

from . import ALGORITHM_VERSION, __version__
from .config import DEFAULT_UNKNOWN_LABELS, KNNConfig
from .evaluation import labels_for_matrix, predict_unknown_samples
from .ibs import load_ibs_distance_matrix, read_metadata
from .plink_dataset import (
    MarkerAlignment,
    align_markers,
    read_bim,
    read_fam,
    require_plink_prefix,
    write_id_pairs,
    write_marker_ids,
)
from .plink_runtime import (
    PlinkCommandError,
    PlinkRuntime,
    read_sample_missingness,
    run_bfile,
    run_merge,
)
from .reference import (
    load_reference_manifest,
    reference_file_path,
    sha256_file,
)


@dataclass(frozen=True)
class JobConfig:
    """Validation, PLINK, and KNN parameters for one job."""

    knn: KNNConfig = field(default_factory=KNNConfig)
    min_marker_overlap: float = 0.90
    max_sample_missingness: float = 0.20
    max_query_samples: int = 100
    plink_executable: str = "plink"
    autosome_count: int | None = None
    allow_extra_chr: bool = True

    def validate(self) -> None:
        self.knn.validate()
        if not 0 < self.min_marker_overlap <= 1:
            raise ValueError("min_marker_overlap must be in (0, 1]")
        if not 0 <= self.max_sample_missingness < 1:
            raise ValueError("max_sample_missingness must be in [0, 1)")
        if self.max_query_samples < 1:
            raise ValueError("max_query_samples must be at least 1")


class JobRejected(Exception):
    """An expected input or QC rejection."""

    def __init__(
        self,
        reason_code: str,
        message: str,
        details: Dict[str, object] | None = None,
    ):
        self.reason_code = reason_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_safe(value: Any) -> Any:
    """Convert pandas/NumPy values and non-finite floats to strict JSON."""

    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if pd.isna(value):
        return None
    return value


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_status(
    path: Path,
    job_id: str,
    status: str,
    *,
    created_at: str,
    message: str = "",
) -> None:
    write_json(
        path,
        {
            "job_id": job_id,
            "status": status,
            "message": message,
            "created_at": created_at,
            "updated_at": utc_now(),
        },
    )


def prepare_job_directory(job_dir: Path) -> dict[str, Path]:
    """Create an empty auditable job directory."""

    if job_dir.exists() and any(job_dir.iterdir()):
        raise ValueError(f"Job directory is not empty: {job_dir}")
    job_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "root": job_dir,
        "input": job_dir / "input",
        "work": job_dir / "work",
        "output": job_dir / "output",
        "logs": job_dir / "logs",
    }
    for key, path in paths.items():
        if key != "root":
            path.mkdir(parents=True, exist_ok=True)
    return paths


def copy_query_dataset(source_prefix: Path, destination_prefix: Path) -> None:
    require_plink_prefix(source_prefix)
    for suffix in (".bed", ".bim", ".fam"):
        shutil.copy2(
            Path(f"{source_prefix}{suffix}"),
            Path(f"{destination_prefix}{suffix}"),
        )


def reference_prefix_from_manifest(
    manifest_path: Path,
    manifest: Dict[str, object],
) -> Path:
    bed = reference_file_path(manifest_path, manifest, "bed")
    bim = reference_file_path(manifest_path, manifest, "bim")
    fam = reference_file_path(manifest_path, manifest, "fam")
    prefix = bed.with_suffix("")
    if Path(f"{prefix}.bim").resolve() != bim:
        raise ValueError("Reference BED and BIM paths do not share a prefix")
    if Path(f"{prefix}.fam").resolve() != fam:
        raise ValueError("Reference BED and FAM paths do not share a prefix")
    return prefix


def write_combined_metadata(
    path: Path,
    reference_samples: list,
    reference_metadata: pd.DataFrame,
    query_samples: list,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["ID", "POP"])
        for sample in reference_samples:
            writer.writerow([sample.iid, reference_metadata.loc[sample.iid, "LABEL"]])
        for sample in query_samples:
            writer.writerow([sample.iid, ""])


def merge_with_retry(
    reference_prefix: Path,
    query_prefix: Path,
    work_dir: Path,
    runtime: PlinkRuntime,
    log_path: Path,
    alignment: MarkerAlignment,
    min_marker_overlap: float,
) -> tuple[Path, list[str], int]:
    """Merge once, then exclude PLINK ``missnp`` markers and retry."""

    first_output = work_dir / "merged"
    result = run_merge(
        reference_prefix,
        query_prefix,
        first_output,
        runtime,
        log_path,
        check=False,
    )
    if result.returncode == 0:
        return first_output, [], alignment.compatible_marker_count

    missnp_candidates = [
        Path(f"{first_output}-merge.missnp"),
        Path(f"{first_output}.missnp"),
    ]
    missnp_path = next((path for path in missnp_candidates if path.is_file()), None)
    if missnp_path is None:
        raise PlinkCommandError(
            [runtime.executable, "--bfile", str(reference_prefix), "--bmerge"],
            result.returncode,
        )

    excluded = [line.strip() for line in missnp_path.read_text().splitlines() if line.strip()]
    excluded_set = set(excluded)
    final_marker_count = len(
        [marker for marker in alignment.compatible_ids if marker not in excluded_set]
    )
    final_overlap = final_marker_count / alignment.reference_marker_count
    if final_overlap < min_marker_overlap:
        raise JobRejected(
            "merge_marker_mismatch",
            "Too many markers were excluded after the PLINK merge failed",
            {
                "merge_excluded_marker_count": len(excluded),
                "final_marker_count": final_marker_count,
                "final_marker_overlap_ratio": final_overlap,
            },
        )

    reference_retry = work_dir / "reference_retry"
    query_retry = work_dir / "query_retry"
    run_bfile(
        reference_prefix,
        ["--exclude", str(missnp_path), "--make-bed"],
        reference_retry,
        runtime,
        log_path,
    )
    run_bfile(
        query_prefix,
        ["--exclude", str(missnp_path), "--make-bed"],
        query_retry,
        runtime,
        log_path,
    )
    merged_retry = work_dir / "merged_retry"
    run_merge(
        reference_retry,
        query_retry,
        merged_retry,
        runtime,
        log_path,
    )
    return merged_retry, excluded, final_marker_count


def run_identification_job(
    query_prefix: Path,
    job_dir: Path,
    reference_manifest: Path,
    config: JobConfig | None = None,
    *,
    job_id: str | None = None,
) -> Dict[str, object]:
    """Run validation, PLINK merging, IBS, and weighted KNN for new samples."""

    config = config or JobConfig()
    config.validate()
    job_id = job_id or job_dir.name
    created_at = utc_now()
    paths = prepare_job_directory(job_dir)
    status_path = paths["root"] / "status.json"
    result_path = paths["output"] / "result.json"
    qc_path = paths["output"] / "quality_control.json"
    log_path = paths["logs"] / "analysis.log"
    write_status(
        status_path,
        job_id,
        "validating",
        created_at=created_at,
        message="Validating query PLINK files",
    )

    qc: Dict[str, object] = {}
    algorithm_version = ALGORITHM_VERSION
    reference_version = "unknown"

    try:
        manifest = load_reference_manifest(reference_manifest, verify=True)
        reference_version = str(manifest["reference_version"])
        reference_prefix = reference_prefix_from_manifest(reference_manifest, manifest)
        metadata_path = reference_file_path(reference_manifest, manifest, "metadata")
        copied_query_prefix = paths["input"] / "query"
        copy_query_dataset(query_prefix, copied_query_prefix)

        input_files = {
            suffix.lstrip("."): {
                "path": f"input/query{suffix}",
                "sha256": sha256_file(Path(f"{copied_query_prefix}{suffix}")),
            }
            for suffix in (".bed", ".bim", ".fam")
        }

        query_samples = read_fam(Path(f"{copied_query_prefix}.fam"))
        if len(query_samples) > config.max_query_samples:
            raise JobRejected(
                "too_many_query_samples",
                f"Query contains {len(query_samples)} samples; "
                f"maximum is {config.max_query_samples}",
            )

        reference_samples_all = read_fam(Path(f"{reference_prefix}.fam"))
        reference_iids = {sample.iid for sample in reference_samples_all}
        overlapping_ids = sorted(
            {sample.iid for sample in query_samples}.intersection(reference_iids)
        )
        if overlapping_ids:
            raise JobRejected(
                "sample_id_conflict",
                "Query sample IDs already exist in the frozen reference genotype data",
                {"conflicting_sample_ids": overlapping_ids},
            )

        reference_metadata = read_metadata(metadata_path, "ID", "POP", "\t")
        known_reference_samples = [
            sample
            for sample in reference_samples_all
            if sample.iid in reference_metadata.index
            and str(reference_metadata.loc[sample.iid, "LABEL"])
            not in DEFAULT_UNKNOWN_LABELS
        ]
        expected_reference_count = int(
            manifest.get("samples", {}).get("labelled_reference_count", 0)
        )
        if expected_reference_count and len(known_reference_samples) != expected_reference_count:
            raise RuntimeError(
                "Reference labelled-sample count does not match manifest: "
                f"{len(known_reference_samples)} != {expected_reference_count}"
            )

        reference_markers = read_bim(Path(f"{reference_prefix}.bim"))
        query_markers = read_bim(Path(f"{copied_query_prefix}.bim"))
        alignment = align_markers(reference_markers, query_markers)
        qc.update(
            {
                "query_sample_count": len(query_samples),
                "reference_candidate_count": len(known_reference_samples),
                "marker_alignment": alignment.to_dict(),
            }
        )
        if alignment.overlap_ratio < config.min_marker_overlap:
            raise JobRejected(
                "insufficient_marker_overlap",
                "Query does not contain enough compatible panel-v1 markers",
                {
                    "required_marker_overlap_ratio": config.min_marker_overlap,
                    "actual_marker_overlap_ratio": alignment.overlap_ratio,
                    "compatible_marker_count": alignment.compatible_marker_count,
                    "reference_marker_count": alignment.reference_marker_count,
                },
            )

        autosome_count = config.autosome_count
        if autosome_count is None:
            autosome_count = int(manifest.get("plink", {}).get("autosome_count", 45))
        runtime = PlinkRuntime(
            executable=config.plink_executable,
            autosome_count=autosome_count,
            allow_extra_chr=config.allow_extra_chr,
        )

        marker_file = paths["work"] / "compatible_markers.txt"
        flip_file = paths["work"] / "strand_flip_markers.txt"
        reference_keep = paths["work"] / "reference.keep"
        write_marker_ids(marker_file, alignment.compatible_ids)
        write_marker_ids(flip_file, alignment.flip_ids)
        write_id_pairs(reference_keep, known_reference_samples)

        write_status(
            status_path,
            job_id,
            "running",
            created_at=created_at,
            message="Preparing and merging PLINK datasets",
        )
        reference_prepared = paths["work"] / "reference_prepared"
        query_prepared = paths["work"] / "query_prepared"
        run_bfile(
            reference_prefix,
            [
                "--keep",
                str(reference_keep),
                "--extract",
                str(marker_file),
                "--make-bed",
            ],
            reference_prepared,
            runtime,
            log_path,
        )
        query_arguments = ["--extract", str(marker_file)]
        if alignment.flip_ids:
            query_arguments.extend(["--flip", str(flip_file)])
        query_arguments.append("--make-bed")
        run_bfile(
            copied_query_prefix,
            query_arguments,
            query_prepared,
            runtime,
            log_path,
        )

        missing_prefix = paths["work"] / "query_missingness"
        run_bfile(
            query_prepared,
            ["--missing"],
            missing_prefix,
            runtime,
            log_path,
        )
        missingness = read_sample_missingness(Path(f"{missing_prefix}.imiss"))
        missing_iids = [sample.iid for sample in query_samples if sample.iid not in missingness]
        if missing_iids:
            raise RuntimeError(f"PLINK missingness output omitted samples: {missing_iids}")

        rejected_samples = [
            {
                "sample_id": sample.iid,
                "reason": "high_genotype_missingness",
                "missing_rate": missingness[sample.iid],
                "maximum_missing_rate": config.max_sample_missingness,
            }
            for sample in query_samples
            if missingness[sample.iid] > config.max_sample_missingness
        ]
        rejected_ids = {record["sample_id"] for record in rejected_samples}
        accepted_samples = [
            sample for sample in query_samples if sample.iid not in rejected_ids
        ]
        qc["sample_missingness"] = [
            {"sample_id": sample.iid, "missing_rate": missingness[sample.iid]}
            for sample in query_samples
        ]
        qc["accepted_sample_count"] = len(accepted_samples)
        qc["rejected_sample_count"] = len(rejected_samples)
        qc["rejected_samples"] = rejected_samples
        if not accepted_samples:
            raise JobRejected(
                "all_samples_failed_qc",
                "Every query sample exceeded the missing-genotype threshold",
                {"rejected_samples": rejected_samples},
            )

        query_for_merge = query_prepared
        if rejected_samples:
            accepted_keep = paths["work"] / "accepted_query.keep"
            write_id_pairs(accepted_keep, accepted_samples)
            query_for_merge = paths["work"] / "query_qc_pass"
            run_bfile(
                query_prepared,
                ["--keep", str(accepted_keep), "--make-bed"],
                query_for_merge,
                runtime,
                log_path,
            )

        merged_prefix, merge_excluded, final_marker_count = merge_with_retry(
            reference_prepared,
            query_for_merge,
            paths["work"],
            runtime,
            log_path,
            alignment,
            config.min_marker_overlap,
        )
        final_overlap = final_marker_count / alignment.reference_marker_count
        qc["merge_excluded_marker_count"] = len(merge_excluded)
        qc["merge_excluded_marker_ids"] = merge_excluded
        qc["final_marker_count"] = final_marker_count
        qc["final_marker_overlap_ratio"] = final_overlap

        combined_metadata = paths["work"] / "combined_metadata.tsv"
        write_combined_metadata(
            combined_metadata,
            known_reference_samples,
            reference_metadata,
            accepted_samples,
        )

        ibs_prefix = paths["work"] / "ibs"
        run_bfile(
            merged_prefix,
            ["--distance", "square", "ibs"],
            ibs_prefix,
            runtime,
            log_path,
        )
        distances, matrix_ids = load_ibs_distance_matrix(
            Path(f"{ibs_prefix}.mibs"),
            Path(f"{ibs_prefix}.mibs.id"),
            ids_column=1,
        )
        combined_labels = read_metadata(combined_metadata, "ID", "POP", "\t")
        labels = labels_for_matrix(matrix_ids, combined_labels)
        assignments = predict_unknown_samples(
            matrix_ids,
            distances,
            labels,
            config.knn,
            reference_version=reference_version,
            algorithm_version=algorithm_version,
        )
        expected_query_ids = {sample.iid for sample in accepted_samples}
        actual_query_ids = set(assignments.get("ID", pd.Series(dtype=str)).astype(str))
        if actual_query_ids != expected_query_ids:
            raise RuntimeError(
                "KNN output sample IDs do not match accepted query samples: "
                f"expected={sorted(expected_query_ids)}, actual={sorted(actual_query_ids)}"
            )

        assignments["matched_marker_count"] = final_marker_count
        assignments["marker_overlap_ratio"] = final_overlap
        assignments["sample_missing_rate"] = assignments["ID"].map(missingness)
        assignments_path = paths["output"] / "knn_assignments.csv"
        assignments.to_csv(assignments_path, index=False)
        write_json(qc_path, qc)

        assignment_records = json_safe(assignments.to_dict(orient="records"))
        completed_at = utc_now()
        result: Dict[str, object] = {
            "schema_version": 1,
            "job_id": job_id,
            "status": "completed",
            "created_at": created_at,
            "completed_at": completed_at,
            "reference_version": reference_version,
            "application_version": __version__,
            "algorithm_version": algorithm_version,
            "parameters": {
                "k": config.knn.k,
                "min_known_neighbors": config.knn.min_known_neighbors,
                "epsilon": config.knn.epsilon,
                "weight_power": config.knn.weight_power,
                "min_marker_overlap": config.min_marker_overlap,
                "max_sample_missingness": config.max_sample_missingness,
            },
            "input_files": input_files,
            "summary": {
                "submitted_samples": len(query_samples),
                "accepted_samples": len(accepted_samples),
                "rejected_samples": len(rejected_samples),
                "assigned_samples": len(assignments),
                "final_marker_count": final_marker_count,
                "final_marker_overlap_ratio": final_overlap,
            },
            "rejected_samples": rejected_samples,
            "assignments": assignment_records,
            "files": {
                "assignments_csv": "output/knn_assignments.csv",
                "quality_control_json": "output/quality_control.json",
                "analysis_log": "logs/analysis.log",
            },
        }
        write_json(result_path, result)
        write_status(
            status_path,
            job_id,
            "completed",
            created_at=created_at,
            message=f"Assigned {len(assignments)} query samples",
        )
        return result

    except JobRejected as error:
        qc.update(error.details)
        write_json(qc_path, qc)
        result = {
            "schema_version": 1,
            "job_id": job_id,
            "status": "rejected",
            "created_at": created_at,
            "completed_at": utc_now(),
            "reference_version": reference_version,
            "application_version": __version__,
            "algorithm_version": algorithm_version,
            "reason_code": error.reason_code,
            "message": error.message,
            "details": error.details,
        }
        write_json(result_path, result)
        write_status(
            status_path,
            job_id,
            "rejected",
            created_at=created_at,
            message=error.message,
        )
        return result
    except Exception as error:
        with log_path.open("a", encoding="utf-8") as log:
            log.write("\nUNEXPECTED ERROR\n")
            log.write(traceback.format_exc())
        result = {
            "schema_version": 1,
            "job_id": job_id,
            "status": "failed",
            "created_at": created_at,
            "completed_at": utc_now(),
            "reference_version": reference_version,
            "application_version": __version__,
            "algorithm_version": algorithm_version,
            "message": str(error),
        }
        write_json(result_path, result)
        write_status(
            status_path,
            job_id,
            "failed",
            created_at=created_at,
            message=str(error),
        )
        raise
