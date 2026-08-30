"""Stable FULL_REBUILD state-cutover contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field

from fabric_data_framework.contracts.base import FrozenModel


class RebuildProgressKind(str, Enum):
    """Authoritative progress shape installed after a successful rebuild."""

    NONE = "NONE"
    WATERMARK = "WATERMARK"
    CDC = "CDC"
    EXTERNAL = "EXTERNAL"


class FullRebuildStateReplacement(FrozenModel):
    """Capture-aware runtime state to install after target rebuild succeeds.

    The state adapter owns physical persistence. This contract prevents the rebuild
    coordinator from blindly deleting all checkpoints when the correct cutover may be
    a watermark, a CDC fence, or provider-owned external progress evidence.
    """

    progress_kind: RebuildProgressKind
    progress_payload: dict[str, Any] = Field(default_factory=dict)
    dataset_state: dict[str, Any] = Field(default_factory=dict)
    source_boundary_reference: str | None = None


class FullRebuildStateSnapshot(FrozenModel):
    dataset_id: str = Field(min_length=1)
    version: int = Field(ge=0)
    replacement: FullRebuildStateReplacement | None = None
    last_rebuild_request_id: UUID | None = None
    last_rebuild_dataset_run_id: UUID | None = None


@runtime_checkable
class FullRebuildStateAdapter(Protocol):
    """Optimistic runtime-state cutover boundary for FULL_REBUILD."""

    def read_state(self, dataset_id: str) -> FullRebuildStateSnapshot: ...

    def commit_rebuild_state(
        self,
        *,
        dataset_id: str,
        expected_version: int,
        rebuild_request_id: UUID,
        dataset_run_id: UUID,
        replacement: FullRebuildStateReplacement,
    ) -> FullRebuildStateSnapshot: ...


__all__ = [
    "FullRebuildStateAdapter",
    "FullRebuildStateReplacement",
    "FullRebuildStateSnapshot",
    "RebuildProgressKind",
]
