"""Capture-strategy implementations and contracts."""

from .bootstrap_cdc import (
    CDCBootstrapEvidence,
    CDCBootstrapEvidenceError,
    CDCBootstrapPlan,
    normalize_bootstrap_cdc_batch,
    plan_cdc_bootstrap,
)
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
    "CDCBootstrapEvidence",
    "CDCBootstrapEvidenceError",
    "CDCBootstrapPlan",
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
    "normalize_bootstrap_cdc_batch",
    "normalize_cdc_batch",
    "plan_cdc_bootstrap",
]
