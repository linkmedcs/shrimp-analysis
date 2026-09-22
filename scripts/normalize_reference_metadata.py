#!/usr/bin/env python3
"""Normalize a reference metadata file to strict two-column TSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def normalize_metadata(source: Path, destination: Path) -> tuple[int, int]:
    """Write ``ID``/``POP`` rows and return record and blank-label counts."""

    seen_ids: set[str] = set()
    records: list[tuple[str, str]] = []

    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, None)
        if not header or header[0].strip() != "ID" or "POP" not in header:
            raise ValueError("Metadata header must contain ID and POP columns")

        for line_number, row in enumerate(reader, start=2):
            if not row or not any(field.strip() for field in row):
                continue

            sample_id = row[0].strip()
            if not sample_id:
                raise ValueError(f"Missing sample ID on line {line_number}")
            if sample_id in seen_ids:
                raise ValueError(f"Duplicate sample ID on line {line_number}: {sample_id}")

            non_empty_labels = [field.strip() for field in row[1:] if field.strip()]
            unique_labels = list(dict.fromkeys(non_empty_labels))
            if len(unique_labels) > 1:
                raise ValueError(
                    f"Conflicting labels on line {line_number}: {unique_labels}"
                )

            label = unique_labels[0] if unique_labels else ""
            seen_ids.add(sample_id)
            records.append((sample_id, label))

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["ID", "POP"])
        writer.writerows(records)

    blank_labels = sum(not label for _, label in records)
    return len(records), blank_labels


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize reference metadata to strict ID/POP TSV."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    record_count, blank_label_count = normalize_metadata(
        args.source,
        args.destination,
    )
    print(
        f"Wrote {record_count} records to {args.destination}; "
        f"blank labels: {blank_label_count}"
    )


if __name__ == "__main__":
    main()
