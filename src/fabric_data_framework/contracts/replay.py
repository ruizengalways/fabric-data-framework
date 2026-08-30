"""Stable quarantine-replay contracts.

Large quarantine payloads belong in governed data storage. The relational control
plane retains immutable lineage/reference evidence and the replay correlation only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field

from fabric_data_framework.contracts.base import FrozenModel


class QuarantineBatchEvidence(FrozenModel):
    """Control-plane evidence for one immutable quarantined batch."""

    quarantine_id: UUID
    dataset_run_id: UUID
    dataset_id: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    reason_code: str = Field(min_length=1)
    reason_detail: str | None = None
    source_reference: str | None = None
    replayed_by_dataset_run_id: UUID | None = None
    created_at: datetime


class QuarantineReplayPayload(FrozenModel):
    """Payload materialized by a governed quarantine data-store adapter."""

    quarantine_id: UUID
    dataset_id: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    rows: tuple[dict[str, Any], ...]
    payload_version: str | None = None


class QuarantineReplayPlan(FrozenModel):
    """Immutable replay scope derived from one audited REPLAY request."""

    reprocess_request_id: UUID
    dataset_id: str = Field(min_length=1)
    quarantine_ids: tuple[UUID, ...]
    source_references: tuple[str, ...]
    total_rows: int = Field(ge=0)

    def model_post_init(self, __context: Any) -> None:
        if not self.quarantine_ids:
            raise ValueError("quarantine replay plan requires at least one batch")
        if len(set(self.quarantine_ids)) != len(self.quarantine_ids):
            raise ValueError("quarantine replay plan cannot contain duplicate batch ids")
        if len(self.source_references) != len(self.quarantine_ids):
            raise ValueError("quarantine replay source references must align with batch ids")


@runtime_checkable
class QuarantineReplayPayloadProvider(Protocol):
    """Load retained quarantine payload without coupling recovery to one store."""

    def load_payload(self, batch: QuarantineBatchEvidence) -> QuarantineReplayPayload: ...


__all__ = [
    "QuarantineBatchEvidence",
    "QuarantineReplayPayload",
    "QuarantineReplayPayloadProvider",
    "QuarantineReplayPlan",
]
