"""Durable semantic identity and lifecycle contracts for target mutations.

The framework intentionally separates a logical target operation from a physical
``dataset_run_id``. Retries of the same logical mutation must converge on the same
operation key even when a new physical attempt is created.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from .base import FrozenModel
from .recovery import UnknownOutcomeResolution


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def fingerprint_semantic_payload(payload: Any) -> str:
    """Return a stable SHA-256 fingerprint for JSON-compatible semantic input.

    Callers should fingerprint the *frozen input set or source boundary* that drives
    a target mutation: for example a snapshot ID + manifest, a watermark window, a
    CDC checkpoint range, or an immutable Bronze batch identifier. Runtime attempt
    IDs and timestamps must not be included.
    """

    try:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("semantic payload must be deterministic JSON-compatible data") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TargetOperationStatus(str, Enum):
    """Current durable state of one semantic target mutation."""

    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    UNKNOWN = "UNKNOWN"
    NOT_COMMITTED = "NOT_COMMITTED"


class TargetOperationAction(str, Enum):
    """What a caller is allowed to do after claiming an operation."""

    EXECUTE = "EXECUTE"
    SKIP_SUCCEEDED = "SKIP_SUCCEEDED"
    RECONCILE_REQUIRED = "RECONCILE_REQUIRED"


class TargetOperationIntent(FrozenModel):
    """Stable semantic identity of a target write, independent of physical attempt."""

    dataset_id: str = Field(min_length=1)
    operation_kind: str = Field(min_length=1, max_length=64)
    target_reference: str = Field(min_length=1, max_length=1024)
    effective_config_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    semantic_version: int = Field(default=1, ge=1)

    @field_validator("effective_config_hash", "input_fingerprint")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return value.lower()

    @property
    def operation_key(self) -> str:
        canonical = json.dumps(
            {
                "dataset_id": self.dataset_id,
                "effective_config_hash": self.effective_config_hash,
                "input_fingerprint": self.input_fingerprint,
                "operation_kind": self.operation_kind,
                "semantic_version": self.semantic_version,
                "target_reference": self.target_reference,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TargetOperationRecord(FrozenModel):
    """Persisted current state used for optimistic compare-and-swap decisions."""

    operation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_id: str = Field(min_length=1)
    operation_kind: str = Field(min_length=1, max_length=64)
    target_reference: str = Field(min_length=1, max_length=1024)
    effective_config_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    semantic_version: int = Field(default=1, ge=1)
    status: TargetOperationStatus
    owner_dataset_run_id: UUID
    attempt: int = Field(ge=1)
    version: int = Field(ge=1)
    outcome_reference: str | None = Field(default=None, max_length=2048)
    error_code: str | None = Field(default=None, max_length=128)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("effective_config_hash", "input_fingerprint")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return value.lower()

    @property
    def intent(self) -> TargetOperationIntent:
        return TargetOperationIntent(
            dataset_id=self.dataset_id,
            operation_kind=self.operation_kind,
            target_reference=self.target_reference,
            effective_config_hash=self.effective_config_hash,
            input_fingerprint=self.input_fingerprint,
            semantic_version=self.semantic_version,
        )

    @model_validator(mode="after")
    def validate_record(self) -> "TargetOperationRecord":
        if self.operation_key != self.intent.operation_key:
            raise ValueError("operation_key does not match semantic target operation intent")
        _require_aware(self.created_at, "created_at")
        if self.updated_at is not None:
            _require_aware(self.updated_at, "updated_at")
            if self.updated_at < self.created_at:
                raise ValueError("updated_at cannot be before created_at")
        if self.completed_at is not None:
            _require_aware(self.completed_at, "completed_at")
            if self.completed_at < self.created_at:
                raise ValueError("completed_at cannot be before created_at")
        if self.status is TargetOperationStatus.IN_PROGRESS and self.completed_at is not None:
            raise ValueError("IN_PROGRESS operation cannot have completed_at")
        if self.status is TargetOperationStatus.SUCCEEDED and self.completed_at is None:
            raise ValueError("SUCCEEDED operation requires completed_at")
        return self


class TargetOperationClaim(FrozenModel):
    action: TargetOperationAction
    record: TargetOperationRecord


class TargetOperationEvent(FrozenModel):
    """Append-only lifecycle evidence written beside each successful CAS transition."""

    event_id: UUID = Field(default_factory=uuid4)
    operation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    from_status: TargetOperationStatus | None = None
    to_status: TargetOperationStatus
    owner_dataset_run_id: UUID
    attempt: int = Field(ge=1)
    version: int = Field(ge=1)
    outcome_reference: str | None = Field(default=None, max_length=2048)
    error_code: str | None = Field(default=None, max_length=128)
    error_message: str | None = None
    occurred_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_time(self) -> "TargetOperationEvent":
        _require_aware(self.occurred_at, "occurred_at")
        return self


_ALLOWED_TRANSITIONS: dict[TargetOperationStatus, frozenset[TargetOperationStatus]] = {
    TargetOperationStatus.IN_PROGRESS: frozenset(
        {
            TargetOperationStatus.SUCCEEDED,
            TargetOperationStatus.UNKNOWN,
            TargetOperationStatus.NOT_COMMITTED,
        }
    ),
    TargetOperationStatus.UNKNOWN: frozenset(
        {
            TargetOperationStatus.SUCCEEDED,
            TargetOperationStatus.UNKNOWN,
            TargetOperationStatus.NOT_COMMITTED,
        }
    ),
    TargetOperationStatus.NOT_COMMITTED: frozenset({TargetOperationStatus.IN_PROGRESS}),
    TargetOperationStatus.SUCCEEDED: frozenset(),
}


def require_target_operation_transition(
    before: TargetOperationStatus,
    after: TargetOperationStatus,
) -> None:
    if after not in _ALLOWED_TRANSITIONS[before]:
        raise ValueError(f"invalid target operation transition: {before.value} -> {after.value}")


def resolution_for_target_operation(
    status: TargetOperationStatus,
) -> UnknownOutcomeResolution:
    """Map persisted target state to the existing fail-closed recovery contract."""

    if status is TargetOperationStatus.SUCCEEDED:
        return UnknownOutcomeResolution.COMMITTED
    if status is TargetOperationStatus.NOT_COMMITTED:
        return UnknownOutcomeResolution.NOT_COMMITTED
    return UnknownOutcomeResolution.UNRESOLVED


__all__ = [
    "TargetOperationAction",
    "TargetOperationClaim",
    "TargetOperationEvent",
    "TargetOperationIntent",
    "TargetOperationRecord",
    "TargetOperationStatus",
    "fingerprint_semantic_payload",
    "require_target_operation_transition",
    "resolution_for_target_operation",
]
