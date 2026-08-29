"""FULL capture contracts: explicit complete-snapshot evidence, never inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from pydantic import Field

from ..config import FrozenModel


class FullSnapshotEvidenceError(ValueError):
    """Raised when source-provided FULL snapshot evidence is internally inconsistent."""


class FullSnapshotEvidence(FrozenModel):
    """Evidence supplied by a source adapter for one bounded FULL snapshot."""

    snapshot_id: str = Field(min_length=1)
    complete: bool
    source_row_count: int = Field(ge=0)
    boundary_ref: str | None = None


@dataclass(frozen=True)
class FullCaptureBatch:
    rows: tuple[dict[str, Any], ...]
    evidence: FullSnapshotEvidence


def capture_full_snapshot(
    rows: Sequence[Mapping[str, Any]],
    *,
    evidence: FullSnapshotEvidence,
) -> FullCaptureBatch:
    """Freeze a source-provided FULL candidate and verify its evidence count.

    Completeness is deliberately *not* inferred from successful iteration or row
    count. A connector/source adapter must provide the evidence. Publication guards
    decide whether an incomplete snapshot is allowed (production default: no).
    """

    frozen_rows = tuple(dict(row) for row in rows)
    if evidence.source_row_count != len(frozen_rows):
        raise FullSnapshotEvidenceError(
            "source snapshot evidence row count does not match extracted rows: "
            f"evidence={evidence.source_row_count}, actual={len(frozen_rows)}"
        )
    return FullCaptureBatch(rows=frozen_rows, evidence=evidence)
