"""Logged PLINK 1.9 command execution for identification jobs."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class PlinkCommandError(RuntimeError):
    def __init__(self, command: Sequence[str], returncode: int):
        self.command = list(command)
        self.returncode = returncode
        super().__init__(
            f"PLINK failed with exit code {returncode}: "
            + " ".join(shlex.quote(part) for part in command)
        )


@dataclass(frozen=True)
class PlinkRuntime:
    executable: str = "plink"
    autosome_count: int | None = 45
    allow_extra_chr: bool = True

    def common_args(self) -> list[str]:
        args: list[str] = []
        if self.autosome_count is not None:
            args.extend(["--chr-set", str(self.autosome_count), "no-xy"])
        if self.allow_extra_chr:
            args.append("--allow-extra-chr")
        return args


def run_command(
    command: Sequence[str],
    log_path: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute a command and append combined output to the job log."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = " ".join(shlex.quote(str(part)) for part in command)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n$ {rendered}\n")
        log.flush()
        try:
            result = subprocess.run(
                [str(part) for part in command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"Executable not found: {command[0]}") from exc
        log.write(result.stdout or "")
        log.write(f"\n[exit_code={result.returncode}]\n")
    if check and result.returncode != 0:
        raise PlinkCommandError(command, result.returncode)
    return result


def run_bfile(
    input_prefix: Path,
    arguments: Sequence[str],
    output_prefix: Path,
    runtime: PlinkRuntime,
    log_path: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [runtime.executable, "--bfile", str(input_prefix)]
    command.extend(runtime.common_args())
    command.extend(str(argument) for argument in arguments)
    command.extend(["--out", str(output_prefix)])
    return run_command(command, log_path, check=check)


def run_vcf_import(
    vcf_path: Path,
    output_prefix: Path,
    runtime: PlinkRuntime,
    log_path: Path,
) -> subprocess.CompletedProcess[str]:
    """Convert a VCF/VCF.GZ query into the PLINK binary format."""

    command = [runtime.executable, "--vcf", str(vcf_path)]
    command.extend(runtime.common_args())
    command.extend(["--double-id", "--make-bed", "--out", str(output_prefix)])
    return run_command(command, log_path)


def run_merge(
    reference_prefix: Path,
    query_prefix: Path,
    output_prefix: Path,
    runtime: PlinkRuntime,
    log_path: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [runtime.executable, "--bfile", str(reference_prefix)]
    command.extend(runtime.common_args())
    command.extend(
        [
            "--bmerge",
            f"{query_prefix}.bed",
            f"{query_prefix}.bim",
            f"{query_prefix}.fam",
            "--make-bed",
            "--out",
            str(output_prefix),
        ]
    )
    return run_command(command, log_path, check=check)


def read_sample_missingness(path: Path) -> dict[str, float]:
    """Read PLINK 1.9 ``.imiss`` output keyed by IID."""

    if not path.is_file():
        raise FileNotFoundError(f"PLINK missingness output not found: {path}")
    values: dict[str, float] = {}
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().strip().split()
        try:
            iid_index = header.index("IID")
            missing_index = header.index("F_MISS")
        except ValueError as exc:
            raise ValueError(f"Unexpected PLINK .imiss header: {header}") from exc
        for line in handle:
            fields = line.strip().split()
            if not fields:
                continue
            values[fields[iid_index]] = float(fields[missing_index])
    return values
