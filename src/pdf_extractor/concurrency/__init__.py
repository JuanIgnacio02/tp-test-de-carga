"""Concurrencia: pool de procesos y control de admisión (backpressure)."""

from .admission import AdmissionController, OverloadedError, QueueFullError, QueueTimeoutError
from .worker_pool import WorkerCrashedError, WorkerPool

__all__ = [
    "AdmissionController",
    "OverloadedError",
    "QueueFullError",
    "QueueTimeoutError",
    "WorkerCrashedError",
    "WorkerPool",
]
