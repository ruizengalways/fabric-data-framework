"""No-gap full-baseline -> WATERMARK bootstrap evidence and first-read planning."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from pydantic import Field

from ..config import FrozenModel, WatermarkConfig
from ..runtime import WatermarkPosition
from ..watermark import WatermarkBatch, plan_watermark_batch


class WatermarkBootstrapEvidenceError(ValueError):
    """Raised when source evidence cannot prove a safe baseline -> watermark handoff."""


class WatermarkBootstrapEvidence(FrozenModel):
    """Source/provider evidence that binds a complete baseline to one watermark boundary.

    ``baseline_consistent_through_boundary`` means the complete baseline contains the
    authoritative effects of source changes through ``boundary``.  The separate
    ``post_boundary_changes_guaranteed_visible`` proof prevents a timestamp-like
    watermark from being treated as safe when a later commit can appear at or below
    the already-committed boundary.
    """

    dataset_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    source_epoch: str = Field(min_length=1)
    boundary: WatermarkPosition
    complete_baseline: bool
    baseline_consistent_through_boundary: bool
    watermark_ordering_verified: bool
    post_boundary_changes_guaranteed_visible: bool


class WatermarkBootstrapPlan(FrozenModel):
    dataset_id: str
    snapshot_id: str
    source_epoch: str
    baseline_watermark: WatermarkPosition
    overlap_window_seconds: int
    first_incremental_may_reread_baseline: bool
    requires_idempotent_downstream: bool


def _validate_boundary_shape(
    boundary: WatermarkPosition,
    config: WatermarkConfig,
) -> None:
    if boundary.value is None:
        raise WatermarkBootstrapEvidenceError("watermark bootstrap boundary cannot be null")
    if len(boundary.tie_breaker) != len(config.tie_breaker):
        raise WatermarkBootstrapEvidenceError(
            "watermark bootstrap boundary tie-breaker arity does not match WatermarkConfig"
        )
    if config.overlap_window_seconds == 0 and not config.tie_breaker:
        raise WatermarkBootstrapEvidenceError(
            "strict watermark bootstrap requires a deterministic tie-breaker or a positive overlap window"
        )
    if config.overlap_window_seconds > 0 and not isinstance(boundary.value, datetime):
        raise WatermarkBootstrapEvidenceError(
            "positive watermark overlap bootstrap requires a datetime boundary"
        )


def plan_watermark_bootstrap(
    evidence: WatermarkBootstrapEvidence,
    config: WatermarkConfig,
) -> WatermarkBootstrapPlan:
    """Validate the source fence needed for a safe full-baseline -> watermark handoff."""

    _validate_boundary_shape(evidence.boundary, config)
    if not evidence.complete_baseline:
        raise WatermarkBootstrapEvidenceError(
            "watermark bootstrap requires a complete authoritative baseline"
        )
    if not evidence.baseline_consistent_through_boundary:
        raise WatermarkBootstrapEvidenceError(
            "watermark bootstrap requires proof that baseline is consistent through the boundary"
        )
    if not evidence.watermark_ordering_verified:
        raise WatermarkBootstrapEvidenceError(
            "watermark bootstrap requires a verified deterministic source ordering contract"
        )
    if not evidence.post_boundary_changes_guaranteed_visible:
        raise WatermarkBootstrapEvidenceError(
            "watermark bootstrap cannot prove that future source changes remain visible after the committed boundary"
        )

    overlap = config.overlap_window_seconds
    return WatermarkBootstrapPlan(
        dataset_id=evidence.dataset_id,
        snapshot_id=evidence.snapshot_id,
        source_epoch=evidence.source_epoch,
        baseline_watermark=evidence.boundary,
        overlap_window_seconds=overlap,
        first_incremental_may_reread_baseline=overlap > 0,
        requires_idempotent_downstream=overlap > 0,
    )


def plan_first_watermark_batch(
    rows: Sequence[Mapping[str, Any]],
    *,
    evidence: WatermarkBootstrapEvidence,
    config: WatermarkConfig,
) -> WatermarkBatch:
    """Plan the first steady-state watermark read after a proven baseline boundary.

    Strict watermark mode starts strictly after the committed composite boundary.
    Lookback mode intentionally rereads the configured overlap and therefore requires
    idempotent downstream semantics; reread is not treated as a bootstrap defect.
    """

    plan = plan_watermark_bootstrap(evidence, config)
    return plan_watermark_batch(rows, config, before=plan.baseline_watermark)


def assert_same_watermark_bootstrap(
    expected: WatermarkBootstrapEvidence,
    observed: WatermarkBootstrapEvidence,
) -> None:
    """Fail if a retry/replay tries to silently change the baseline fence evidence."""

    if expected != observed:
        raise WatermarkBootstrapEvidenceError(
            "watermark bootstrap evidence changed between attempts; reuse the original baseline fence"
        )


__all__ = [
    "WatermarkBootstrapEvidence",
    "WatermarkBootstrapEvidenceError",
    "WatermarkBootstrapPlan",
    "assert_same_watermark_bootstrap",
    "plan_first_watermark_batch",
    "plan_watermark_bootstrap",
]
