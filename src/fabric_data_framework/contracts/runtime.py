"""Immutable runtime context, status aggregation and state-commit invariants."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Iterable
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from fabric_data_framework.metadata.config import Criticality, DatasetStatus, PipelineStatus, RunMode
from .base import FrozenModel
from .environment import EnvironmentName


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
    batch_quarantined: bool = False

    @property
    def can_advance_state(self) -> bool:
        return (
            self.target_committed
            and not self.batch_quarantined
            and (not self.reconciliation_required or self.reconciliation_passed)
        )


WatermarkScalar = str | int | float | datetime | None
WatermarkTieBreakerScalar = str | int | float


def _validate_watermark_scalar(value: Any, *, allow_none: bool, field_name: str) -> Any:
    if value is None:
        if allow_none:
            return value
        raise ValueError(f"{field_name} cannot be null")
    if type(value) is bool:
        raise TypeError(f"{field_name} cannot be bool")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    if isinstance(value, datetime):
        _require_aware(value, field_name)
        return value
    if type(value) not in {str, int, float}:
        raise TypeError(f"unsupported {field_name} type: {type(value).__name__}")
    return value


class WatermarkPosition(FrozenModel):
    value: WatermarkScalar
    tie_breaker: tuple[WatermarkTieBreakerScalar, ...] = ()

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: Any) -> Any:
        return _validate_watermark_scalar(value, allow_none=True, field_name="watermark value")

    @field_validator("tie_breaker", mode="before")
    @classmethod
    def validate_tie_breaker(cls, value: Any) -> Any:
        if value is None:
            return ()
        items = tuple(value)
        for index, item in enumerate(items):
            _validate_watermark_scalar(
                item,
                allow_none=False,
                field_name=f"watermark tie_breaker[{index}]",
            )
            if isinstance(item, datetime):
                raise TypeError("watermark tie_breaker values do not support datetime")
        return items


def _compare_scalar(left: Any, right: Any, *, field_name: str) -> int:
    _validate_watermark_scalar(left, allow_none=False, field_name=field_name)
    _validate_watermark_scalar(right, allow_none=False, field_name=field_name)

    if isinstance(left, datetime) or isinstance(right, datetime):
        if not isinstance(left, datetime) or not isinstance(right, datetime):
            raise TypeError(f"{field_name} types are not safely comparable")
        left_value = left.astimezone(timezone.utc)
        right_value = right.astimezone(timezone.utc)
    elif type(left) in {int, float} and type(right) in {int, float}:
        left_value = left
        right_value = right
    elif isinstance(left, str) and isinstance(right, str):
        left_value = left
        right_value = right
    else:
        raise TypeError(
            f"{field_name} types are not safely comparable: "
            f"{type(left).__name__} vs {type(right).__name__}"
        )

    if left_value < right_value:
        return -1
    if left_value > right_value:
        return 1
    return 0


def compare_watermark_positions(left: WatermarkPosition, right: WatermarkPosition) -> int:
    """Compare two composite positions or fail when their domains are incompatible."""

    value_order = _compare_scalar(left.value, right.value, field_name="watermark value")
    if value_order:
        return value_order
    if len(left.tie_breaker) != len(right.tie_breaker):
        raise ValueError(
            "watermark positions have different tie-breaker arity: "
            f"{len(left.tie_breaker)} vs {len(right.tie_breaker)}"
        )
    for index, (left_item, right_item) in enumerate(
        zip(left.tie_breaker, right.tie_breaker, strict=True)
    ):
        order = _compare_scalar(
            left_item,
            right_item,
            field_name=f"watermark tie_breaker[{index}]",
        )
        if order:
            return order
    return 0


class WatermarkState(FrozenModel):
    position: WatermarkPosition | None = None
    version: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_state(self) -> "WatermarkState":
        if (self.position is None) != (self.version == 0):
            raise ValueError("empty watermark state must have version 0 and committed state version >= 1")
        return self


class WatermarkConflictError(RuntimeError):
    """Raised when an atomic watermark compare-and-set observes a stale writer."""


class WatermarkTransition(FrozenModel):
    before: WatermarkPosition | None = None
    after: WatermarkPosition
    gate: StateCommitGate

    @model_validator(mode="after")
    def validate_advance(self) -> "WatermarkTransition":
        if self.before is None:
            changed = True
        else:
            ordering = compare_watermark_positions(self.after, self.before)
            if ordering < 0:
                raise ValueError("watermark/state cannot move backwards")
            changed = ordering > 0
        if changed and not self.gate.can_advance_state:
            raise ValueError(
                "watermark/state cannot advance before target commit and required reconciliation"
            )
        return self


__all__ = [
    "DatasetOutcome",
    "RuntimeContext",
    "StateCommitGate",
    "WatermarkConflictError",
    "WatermarkPosition",
    "WatermarkState",
    "WatermarkTransition",
    "aggregate_pipeline_status",
    "compare_watermark_positions",
]
