"""Quarantine evidence, review, and manual-correction contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from .base import FrozenModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QuarantineScope(str, Enum):
    ROW = "ROW"
    BATCH = "BATCH"


class QuarantineStatus(str, Enum):
    """Governed case status for one immutable quarantine batch.

    ``REPLAYED`` is a derived terminal status. Operators cannot set it directly; the
    framework derives it only from the successful replay correlation written after the
    target/reconciliation state gate passes.
    """

    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    WAIVED = "WAIVED"
    REPLAYED = "REPLAYED"


class QuarantineResolution(str, Enum):
    """Auditable reason a quarantine case stopped being open for investigation."""

    SOURCE_CORRECTED = "SOURCE_CORRECTED"
    RULE_OR_MAPPING_FIXED = "RULE_OR_MAPPING_FIXED"
    MANUAL_CORRECTION = "MANUAL_CORRECTION"
    ACCEPTED_EXCEPTION = "ACCEPTED_EXCEPTION"
    REJECTED_AS_INVALID = "REJECTED_AS_INVALID"


class QuarantineBatch(FrozenModel):
    quarantine_id: UUID = Field(default_factory=uuid4)
    dataset_run_id: UUID
    dataset_id: str = Field(min_length=1)
    scope: QuarantineScope
    row_count: int = Field(ge=1)
    reason_code: str = Field(min_length=1)
    reason_detail: str | None = None
    source_reference: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    replayed_by_dataset_run_id: UUID | None = None


class QuarantineManualCorrection(FrozenModel):
    """Immutable reference to a governed manual-correction payload.

    Corrected rows do not live in the relational Control Plane. ``correction_reference``
    points to governed data-plane storage and ``correction_payload_sha256`` binds the
    approval to exact correction bytes. The original quarantine payload remains
    immutable and is referenced separately.
    """

    correction_id: UUID = Field(default_factory=uuid4)
    quarantine_id: UUID
    dataset_id: str = Field(min_length=1)
    original_source_reference: str = Field(min_length=1)
    correction_reference: str = Field(min_length=1)
    correction_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corrected_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    ticket_reference: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class QuarantineReviewEvent(FrozenModel):
    """Append-only review/resolution event for one quarantine case."""

    event_id: UUID = Field(default_factory=uuid4)
    quarantine_id: UUID
    dataset_id: str = Field(min_length=1)
    status: QuarantineStatus
    resolution: QuarantineResolution | None = None
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    ticket_reference: str | None = None
    correction_id: UUID | None = None
    occurred_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_resolution_shape(self) -> "QuarantineReviewEvent":
        terminal = {
            QuarantineStatus.RESOLVED,
            QuarantineStatus.REJECTED,
            QuarantineStatus.WAIVED,
        }
        if self.status is QuarantineStatus.REPLAYED:
            raise ValueError("REPLAYED is derived from successful replay and cannot be a review event")
        if self.status in terminal and self.resolution is None:
            raise ValueError(f"{self.status.value} review event requires resolution")
        if self.status not in terminal and self.resolution is not None:
            raise ValueError("non-terminal review event cannot declare resolution")
        if self.resolution is QuarantineResolution.MANUAL_CORRECTION:
            if self.correction_id is None:
                raise ValueError("MANUAL_CORRECTION resolution requires correction_id")
        elif self.correction_id is not None:
            raise ValueError("correction_id is only valid for MANUAL_CORRECTION resolution")
        return self


class QuarantineCase(FrozenModel):
    """Derived current case state; original quarantine evidence remains authoritative."""

    quarantine_id: UUID
    dataset_id: str = Field(min_length=1)
    status: QuarantineStatus
    latest_review_event_id: UUID | None = None
    resolution: QuarantineResolution | None = None
    correction_id: UUID | None = None
    replayed_by_dataset_run_id: UUID | None = None

    @model_validator(mode="after")
    def validate_derived_state(self) -> "QuarantineCase":
        if self.status is QuarantineStatus.REPLAYED and self.replayed_by_dataset_run_id is None:
            raise ValueError("REPLAYED quarantine case requires replayed_by_dataset_run_id")
        if self.status is not QuarantineStatus.REPLAYED and self.replayed_by_dataset_run_id is not None:
            raise ValueError("replay marker requires derived REPLAYED quarantine case status")
        return self


__all__ = [
    "QuarantineBatch",
    "QuarantineCase",
    "QuarantineManualCorrection",
    "QuarantineResolution",
    "QuarantineReviewEvent",
    "QuarantineScope",
    "QuarantineStatus",
]
