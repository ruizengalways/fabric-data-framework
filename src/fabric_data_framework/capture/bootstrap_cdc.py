"""No-gap/no-double-apply snapshot bootstrap into steady-state CDC."""

from __future__ import annotations

from typing import Sequence

from pydantic import Field

from ..config import FrozenModel
from .cdc import (
    CDCCheckpoint,
    CDCEvidenceError,
    CDCEvent,
    CDCNormalizedBatch,
    normalize_cdc_batch,
)


class CDCBootstrapEvidenceError(CDCEvidenceError):
    """Raised when snapshot/stream evidence cannot prove a safe handoff."""


class CDCBootstrapEvidence(FrozenModel):
    """Provider-neutral evidence for a snapshot that is fenced by CDC positions.

    ``stream_start_checkpoint`` is the earliest CDC position retained/buffered for
    the bootstrap. ``snapshot_checkpoint`` is the inclusive source position through
    which the complete snapshot is transactionally/source-consistent.
    """

    dataset_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    source_epoch: str = Field(min_length=1)
    stream_start_checkpoint: CDCCheckpoint
    snapshot_checkpoint: CDCCheckpoint
    complete_snapshot: bool
    snapshot_consistent_through_checkpoint: bool
    stream_retained_from_start: bool


class CDCBootstrapPlan(FrozenModel):
    dataset_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    source_epoch: str = Field(min_length=1)
    stream_start_checkpoint: CDCCheckpoint
    lower_checkpoint: CDCCheckpoint


def _partition_map(checkpoint: CDCCheckpoint) -> dict[str, tuple[int, ...]]:
    return {item.partition: item.values for item in checkpoint.positions}


def _require_same_partitions(
    left: CDCCheckpoint,
    right: CDCCheckpoint,
    *,
    label: str,
) -> None:
    left_partitions = set(_partition_map(left))
    right_partitions = set(_partition_map(right))
    if left_partitions != right_partitions:
        raise CDCBootstrapEvidenceError(
            f"CDC bootstrap partition set changed between {label}; repartitioning during "
            "bootstrap is not certified"
        )


def plan_cdc_bootstrap(evidence: CDCBootstrapEvidence) -> CDCBootstrapPlan:
    """Validate the source fence needed for a safe snapshot -> CDC handoff."""

    if not evidence.complete_snapshot:
        raise CDCBootstrapEvidenceError("CDC bootstrap requires a complete snapshot")
    if not evidence.snapshot_consistent_through_checkpoint:
        raise CDCBootstrapEvidenceError(
            "CDC bootstrap requires proof that snapshot is consistent through its checkpoint"
        )
    if not evidence.stream_retained_from_start:
        raise CDCBootstrapEvidenceError(
            "CDC bootstrap requires retained/buffered CDC from stream start"
        )
    if not evidence.snapshot_checkpoint.positions:
        raise CDCBootstrapEvidenceError("CDC bootstrap snapshot checkpoint cannot be empty")

    _require_same_partitions(
        evidence.stream_start_checkpoint,
        evidence.snapshot_checkpoint,
        label="stream start and snapshot checkpoint",
    )
    start = _partition_map(evidence.stream_start_checkpoint)
    snapshot = _partition_map(evidence.snapshot_checkpoint)
    for partition, snapshot_position in snapshot.items():
        if start[partition] > snapshot_position:
            raise CDCBootstrapEvidenceError(
                f"CDC stream starts after snapshot checkpoint for partition {partition}; "
                "changes may be missing"
            )

    return CDCBootstrapPlan(
        dataset_id=evidence.dataset_id,
        snapshot_id=evidence.snapshot_id,
        source_epoch=evidence.source_epoch,
        stream_start_checkpoint=evidence.stream_start_checkpoint,
        lower_checkpoint=evidence.snapshot_checkpoint,
    )


def normalize_bootstrap_cdc_batch(
    events: Sequence[CDCEvent],
    *,
    evidence: CDCBootstrapEvidence,
    upper_checkpoint: CDCCheckpoint,
    complete_through_upper: bool,
) -> CDCNormalizedBatch:
    """Normalize buffered CDC after a proven snapshot boundary.

    Events at or below the snapshot checkpoint are intentionally ignored because the
    snapshot already contains their effects. Events strictly above that boundary are
    retained, proving the handoff has neither a source-position gap nor double apply.
    """

    plan = plan_cdc_bootstrap(evidence)
    _require_same_partitions(
        plan.lower_checkpoint,
        upper_checkpoint,
        label="snapshot checkpoint and first CDC upper checkpoint",
    )
    return normalize_cdc_batch(
        events,
        lower_checkpoint=plan.lower_checkpoint,
        upper_checkpoint=upper_checkpoint,
        complete_through_upper=complete_through_upper,
    )


__all__ = [
    "CDCBootstrapEvidence",
    "CDCBootstrapEvidenceError",
    "CDCBootstrapPlan",
    "normalize_bootstrap_cdc_batch",
    "plan_cdc_bootstrap",
]
