"""Typed handoff from native/custom capture engines into framework processing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from ..config import CaptureStrategy, ExecutionEngine, FrozenModel, ProgressOwner


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class CaptureReceipt(FrozenModel):
    """Immutable evidence produced by a physical capture/movement operation."""

    dataset_run_id: UUID
    dataset_id: str = Field(min_length=1)
    capture_strategy: CaptureStrategy
    execution_engine: ExecutionEngine
    progress_owner: ProgressOwner
    native_run_id: str | None = None
    source_reference: str | None = None
    landing_reference: str = Field(min_length=1)
    rows_read: int = Field(ge=0)
    rows_written: int = Field(ge=0)
    source_lower_bound: Any | None = None
    source_upper_bound: Any | None = None
    snapshot_id: str | None = None
    complete_snapshot: bool | None = None
    external_checkpoint_reference: str | None = None
    schema_version: str | None = None
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_receipt(self) -> "CaptureReceipt":
        _require_aware(self.started_at, "started_at")
        _require_aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")
        if self.rows_written > self.rows_read:
            raise ValueError("rows_written cannot exceed rows_read for capture receipt")
        if self.capture_strategy in {CaptureStrategy.FULL, CaptureStrategy.SNAPSHOT}:
            if self.snapshot_id is None:
                raise ValueError("FULL/SNAPSHOT capture receipt requires snapshot_id")
            if self.complete_snapshot is None:
                raise ValueError("FULL/SNAPSHOT capture receipt requires completeness evidence")
        if (
            self.progress_owner is ProgressOwner.EXTERNAL
            and self.capture_strategy in {
                CaptureStrategy.WATERMARK,
                CaptureStrategy.CDC,
                CaptureStrategy.STREAM,
            }
            and not self.external_checkpoint_reference
        ):
            raise ValueError(
                "external progress owner requires external_checkpoint_reference "
                "for stateful capture"
            )
        return self
