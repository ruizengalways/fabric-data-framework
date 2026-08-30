"""Stable recovery/reprocessing contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from fabric_data_framework.config import RunMode
from fabric_data_framework.contracts.base import FrozenModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReprocessRequestStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class UnknownOutcomeResolution(str, Enum):
    """Result of reconciliation after an uncertain target mutation response."""

    COMMITTED = "COMMITTED"
    NOT_COMMITTED = "NOT_COMMITTED"
    UNRESOLVED = "UNRESOLVED"


class ReprocessRequest(FrozenModel):
    """Audited operator/system request for non-normal processing."""

    reprocess_request_id: UUID = Field(default_factory=uuid4)
    dataset_id: str = Field(min_length=1)
    run_mode: RunMode
    reason: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    original_pipeline_run_id: UUID | None = None
    original_dataset_run_id: UUID | None = None
    range_json: dict[str, Any] | None = None
    status: ReprocessRequestStatus = ReprocessRequestStatus.PENDING
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_request(self) -> "ReprocessRequest":
        if self.run_mode is RunMode.NORMAL:
            raise ValueError("reprocess request cannot use NORMAL run mode")
        if self.run_mode is RunMode.RETRY and self.original_dataset_run_id is None:
            raise ValueError("RETRY request requires original_dataset_run_id")
        if self.run_mode is RunMode.BACKFILL:
            payload = self.range_json or {}
            if "lower" not in payload or "upper" not in payload:
                raise ValueError("BACKFILL request requires lower and upper range_json bounds")
        if self.run_mode is RunMode.REPLAY:
            quarantine_ids = (self.range_json or {}).get("quarantine_ids")
            if self.original_dataset_run_id is None and not quarantine_ids:
                raise ValueError(
                    "REPLAY request requires original_dataset_run_id or quarantine_ids"
                )
        if self.run_mode is RunMode.FULL_REBUILD:
            if (self.range_json or {}).get("authoritative_reset") is not True:
                raise ValueError(
                    "FULL_REBUILD request requires range_json.authoritative_reset=true"
                )
        if self.updated_at is not None and self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at")
        return self


class DatasetAttemptLineage(FrozenModel):
    """Immutable linkage for one physical/logical dataset attempt."""

    dataset_run_id: UUID
    dataset_id: str = Field(min_length=1)
    root_dataset_run_id: UUID
    previous_dataset_run_id: UUID | None = None
    attempt: int = Field(ge=1)
    run_mode: RunMode
    reprocess_request_id: UUID | None = None
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_lineage(self) -> "DatasetAttemptLineage":
        if self.attempt == 1:
            if self.previous_dataset_run_id is not None:
                raise ValueError("attempt 1 cannot have previous_dataset_run_id")
            if self.root_dataset_run_id != self.dataset_run_id:
                raise ValueError("attempt 1 must be its own root_dataset_run_id")
        elif self.previous_dataset_run_id is None:
            raise ValueError("attempt > 1 requires previous_dataset_run_id")
        return self


__all__ = [
    "DatasetAttemptLineage",
    "ReprocessRequest",
    "ReprocessRequestStatus",
    "UnknownOutcomeResolution",
]
