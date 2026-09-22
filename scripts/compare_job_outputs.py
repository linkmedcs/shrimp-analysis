#!/usr/bin/env python3
"""Compare stable outputs from two identification Job Runner directories."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


VOLATILE_RESULT_FIELDS = {"job_id", "created_at", "completed_at"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def stable_result(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: value
        for key, value in result.items()
        if key not in VOLATILE_RESULT_FIELDS
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two completed job outputs.")
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    args = parser.parse_args()

    expected_assignments = read_csv(args.expected / "output/knn_assignments.csv")
    actual_assignments = read_csv(args.actual / "output/knn_assignments.csv")
    if expected_assignments != actual_assignments:
        raise SystemExit("knn_assignments.csv differs")
    print(f"OK knn_assignments.csv: {len(actual_assignments)} rows")

    expected_qc = json.loads(
        (args.expected / "output/quality_control.json").read_text(encoding="utf-8")
    )
    actual_qc = json.loads(
        (args.actual / "output/quality_control.json").read_text(encoding="utf-8")
    )
    if expected_qc != actual_qc:
        raise SystemExit("quality_control.json differs")
    print("OK quality_control.json")

    if stable_result(args.expected / "output/result.json") != stable_result(
        args.actual / "output/result.json"
    ):
        raise SystemExit("Stable result.json fields differ")
    print("OK stable result.json fields")
    print("Job outputs are equivalent.")


if __name__ == "__main__":
    main()
