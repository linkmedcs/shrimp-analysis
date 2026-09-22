"""Configuration objects shared by the CLI and future worker service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


DEFAULT_UNKNOWN_LABELS: FrozenSet[str] = frozenset(
    {"", "NA", "N/A", ".", "Unknown", "unknown"}
)


@dataclass(frozen=True)
class KNNConfig:
    """Parameters controlling distance-weighted KNN assignment."""

    k: int = 5
    min_known_neighbors: int = 3
    epsilon: float = 1e-6
    weight_power: float = 1.0
    unknown_labels: FrozenSet[str] = DEFAULT_UNKNOWN_LABELS

    def validate(self) -> None:
        if self.k < 1:
            raise ValueError("k must be at least 1")
        if self.min_known_neighbors < 1:
            raise ValueError("min_known_neighbors must be at least 1")
        if self.min_known_neighbors > self.k:
            raise ValueError("min_known_neighbors cannot be greater than k")
        if self.epsilon <= 0:
            raise ValueError("epsilon must be positive")
        if self.weight_power <= 0:
            raise ValueError("weight_power must be positive")
