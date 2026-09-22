"""Reference-database manifest loading and checksum verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_reference_manifest(path: Path, verify: bool = True) -> Dict[str, object]:
    """Load a manifest and optionally verify every listed file checksum."""

    if not path.exists():
        raise FileNotFoundError(f"Reference manifest not found: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if "reference_version" not in manifest:
        raise ValueError("Reference manifest has no reference_version")
    if verify:
        for file_info in manifest.get("files", []):
            file_path = (path.parent / Path(str(file_info["path"]))).resolve()
            if not file_path.exists():
                raise FileNotFoundError(f"Reference file not found: {file_path}")
            expected = str(file_info.get("sha256", ""))
            if expected and sha256_file(file_path) != expected:
                raise ValueError(f"Reference checksum mismatch: {file_path}")
    return manifest


def reference_file_path(
    manifest_path: Path,
    manifest: Dict[str, object],
    role: str,
) -> Path:
    """Resolve exactly one file entry by role."""

    matches = [
        file_info
        for file_info in manifest.get("files", [])
        if str(file_info.get("role")) == role
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Reference manifest must contain exactly one {role!r} file; "
            f"found {len(matches)}"
        )
    return (manifest_path.parent / Path(str(matches[0]["path"]))).resolve()
