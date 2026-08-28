"""Provider-neutral isolated staging contracts used before target publication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4


@dataclass(frozen=True)
class StagedBatch:
    """Immutable candidate isolated from the live target until publication succeeds."""

    stage_id: UUID
    dataset_run_id: UUID
    rows: tuple[dict[str, Any], ...]


def stage_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    dataset_run_id: UUID,
    stage_id: UUID | None = None,
) -> StagedBatch:
    return StagedBatch(
        stage_id=stage_id or uuid4(),
        dataset_run_id=dataset_run_id,
        rows=tuple(dict(row) for row in rows),
    )
