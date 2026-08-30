"""Safe FULL-candidate REPLACE planning and publication semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from pydantic import Field

from ..capture.full import FullSnapshotEvidence
from fabric_data_framework.contracts.base import FrozenModel
from ..data_plane.staging import StagedBatch
from fabric_data_framework.contracts.audit import MutationCounts


class ReplaceGuardError(ValueError):
    """Raised when a FULL candidate is unsafe to publish over the live target."""


class ReplaceGuardPolicy(FrozenModel):
    """Protective publication policy for FULL -> REPLACE."""

    require_complete_snapshot: bool = True
    allow_empty_source: bool = False
    allow_empty_candidate: bool = False
    max_candidate_drop_fraction: float | None = Field(default=None, ge=0.0, le=1.0)


@dataclass(frozen=True)
class ReplacePlan:
    rows: tuple[dict[str, Any], ...]
    before_count: int
    candidate_count: int
    mutations: MutationCounts


class InMemoryReplaceTarget:
    """Deterministic target adapter proving publication is isolated until commit."""

    def __init__(self, rows: Sequence[dict[str, Any]] = ()) -> None:
        self._rows = tuple(dict(row) for row in rows)

    def read(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(row) for row in self._rows)

    def publish(self, rows: Sequence[dict[str, Any]]) -> None:
        self._rows = tuple(dict(row) for row in rows)


def plan_replace(
    current_rows: Sequence[dict[str, Any]],
    staged: StagedBatch,
    *,
    evidence: FullSnapshotEvidence,
    policy: ReplaceGuardPolicy,
) -> ReplacePlan:
    """Validate destructive REPLACE guards without mutating the live target."""

    before_count = len(current_rows)
    candidate_count = len(staged.rows)

    if policy.require_complete_snapshot and not evidence.complete:
        raise ReplaceGuardError("FULL -> REPLACE requires complete snapshot evidence")

    if before_count > 0 and evidence.source_row_count == 0 and not policy.allow_empty_source:
        raise ReplaceGuardError(
            "empty FULL source is not allowed to replace a non-empty target"
        )

    if before_count > 0 and candidate_count == 0 and not policy.allow_empty_candidate:
        raise ReplaceGuardError(
            "empty accepted candidate is not allowed to replace a non-empty target"
        )

    if (
        policy.max_candidate_drop_fraction is not None
        and before_count > 0
        and candidate_count < before_count
    ):
        drop_fraction = (before_count - candidate_count) / before_count
        if drop_fraction > policy.max_candidate_drop_fraction:
            raise ReplaceGuardError(
                "FULL candidate row-count drop exceeds configured guard: "
                f"drop_fraction={drop_fraction:.6f}, "
                f"max={policy.max_candidate_drop_fraction:.6f}"
            )

    return ReplacePlan(
        rows=tuple(dict(row) for row in staged.rows),
        before_count=before_count,
        candidate_count=candidate_count,
        mutations=MutationCounts(inserted=candidate_count, deleted=before_count),
    )
