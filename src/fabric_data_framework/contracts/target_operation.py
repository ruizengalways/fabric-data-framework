"""Stable target-mutation idempotency and journal contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field, model_validator

from ..config import ApplyStrategy, FrozenModel, RunMode, canonical_hash
from .recovery import UnknownOutcomeResolution

_HASH_PATTERN = r"^[0-9a-f]{64}$"
_OPERATION_KEY_SCHEMA = "target-operation-v1"


class TargetOperationStatus(str, Enum):
    PREPARED = "PREPARED"
    IN_PROGRESS = "IN_PROGRESS"
    COMMIT_UNKNOWN = "COMMIT_UNKNOWN"
    COMMITTED = "COMMITTED"
    NOT_COMMITTED = "NOT_COMMITTED"
    FAILED = "FAILED"


_ALLOWED_TRANSITIONS: dict[TargetOperationStatus, frozenset[TargetOperationStatus]] = {
    TargetOperationStatus.PREPARED: frozenset(
        {TargetOperationStatus.IN_PROGRESS, TargetOperationStatus.FAILED}
    ),
    TargetOperationStatus.IN_PROGRESS: frozenset(
        {
            TargetOperationStatus.COMMITTED,
            TargetOperationStatus.COMMIT_UNKNOWN,
            TargetOperationStatus.NOT_COMMITTED,
            TargetOperationStatus.FAILED,
        }
    ),
    TargetOperationStatus.COMMIT_UNKNOWN: frozenset(
        {TargetOperationStatus.COMMITTED, TargetOperationStatus.NOT_COMMITTED}
    ),
    TargetOperationStatus.NOT_COMMITTED: frozenset(
        {TargetOperationStatus.IN_PROGRESS, TargetOperationStatus.FAILED}
    ),
    TargetOperationStatus.COMMITTED: frozenset(),
    TargetOperationStatus.FAILED: frozenset(),
}


class InvalidTargetOperationTransition(ValueError):
    """Raised when a journal lifecycle transition is not allowed."""


class TargetOperationSpec(FrozenModel):
    """Semantic identity of one target mutation, stable across retry attempts.

    ``mutation_scope_hash`` is supplied by the owning executor from the frozen input
    boundary/set (watermark window, CDC range, snapshot/candidate identity, replay
    scope, etc.). Attempt IDs are deliberately excluded from ``operation_key``.
    """

    dataset_id: str = Field(min_length=1)
    run_mode: RunMode
    apply_strategy: ApplyStrategy
    target_reference: str = Field(min_length=1, max_length=1024)
    effective_config_hash: str = Field(pattern=_HASH_PATTERN)
    mutation_scope_hash: str = Field(pattern=_HASH_PATTERN)

    @property
    def operation_key(self) -> str:
        return canonical_hash(
            {
                "schema": _OPERATION_KEY_SCHEMA,
                "dataset_id": self.dataset_id,
                "run_mode": self.run_mode.value,
                "apply_strategy": self.apply_strategy.value,
                "target_reference": self.target_reference,
                "effective_config_hash": self.effective_config_hash,
                "mutation_scope_hash": self.mutation_scope_hash,
            }
        )

    def semantic_identity(self) -> dict[str, str]:
        return {
            "dataset_id": self.dataset_id,
            "run_mode": self.run_mode.value,
            "apply_strategy": self.apply_strategy.value,
            "target_reference": self.target_reference,
            "effective_config_hash": self.effective_config_hash,
            "mutation_scope_hash": self.mutation_scope_hash,
        }


class TargetOperationJournalEntry(FrozenModel):
    operation_key: str = Field(pattern=_HASH_PATTERN)
    dataset_id: str = Field(min_length=1)
    run_mode: RunMode
    apply_strategy: ApplyStrategy
    target_reference: str = Field(min_length=1, max_length=1024)
    effective_config_hash: str = Field(pattern=_HASH_PATTERN)
    mutation_scope_hash: str = Field(pattern=_HASH_PATTERN)
    first_dataset_run_id: UUID
    last_dataset_run_id: UUID
    status: TargetOperationStatus
    attempts_started: int = Field(ge=0)
    outcome_reference: str | None = Field(default=None, max_length=2048)
    last_error_code: str | None = Field(default=None, max_length=128)
    last_error_message: str | None = None
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime | None = None
    committed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_entry(self) -> "TargetOperationJournalEntry":
        if self.status is TargetOperationStatus.PREPARED and self.attempts_started != 0:
            raise ValueError("PREPARED target operation cannot have started attempts")
        if self.status in {
            TargetOperationStatus.IN_PROGRESS,
            TargetOperationStatus.COMMIT_UNKNOWN,
            TargetOperationStatus.COMMITTED,
            TargetOperationStatus.NOT_COMMITTED,
        } and self.attempts_started < 1:
            raise ValueError(f"{self.status.value} target operation requires a started attempt")
        if self.status is TargetOperationStatus.COMMITTED and self.committed_at is None:
            raise ValueError("COMMITTED target operation requires committed_at")
        if self.status is not TargetOperationStatus.COMMITTED and self.committed_at is not None:
            raise ValueError("only COMMITTED target operation may set committed_at")
        return self

    def matches(self, spec: TargetOperationSpec) -> bool:
        return self.operation_key == spec.operation_key and {
            "dataset_id": self.dataset_id,
            "run_mode": self.run_mode.value,
            "apply_strategy": self.apply_strategy.value,
            "target_reference": self.target_reference,
            "effective_config_hash": self.effective_config_hash,
            "mutation_scope_hash": self.mutation_scope_hash,
        } == spec.semantic_identity()


class TargetOperationReconciliation(FrozenModel):
    resolution: UnknownOutcomeResolution
    evidence_reference: str | None = Field(default=None, max_length=2048)


def validate_target_operation_transition(
    current: TargetOperationStatus,
    target: TargetOperationStatus,
) -> None:
    if target is current:
        return
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidTargetOperationTransition(
            f"target operation cannot transition {current.value} -> {target.value}"
        )


__all__ = [
    "InvalidTargetOperationTransition",
    "TargetOperationJournalEntry",
    "TargetOperationReconciliation",
    "TargetOperationSpec",
    "TargetOperationStatus",
    "validate_target_operation_transition",
]
