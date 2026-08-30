"""Pipeline, dataset and step execution audit contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from fabric_data_framework.metadata.config import DatasetStatus, PipelineStatus, RunMode
from .base import FrozenModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RowAccounting(FrozenModel):
    rows_read: int = Field(ge=0)
    rows_accepted: int = Field(ge=0)
    rows_quarantined: int = Field(default=0, ge=0)
    rows_filtered: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_balance(self) -> "RowAccounting":
        accounted = self.rows_accepted + self.rows_quarantined + self.rows_filtered
        if self.rows_read != accounted:
            raise ValueError(
                "row accounting must satisfy rows_read = accepted + quarantined + filtered"
            )
        return self


class MutationCounts(FrozenModel):
    inserted: int = Field(default=0, ge=0)
    updated: int = Field(default=0, ge=0)
    deleted: int = Field(default=0, ge=0)


class PipelineRunAudit(FrozenModel):
    pipeline_run_id: UUID = Field(default_factory=uuid4)
    environment: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    status: PipelineStatus
    run_mode: RunMode = RunMode.NORMAL
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    domain_git_sha: str = Field(pattern=r"^[0-9a-fA-F]{7,64}$")
    framework_version: str = Field(min_length=1)
    config_bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_times(self) -> "PipelineRunAudit":
        _require_aware(self.started_at, "started_at")
        if self.completed_at is not None:
            _require_aware(self.completed_at, "completed_at")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at cannot be before started_at")
        return self


class DatasetRunAudit(FrozenModel):
    dataset_run_id: UUID = Field(default_factory=uuid4)
    pipeline_run_id: UUID
    dataset_id: str = Field(min_length=1)
    attempt: int = Field(default=1, ge=1)
    run_mode: RunMode
    status: DatasetStatus
    effective_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_accounting: RowAccounting | None = None
    mutations: MutationCounts = Field(default_factory=MutationCounts)
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool | None = None
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "DatasetRunAudit":
        _require_aware(self.started_at, "started_at")
        if self.completed_at is not None:
            _require_aware(self.completed_at, "completed_at")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at cannot be before started_at")
        return self


class StepRunAudit(FrozenModel):
    step_run_id: UUID = Field(default_factory=uuid4)
    dataset_run_id: UUID
    step_name: str = Field(min_length=1)
    status: StepStatus
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    details: dict[str, object] | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "StepRunAudit":
        _require_aware(self.started_at, "started_at")
        if self.completed_at is not None:
            _require_aware(self.completed_at, "completed_at")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at cannot be before started_at")
        return self

__all__ = [
    "DatasetRunAudit", "MutationCounts", "PipelineRunAudit",
    "RowAccounting", "StepRunAudit", "StepStatus",
]
