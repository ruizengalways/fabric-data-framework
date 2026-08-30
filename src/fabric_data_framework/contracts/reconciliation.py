"""Reconciliation result and metric contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from .base import FrozenModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class ReconciliationStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class ReconciliationMetric(FrozenModel):
    name: str = Field(min_length=1)
    expected: str | int | float
    actual: str | int | float
    passed: bool


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
        if self.status is ReconciliationStatus.PASS and any(
            not metric.passed for metric in self.metrics
        ):
            raise ValueError("PASS reconciliation cannot contain failed metrics")
        return self

__all__ = ["ReconciliationMetric", "ReconciliationResult", "ReconciliationStatus"]
