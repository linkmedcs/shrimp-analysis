"""Prediction and leave-one-out evaluation helpers."""

from __future__ import annotations

from typing import List, Set, Tuple

import numpy as np
import pandas as pd

from .config import KNNConfig
from .weighted_knn import assign_one


def labels_for_matrix(matrix_ids: List[str], metadata: pd.DataFrame) -> np.ndarray:
    """Align metadata labels to the distance-matrix sample order."""

    return np.array(
        [
            metadata.loc[sample_id, "LABEL"] if sample_id in metadata.index else ""
            for sample_id in matrix_ids
        ],
        dtype=object,
    )


def known_label_set(labels: np.ndarray, config: KNNConfig) -> Set[str]:
    return {
        str(label)
        for label in labels
        if str(label) not in config.unknown_labels
    }


def predict_unknown_samples(
    matrix_ids: List[str],
    distances: np.ndarray,
    labels: np.ndarray,
    config: KNNConfig,
    reference_version: str = "unversioned",
    algorithm_version: str = "weighted-knn-0.1.0",
) -> pd.DataFrame:
    """Predict only samples whose labels are unknown."""

    config.validate()
    known_labels = known_label_set(labels, config)
    if not known_labels:
        raise ValueError("No labelled reference samples found")

    records = []
    for index, sample_id in enumerate(matrix_ids):
        if str(labels[index]) not in config.unknown_labels:
            continue
        result = assign_one(index, distances, labels, known_labels, config)
        records.append(
            {
                "ID": sample_id,
                "true_label": "",
                "reference_version": reference_version,
                "algorithm_version": algorithm_version,
                **result,
            }
        )
    return pd.DataFrame(records)


def leave_one_out(
    matrix_ids: List[str],
    distances: np.ndarray,
    labels: np.ndarray,
    config: KNNConfig,
    reference_version: str = "unversioned",
    algorithm_version: str = "weighted-knn-0.1.0",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate all labelled reference samples with leave-one-out KNN."""

    config.validate()
    known_labels = known_label_set(labels, config)
    if not known_labels:
        raise ValueError("No labelled reference samples found")

    records = []
    labelled_indices = [
        index for index, label in enumerate(labels) if str(label) in known_labels
    ]
    for index in labelled_indices:
        evaluation_labels = labels.copy()
        evaluation_labels[index] = ""
        result = assign_one(
            index,
            distances,
            evaluation_labels,
            known_labels,
            config,
        )
        predicted = str(result.get("predicted_label", ""))
        records.append(
            {
                "ID": matrix_ids[index],
                "true_label": labels[index],
                "predicted_label": predicted,
                "correct": bool(predicted and predicted == labels[index]),
                "status": result.get("status", ""),
                "known_neighbor_count": result.get("known_neighbor_count", 0),
                "score_ratio": result.get("score_ratio", np.nan),
                "reference_version": reference_version,
                "algorithm_version": algorithm_version,
            }
        )

    evaluation = pd.DataFrame(records)
    valid = evaluation[evaluation["predicted_label"] != ""]
    accuracy = float(valid["correct"].mean()) if not valid.empty else float("nan")
    summary = pd.DataFrame(
        [
            {
                "labelled_samples": len(evaluation),
                "predicted_samples": len(valid),
                "unassigned_samples": len(evaluation) - len(valid),
                "accuracy_on_predicted": accuracy,
                "k": config.k,
                "min_known_neighbors": config.min_known_neighbors,
                "epsilon": config.epsilon,
                "weight_power": config.weight_power,
                "reference_version": reference_version,
                "algorithm_version": algorithm_version,
            }
        ]
    )
    return evaluation, summary
