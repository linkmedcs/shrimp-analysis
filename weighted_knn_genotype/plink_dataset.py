"""PLINK dataset parsing and marker-alignment helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple


DNA_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}


@dataclass(frozen=True)
class FamSample:
    fid: str
    iid: str
    paternal_id: str
    maternal_id: str
    sex: str
    phenotype: str


@dataclass(frozen=True)
class BimMarker:
    chromosome: str
    marker_id: str
    centimorgan: str
    position: int
    allele1: str
    allele2: str

    @property
    def allele_set(self) -> frozenset[str]:
        return frozenset((self.allele1.upper(), self.allele2.upper()))


@dataclass(frozen=True)
class MarkerAlignment:
    reference_marker_count: int
    query_marker_count: int
    compatible_ids: Tuple[str, ...]
    flip_ids: Tuple[str, ...]
    position_mismatch_ids: Tuple[str, ...]
    allele_mismatch_ids: Tuple[str, ...]
    missing_query_ids: Tuple[str, ...]
    extra_query_ids: Tuple[str, ...]

    @property
    def compatible_marker_count(self) -> int:
        return len(self.compatible_ids)

    @property
    def overlap_ratio(self) -> float:
        if self.reference_marker_count == 0:
            return 0.0
        return self.compatible_marker_count / self.reference_marker_count

    def to_dict(self) -> Dict[str, object]:
        return {
            "reference_marker_count": self.reference_marker_count,
            "query_marker_count": self.query_marker_count,
            "compatible_marker_count": self.compatible_marker_count,
            "marker_overlap_ratio": self.overlap_ratio,
            "strand_flip_count": len(self.flip_ids),
            "position_mismatch_count": len(self.position_mismatch_ids),
            "allele_mismatch_count": len(self.allele_mismatch_ids),
            "missing_query_marker_count": len(self.missing_query_ids),
            "extra_query_marker_count": len(self.extra_query_ids),
            "position_mismatch_ids": list(self.position_mismatch_ids),
            "allele_mismatch_ids": list(self.allele_mismatch_ids),
        }


def require_plink_prefix(prefix: Path) -> None:
    """Require a complete PLINK binary dataset."""

    for suffix in (".bed", ".bim", ".fam"):
        path = Path(f"{prefix}{suffix}")
        if not path.is_file():
            raise FileNotFoundError(f"Missing PLINK input: {path}")


def read_fam(path: Path) -> list[FamSample]:
    """Read and validate a PLINK ``.fam`` file."""

    if not path.is_file():
        raise FileNotFoundError(f"FAM file not found: {path}")
    samples: list[FamSample] = []
    seen_iids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            fields = line.strip().split()
            if not fields:
                continue
            if len(fields) < 6:
                raise ValueError(f"FAM line {line_number} has fewer than 6 fields")
            sample = FamSample(*fields[:6])
            if not sample.iid:
                raise ValueError(f"FAM line {line_number} has an empty IID")
            if sample.iid in seen_iids:
                raise ValueError(f"Duplicate IID in FAM: {sample.iid}")
            seen_iids.add(sample.iid)
            samples.append(sample)
    if not samples:
        raise ValueError(f"No samples found in FAM: {path}")
    return samples


def read_bim(path: Path) -> list[BimMarker]:
    """Read and validate a PLINK ``.bim`` file."""

    if not path.is_file():
        raise FileNotFoundError(f"BIM file not found: {path}")
    markers: list[BimMarker] = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            fields = line.strip().split()
            if not fields:
                continue
            if len(fields) < 6:
                raise ValueError(f"BIM line {line_number} has fewer than 6 fields")
            try:
                position = int(fields[3])
            except ValueError as exc:
                raise ValueError(
                    f"BIM line {line_number} has invalid position: {fields[3]}"
                ) from exc
            marker = BimMarker(
                chromosome=fields[0],
                marker_id=fields[1],
                centimorgan=fields[2],
                position=position,
                allele1=fields[4],
                allele2=fields[5],
            )
            if not marker.marker_id:
                raise ValueError(f"BIM line {line_number} has an empty marker ID")
            if marker.marker_id in seen_ids:
                raise ValueError(f"Duplicate marker ID in BIM: {marker.marker_id}")
            seen_ids.add(marker.marker_id)
            markers.append(marker)
    if not markers:
        raise ValueError(f"No markers found in BIM: {path}")
    return markers


def complement_alleles(alleles: Iterable[str]) -> frozenset[str] | None:
    """Return the DNA complement, or ``None`` for non-ACGT alleles."""

    complemented: set[str] = set()
    for allele in alleles:
        allele = allele.upper()
        if allele not in DNA_COMPLEMENT:
            return None
        complemented.add(DNA_COMPLEMENT[allele])
    return frozenset(complemented)


def align_markers(
    reference_markers: list[BimMarker],
    query_markers: list[BimMarker],
) -> MarkerAlignment:
    """Compare query markers to the reference, preserving reference order."""

    reference_by_id = {marker.marker_id: marker for marker in reference_markers}
    query_by_id = {marker.marker_id: marker for marker in query_markers}
    compatible: list[str] = []
    flips: list[str] = []
    position_mismatches: list[str] = []
    allele_mismatches: list[str] = []
    missing_query: list[str] = []

    for reference in reference_markers:
        query = query_by_id.get(reference.marker_id)
        if query is None:
            missing_query.append(reference.marker_id)
            continue
        if (
            query.chromosome != reference.chromosome
            or query.position != reference.position
        ):
            position_mismatches.append(reference.marker_id)
            continue

        if query.allele_set == reference.allele_set:
            compatible.append(reference.marker_id)
            continue

        complemented = complement_alleles(query.allele_set)
        if complemented is not None and complemented == reference.allele_set:
            compatible.append(reference.marker_id)
            flips.append(reference.marker_id)
            continue

        allele_mismatches.append(reference.marker_id)

    extra_query = [
        marker.marker_id
        for marker in query_markers
        if marker.marker_id not in reference_by_id
    ]
    return MarkerAlignment(
        reference_marker_count=len(reference_markers),
        query_marker_count=len(query_markers),
        compatible_ids=tuple(compatible),
        flip_ids=tuple(flips),
        position_mismatch_ids=tuple(position_mismatches),
        allele_mismatch_ids=tuple(allele_mismatches),
        missing_query_ids=tuple(missing_query),
        extra_query_ids=tuple(extra_query),
    )


def write_id_pairs(path: Path, samples: Iterable[FamSample]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for sample in samples:
            handle.write(f"{sample.fid}\t{sample.iid}\n")


def write_marker_ids(path: Path, marker_ids: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for marker_id in marker_ids:
            handle.write(f"{marker_id}\n")
