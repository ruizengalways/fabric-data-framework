"""Capture-strategy implementations and contracts."""

from .full import (
    FullCaptureBatch,
    FullSnapshotEvidence,
    FullSnapshotEvidenceError,
    capture_full_snapshot,
)

__all__ = [
    "FullCaptureBatch",
    "FullSnapshotEvidence",
    "FullSnapshotEvidenceError",
    "capture_full_snapshot",
]
