"""Reusable analysis components for shrimp germplasm identification."""

__version__ = "0.3.0"
ALGORITHM_VERSION = "weighted-knn-0.1.0"

from .config import KNNConfig
from .evaluation import leave_one_out, predict_unknown_samples
from .job_runner import JobConfig, run_identification_job
from .weighted_knn import assign_one

__all__ = [
    "KNNConfig",
    "JobConfig",
    "ALGORITHM_VERSION",
    "assign_one",
    "leave_one_out",
    "predict_unknown_samples",
    "run_identification_job",
]
