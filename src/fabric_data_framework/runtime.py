"""Immutable runtime context, status aggregation and state-commit invariants."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import Criticality, DatasetStatus, PipelineStatus, RunMode
from .infrastructure import EnvironmentName


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class RuntimeContext(FrozenModel):
    pipeline_run_id: UUID = Field(default_factory=uuid4)
    dataset_run_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    environment: EnvironmentName
    domain: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    run_mode: RunMode = RunMode.NORMAL
    attempt: int = Field(default=1, ge=1)
    domain_git_sha: str = Field(pattern=r"^[0-9a-fA-F]{7,64}$")
    framework_version: str = Field(min_length=1)
    effective_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    deployment_id: UUID | None = None
    started_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_time(self) -> "RuntimeContext":
        _require_aware(self.started_at, "started_at")
        return self


class DatasetOutcome(FrozenModel):
    dataset_id: str = Field(min_length=1)
    status: DatasetStatus
    criticality: Criticality


_FINAL_DATASET_STATUSES = {
    DatasetStatus.SUCCEEDED,
    DatasetStatus.FAILED,
    DatasetStatus.QUARANTINED,
    DatasetStatus.SKIPPED,
    DatasetStatus.BLOCKED,
    DatasetStatus.CANCELLED,
}
_PROBLEM_STATUSES = {
    DatasetStatus.FAILED,
    DatasetStatus.QUARANTINED,
    DatasetStatus.BLOCKED,
    DatasetStatus.CANCELLED,
}


def aggregate_pipeline_status(
    outcomes: Iterable[DatasetOutcome],
    *,
    fatal_criticalities: frozenset[Criticality] = frozenset({Criticality.CRITICAL}),
) -> PipelineStatus:
    """Aggregate only after all eligible dataset work reaches a final state."""

    items = tuple(outcomes)
    non_final = [item for item in items if item.status not in _FINAL_DATASET_STATUSES]
    if non_final:
        raise ValueError("cannot aggregate pipeline status while dataset work is non-final")

    if any(
        item.status in _PROBLEM_STATUSES and item.criticality in fatal_criticalities
        for item in items
    ):
        return PipelineStatus.FAILED
    if any(item.status in _PROBLEM_STATUSES or item.status is DatasetStatus.SKIPPED for item in items):
        return PipelineStatus.PARTIAL_SUCCESS
    return PipelineStatus.SUCCESS


class StateCommitGate(FrozenModel):
    target_committed: bool
    reconciliation_required: bool = True
    reconciliation_passed: bool = False
    quarantined: bool = False

    @property
    def can_advance_state(self) -> bool:
        return (
            self.target_committed
            and not self.quarantined
            and (not self.reconciliation_required or self.reconciliation_passed)
        )


WatermarkScalar = str | int | float | datetime | None


class WatermarkPosition(FrozenModel):
    value: WatermarkScalar
    tie_breaker: tuple[str | int | float, ...] = ()


class WatermarkTransition(FrozenModel):
    before: WatermarkPosition | None = None
    after: WatermarkPosition
    gate: StateCommitGate

    @model_validator(mode="after")
    def validate_advance(self) -> "WatermarkTransition":
        changed = self.before is None or self.after != self.before
        if changed and not self.gate.can_advance_state:
            raise ValueError(
                "watermark/state cannot advance before target commit and required reconciliation"
            )
        return self
