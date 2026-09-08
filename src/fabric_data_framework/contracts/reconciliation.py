"""Reconciliation result, metric, and observation contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from .base import FrozenModel


ReconciliationValue = str | int | float | bool
PartitionValue = str | int | float | bool | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class ReconciliationStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class ReconciliationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class ReconciliationMetric(FrozenModel):
    name: str = Field(min_length=1)
    expected: ReconciliationValue
    actual: ReconciliationValue
    passed: bool
    check_id: str | None = Field(default=None, min_length=1)
    severity: ReconciliationSeverity = ReconciliationSeverity.ERROR
    blocking: bool = True
    partition: dict[str, PartitionValue] | None = None

    @model_validator(mode="after")
    def validate_severity(self) -> "ReconciliationMetric":
        if self.severity is ReconciliationSeverity.WARNING and self.blocking:
            raise ValueError("WARNING reconciliation metric cannot block state advance")
        return self


class ReconciliationObservation(FrozenModel):
    """Provider-produced scalar evidence for one configured reconciliation check.

    Provider adapters collect observations through SQL/Spark/native engines. The
    framework evaluates policy semantics and tolerance centrally so provider completion
    never becomes reconciliation authority.
    """

    check_id: str = Field(min_length=1)
    expected: ReconciliationValue | None = None
    actual: ReconciliationValue | None = None
    passed: bool | None = None
    partition: dict[str, PartitionValue] | None = None
    details: dict[str, Any] | None = None


class ReconciliationResult(FrozenModel):
    reconciliation_id: UUID = Field(default_factory=uuid4)
    dataset_run_id: UUID
    dataset_id: str = Field(min_length=1)
    policy_name: str = Field(min_length=1)
    status: ReconciliationStatus
    metrics: tuple[ReconciliationMetric, ...] = ()
    blocks_state_advance: bool = True
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_status(self) -> "ReconciliationResult":
        _require_aware(self.created_at, "created_at")
        failed = tuple(metric for metric in self.metrics if not metric.passed)
        blocking_failed = tuple(metric for metric in failed if metric.blocking)
        if self.status is ReconciliationStatus.PASS and failed:
            raise ValueError("PASS reconciliation cannot contain failed metrics")
        if self.status is ReconciliationStatus.WARN:
            if not failed:
                raise ValueError("WARN reconciliation requires at least one failed metric")
            if blocking_failed:
                raise ValueError("WARN reconciliation cannot contain blocking failed metrics")
        if self.status is ReconciliationStatus.FAIL and failed and not blocking_failed:
            raise ValueError("FAIL reconciliation requires a blocking failed metric")
        return self


__all__ = [
    "ReconciliationMetric",
    "ReconciliationObservation",
    "ReconciliationResult",
    "ReconciliationSeverity",
    "ReconciliationStatus",
]
