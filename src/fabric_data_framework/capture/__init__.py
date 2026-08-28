"""Capture-strategy implementations and contracts."""

from .cdc import (
    CDCCheckpoint,
    CDCCheckpointTransition,
    CDCConflictError,
    CDCContractError,
    CDCEvidenceError,
    CDCEvent,
    CDCNormalizedBatch,
    CDCOperation,
    CDCOrderingError,
    CDCSourcePosition,
    build_cdc_checkpoint,
    normalize_cdc_batch,
)
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
    "CDCCheckpoint",
    "CDCCheckpointTransition",
    "CDCConflictError",
    "CDCContractError",
    "CDCEvidenceError",
    "CDCEvent",
    "CDCNormalizedBatch",
    "CDCOperation",
    "CDCOrderingError",
    "CDCSourcePosition",
    "FullCaptureBatch",
    "FullSnapshotEvidence",
    "FullSnapshotEvidenceError",
    "SnapshotCaptureBatch",
    "SnapshotEvidence",
    "SnapshotEvidenceError",
    "build_cdc_checkpoint",
    "capture_full_snapshot",
    "capture_snapshot",
    "normalize_cdc_batch",
]
