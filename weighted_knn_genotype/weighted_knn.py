"""Core distance-weighted KNN implementation."""

from __future__ import annotations

from typing import Dict, Set

import numpy as np

from .config import KNNConfig


def assign_one(
    target_index: int,
    distances: np.ndarray,
    labels: np.ndarray,
    known_labels: Set[str],
    config: KNNConfig,
) -> Dict[str, object]:
    """Assign one target using only labelled reference samples as candidates."""

    config.validate()
    if distances.ndim != 2 or distances.shape[0] != distances.shape[1]:
        raise ValueError("distances must be a square matrix")
    if len(labels) != distances.shape[0]:
        raise ValueError("labels length must match the distance matrix")
    if target_index < 0 or target_index >= len(labels):
        raise IndexError("target_index is outside the distance matrix")

    known_candidates = np.array(
        [
            index
            for index, label in enumerate(labels)
            if index != target_index and label in known_labels
        ],
        dtype=int,
    )
    result: Dict[str, object] = {
        "reference_candidate_count": int(len(known_candidates)),
    }
    if len(known_candidates) < config.min_known_neighbors:
        result.update(
            {
                "neighbor_count": 0,
                "known_neighbor_count": 0,
                "predicted_label": "",
                "status": "insufficient_reference_samples",
            }
        )
        return result

    candidate_distances = distances[target_index, known_candidates]
    candidate_order = np.argsort(candidate_distances, kind="stable")
    neighbors = known_candidates[
        candidate_order[: min(config.k, len(known_candidates))]
    ]
    neighbor_distances = distances[target_index, neighbors]
    weights = 1.0 / np.power(
        neighbor_distances + config.epsilon,
        config.weight_power,
    )

    scores: Dict[str, float] = {}
    for label, weight in zip(labels[neighbors], weights):
        scores[str(label)] = scores.get(str(label), 0.0) + float(weight)
    mean_distance = {
        label: float(np.mean(neighbor_distances[labels[neighbors] == label]))
        for label in scores
    }
    ranked = sorted(
        scores.items(),
        key=lambda item: (-item[1], mean_distance[item[0]], item[0]),
    )
    best_label = ranked[0][0]
    top_score = ranked[0][1]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    result.update(
        {
            "neighbor_count": int(len(neighbors)),
            "known_neighbor_count": int(len(neighbors)),
            "predicted_label": best_label,
            "status": "assigned",
            "top_score": top_score,
            "second_score": second_score,
            "score_ratio": (
                float("inf") if second_score == 0 else top_score / second_score
            ),
            "assigned_mean_distance": mean_distance[best_label],
            "nearest_distance": float(np.min(neighbor_distances)),
            "scores": ";".join(
                f"{label}={score:.8g}" for label, score in ranked
            ),
        }
    )
    return result
