"""Resolve display names without changing identification labels or stored results."""

from __future__ import annotations

import json
from pathlib import Path


def load_germplasm_names(path: Path) -> dict[str, str]:
    try:
        names = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(names, dict) or any(
        not isinstance(label, str)
        or not label.strip()
        or not isinstance(name, str)
        or not name.strip()
        for label, name in names.items()
    ):
        raise ValueError("Germplasm name map must contain nonempty label/name strings")
    return names


def add_germplasm_names(payload: dict, names: dict[str, str]) -> dict:
    result = dict(payload)
    if payload.get("assignments") is not None:
        result["assignments"] = [
            {
                **assignment,
                "predicted_name": names.get(
                    assignment.get("predicted_label"),
                    assignment.get("predicted_label"),
                ),
            }
            for assignment in payload["assignments"]
        ]
    return result
