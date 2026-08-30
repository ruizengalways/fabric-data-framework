"""Target-native ambiguous-commit probe contract.

A real provider adapter may know how to inspect a submitted Warehouse statement,
Delta commit marker, Spark job result, or another provider-native audit record. This
module standardizes that evidence and persists the result into the durable target
operation journal before recovery proceeds.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field, model_validator
from sqlalchemy import Engine

from ..config import FrozenModel
from ..contracts.recovery import UnknownOutcomeResolution
from ..control_plane.target_operation_journal import read_target_operation, reconcile_target_operation
from ..target_operations import TargetOperationRecord, TargetOperationStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TargetCommitProbeRequest(FrozenModel):
    operation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_id: str = Field(min_length=1)
    operation_kind: str = Field(min_length=1, max_length=64)
    target_reference: str = Field(min_length=1, max_length=1024)
    effective_config_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    current_status: TargetOperationStatus
    current_version: int = Field(ge=1)
    owner_dataset_run_id: UUID
    owner_attempt: int = Field(ge=1)
    prior_outcome_reference: str | None = Field(default=None, max_length=2048)

    @classmethod
    def from_record(cls, record: TargetOperationRecord) -> "TargetCommitProbeRequest":
        return cls(
            operation_key=record.operation_key,
            dataset_id=record.dataset_id,
            operation_kind=record.operation_kind,
            target_reference=record.target_reference,
            effective_config_hash=record.effective_config_hash,
            input_fingerprint=record.input_fingerprint,
            current_status=record.status,
            current_version=record.version,
            owner_dataset_run_id=record.owner_dataset_run_id,
            owner_attempt=record.attempt,
            prior_outcome_reference=record.outcome_reference,
        )


class TargetCommitProbeEvidence(FrozenModel):
    """Provider-native evidence resolving (or failing to resolve) target outcome."""

    provider: str = Field(min_length=1, max_length=128)
    resolution: UnknownOutcomeResolution
    evidence_reference: str | None = Field(default=None, max_length=2048)
    native_operation_id: str | None = Field(default=None, max_length=1024)
    detail: str | None = None
    probed_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_evidence(self) -> "TargetCommitProbeEvidence":
        if self.probed_at.tzinfo is None or self.probed_at.utcoffset() is None:
            raise ValueError("probed_at must be timezone-aware")
        if (
            self.resolution is not UnknownOutcomeResolution.UNRESOLVED
            and self.evidence_reference is None
            and self.native_operation_id is None
        ):
            raise ValueError(
                "resolved target commit probe requires evidence_reference or native_operation_id"
            )
        return self

    @property
    def journal_reference(self) -> str | None:
        if self.evidence_reference is not None:
            return self.evidence_reference
        if self.native_operation_id is not None:
            return f"{self.provider}:{self.native_operation_id}"
        return None


@runtime_checkable
class TargetCommitProbe(Protocol):
    def probe(self, request: TargetCommitProbeRequest) -> TargetCommitProbeEvidence:
        """Inspect provider-native evidence without mutating the target."""


class TargetCommitProbeRunResult(FrozenModel):
    evidence: TargetCommitProbeEvidence
    record: TargetOperationRecord


def probe_and_reconcile_target_operation(
    engine: Engine,
    *,
    operation_key: str,
    dataset_run_id: UUID,
    attempt: int,
    probe: TargetCommitProbe,
) -> TargetCommitProbeRunResult:
    """Probe one ambiguous target operation and durably persist the result.

    Only ``IN_PROGRESS`` and ``UNKNOWN`` are probeable. A provider exception is
    converted to durable ``UNRESOLVED`` evidence so a process crash or flaky provider
    lookup cannot accidentally reopen execution. Raw provider exception messages are
    deliberately not persisted because driver errors may contain connection material.
    """

    current = read_target_operation(engine, operation_key)
    if current is None:
        raise KeyError(f"target operation not found: {operation_key}")
    if current.status not in {
        TargetOperationStatus.IN_PROGRESS,
        TargetOperationStatus.UNKNOWN,
    }:
        raise ValueError(
            "target commit probe requires IN_PROGRESS or UNKNOWN operation state; "
            f"current={current.status.value}"
        )

    request = TargetCommitProbeRequest.from_record(current)
    try:
        evidence = probe.probe(request)
    except Exception as exc:  # provider lookup failure must remain fail-closed
        evidence = TargetCommitProbeEvidence(
            provider=type(probe).__name__,
            resolution=UnknownOutcomeResolution.UNRESOLVED,
            detail=f"target commit probe raised {type(exc).__name__}",
        )

    updated = reconcile_target_operation(
        engine,
        operation_key=operation_key,
        expected_version=current.version,
        resolution=evidence.resolution,
        dataset_run_id=dataset_run_id,
        attempt=attempt,
        outcome_reference=evidence.journal_reference,
        error_message=evidence.detail,
    )
    return TargetCommitProbeRunResult(evidence=evidence, record=updated)


__all__ = [
    "TargetCommitProbe",
    "TargetCommitProbeEvidence",
    "TargetCommitProbeRequest",
    "TargetCommitProbeRunResult",
    "probe_and_reconcile_target_operation",
]
