"""Capture-strategy implementations and contracts."""

from .full import (
    FullCaptureBatch,
    FullSnapshotEvidence,
    FullSnapshotEvidenceError,
    capture_full_snapshot,
)
from .snapshot import (
    SnapshotCaptureBatch,
    SnapshotEvidence,
    SnapshotEvidenceError,
    capture_snapshot,
)

__all__ = [
    "FullCaptureBatch",
    "FullSnapshotEvidence",
    "FullSnapshotEvidenceError",
    "SnapshotCaptureBatch",
    "SnapshotEvidence",
    "SnapshotEvidenceError",
    "capture_full_snapshot",
    "capture_snapshot",
]
