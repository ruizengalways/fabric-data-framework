"""Provider-neutral versioned-target and blue/green cutover contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from fabric_data_framework.contracts.base import FrozenModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TargetVersionSpec(FrozenModel):
    """One physical target version behind a stable logical consumer object.

    The implementation/domain repository owns physical naming. The framework requires
    the stable logical object and physical version to be explicit so a candidate can be
    built and validated without replacing the currently active production object.
    """

    dataset_id: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    logical_object: str = Field(min_length=1)
    physical_object: str = Field(min_length=1)
    version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_distinct_physical_target(self) -> "TargetVersionSpec":
        if self.logical_object == self.physical_object:
            raise ValueError(
                "versioned target physical_object must differ from logical_object"
            )
        return self


class TargetCutoverGate(FrozenModel):
    """Evidence required before a logical consumer binding may move to a candidate."""

    candidate_built: bool
    reconciliation_passed: bool
    consumer_validation_passed: bool
    validation_reference: str = Field(min_length=1)
    approval_reference: str = Field(min_length=1)

    @property
    def can_promote(self) -> bool:
        return (
            self.candidate_built
            and self.reconciliation_passed
            and self.consumer_validation_passed
        )


class TargetCutoverRequest(FrozenModel):
    """Audited request to move a stable logical target from one version to another."""

    cutover_request_id: UUID = Field(default_factory=uuid4)
    dataset_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    logical_object: str = Field(min_length=1)
    from_version: str = Field(min_length=1)
    to_version: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    approval_reference: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_version_change(self) -> "TargetCutoverRequest":
        if self.from_version == self.to_version:
            raise ValueError("target cutover requires different from_version and to_version")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return self


class TargetActiveVersionSnapshot(FrozenModel):
    dataset_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    logical_object: str = Field(min_length=1)
    version: str = Field(min_length=1)
    physical_object: str = Field(min_length=1)
    generation: int = Field(ge=1)
    last_cutover_request_id: UUID | None = None


@runtime_checkable
class TargetCutoverAdapter(Protocol):
    """Environment-specific logical-binding switch boundary."""

    def read_active(
        self,
        *,
        dataset_id: str,
        environment: str,
        logical_object: str,
    ) -> TargetActiveVersionSnapshot: ...

    def promote(
        self,
        *,
        expected_generation: int,
        request: TargetCutoverRequest,
        candidate: TargetVersionSpec,
    ) -> TargetActiveVersionSnapshot: ...


class TargetCutoverResult(FrozenModel):
    request_id: UUID
    before: TargetActiveVersionSnapshot
    after: TargetActiveVersionSnapshot
    candidate: TargetVersionSpec
    already_promoted: bool = False


__all__ = [
    "TargetActiveVersionSnapshot",
    "TargetCutoverAdapter",
    "TargetCutoverGate",
    "TargetCutoverRequest",
    "TargetCutoverResult",
    "TargetVersionSpec",
]
