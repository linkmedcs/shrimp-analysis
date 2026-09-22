#!/usr/bin/env python3
"""Compare weighted-KNN CSV result directories semantically."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


RESULT_FILES = (
    "knn_assignments.csv",
    "loo_evaluation.csv",
    "loo_summary.csv",
)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two KNN result directories.")
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    args = parser.parse_args()

    mismatches: list[str] = []
    for filename in RESULT_FILES:
        expected_path = args.expected / filename
        actual_path = args.actual / filename
        if not expected_path.exists() or not actual_path.exists():
            mismatches.append(f"{filename}: missing file")
            continue

        expected_rows = read_rows(expected_path)
        actual_rows = read_rows(actual_path)
        if expected_rows != actual_rows:
            mismatches.append(
                f"{filename}: differs "
                f"({len(expected_rows)} expected rows, {len(actual_rows)} actual rows)"
            )
        else:
            print(f"OK {filename}: {len(actual_rows)} rows")

    if mismatches:
        raise SystemExit("Result comparison failed:\n" + "\n".join(mismatches))
    print("All result files are identical.")


if __name__ == "__main__":
    main()
