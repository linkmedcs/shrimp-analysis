"""Input/output helpers for PLINK IBS matrices and sample metadata."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


def read_ids(path: Path, column: int = 0) -> List[str]:
    """Read one zero-based column from a whitespace-delimited PLINK ID file."""

    if not path.exists():
        raise FileNotFoundError(f"IDs file not found: {path}")
    ids: List[str] = []
    with path.open() as handle:
        for line_number, line in enumerate(handle, start=1):
            fields = line.strip().split()
            if not fields:
                continue
            if column >= len(fields):
                raise ValueError(
                    f"IDs file {path} line {line_number} has no column {column}"
                )
            ids.append(fields[column])
    if not ids:
        raise ValueError(f"No sample IDs found in {path}")
    return ids


def read_metadata(
    path: Path,
    id_column: str,
    label_column: str,
    separator: Optional[str] = None,
) -> pd.DataFrame:
    """Read metadata and return a two-column frame indexed by sample ID."""

    if not path.exists():
        raise FileNotFoundError(f"Metadata file not found: {path}")
    if separator is None:
        metadata = pd.read_csv(path, sep=r"\s+|,", engine="python", dtype=str)
    else:
        metadata = pd.read_csv(path, sep=separator, dtype=str)

    metadata.columns = [str(column).strip() for column in metadata.columns]
    if id_column not in metadata.columns or label_column not in metadata.columns:
        raise ValueError(
            f"Metadata must contain {id_column!r} and {label_column!r}; "
            f"found columns: {list(metadata.columns)!r}"
        )

    metadata = metadata[[id_column, label_column]].copy()
    metadata.columns = ["ID", "LABEL"]
    metadata["ID"] = metadata["ID"].astype(str).str.strip()
    metadata["LABEL"] = metadata["LABEL"].fillna("").astype(str).str.strip()
    metadata = metadata[metadata["ID"] != ""].drop_duplicates("ID", keep="last")
    if metadata.empty:
        raise ValueError(f"No usable sample records found in {path}")
    return metadata.set_index("ID")


def load_ibs_distance_matrix(
    matrix_path: Path,
    ids_path: Path,
    ids_column: int = 0,
) -> Tuple[np.ndarray, List[str]]:
    """Load a square PLINK IBS similarity matrix and convert it to distance."""

    if not matrix_path.exists():
        raise FileNotFoundError(f"IBS matrix not found: {matrix_path}")
    ids = read_ids(ids_path, column=ids_column)
    matrix = np.loadtxt(matrix_path, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"IBS matrix must be square, got shape {matrix.shape}")
    if matrix.shape[0] != len(ids):
        raise ValueError(
            f"Matrix size {matrix.shape[0]} does not match IDs count {len(ids)}"
        )
    if not np.isfinite(matrix).all():
        raise ValueError("IBS matrix contains NaN or infinite values")
    if len(set(ids)) != len(ids):
        raise ValueError("Sample IDs in the IBS matrix are not unique")

    distances = 1.0 - matrix
    distances = (distances + distances.T) / 2.0
    np.fill_diagonal(distances, 0.0)
    if (distances < -1e-8).any():
        raise ValueError("IBS matrix produced negative distances; check matrix format")
    return np.maximum(distances, 0.0), ids


def generate_plink19_ibs(
    prefix: Path,
    output_prefix: Path,
    executable: str = "plink",
    autosome_count: Optional[int] = None,
    allow_extra_chr: bool = True,
) -> Tuple[Path, Path]:
    """Generate ``.mibs`` and ``.mibs.id`` using PLINK 1.9."""

    for suffix in (".bed", ".bim", ".fam"):
        required = Path(f"{prefix}{suffix}")
        if not required.exists():
            raise FileNotFoundError(f"Missing PLINK input: {required}")

    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    command = build_plink19_ibs_command(
        prefix,
        output_prefix,
        executable=executable,
        autosome_count=autosome_count,
        allow_extra_chr=allow_extra_chr,
    )

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"PLINK executable not found: {executable}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"PLINK failed with exit code {exc.returncode}") from exc

    matrix_path = Path(f"{output_prefix}.mibs")
    ids_path = Path(f"{output_prefix}.mibs.id")
    if not matrix_path.exists() or not ids_path.exists():
        raise RuntimeError("PLINK completed without producing .mibs and .mibs.id")
    return matrix_path, ids_path


def build_plink19_ibs_command(
    prefix: Path,
    output_prefix: Path,
    executable: str = "plink",
    autosome_count: Optional[int] = None,
    allow_extra_chr: bool = True,
) -> List[str]:
    """Build the reproducible PLINK 1.9 command used by the worker."""

    command = [executable, "--bfile", str(prefix)]
    if autosome_count is not None:
        command.extend(["--chr-set", str(autosome_count), "no-xy"])
    if allow_extra_chr:
        command.append("--allow-extra-chr")
    command.extend(["--distance", "square", "ibs", "--out", str(output_prefix)])
    return command
