"""Typed provider contracts for Microsoft Fabric physical capture stages.

These models do not call Fabric APIs. They define the stable boundary between the
provider-neutral ExecutionPlan and an injected Fabric transport/API implementation.
"""

from __future__ import annotations

from fabric_data_framework.contracts.temporal import require_aware_datetime, utc_now


from datetime import datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from fabric_data_framework.metadata.config import (
    CaptureStrategy,
    ExecutionEngine,
    ProgressOwner,)
from fabric_data_framework.contracts.base import FrozenModel
from ...contracts.execution_plan import ExecutionKind, ExecutionUnit


class FabricNativeRunStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class FabricCaptureRequest(FrozenModel):
    """One already-planned physical capture/staging invocation."""

    dataset_run_id: UUID
    dataset_id: str = Field(min_length=1)
    execution_unit: ExecutionUnit
    capture_strategy: CaptureStrategy
    execution_engine: ExecutionEngine
    progress_owner: ProgressOwner
    source_reference: str | None = None
    landing_reference: str = Field(min_length=1)
    source_lower_bound: Any | None = None
    source_upper_bound: Any | None = None
    snapshot_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> "FabricCaptureRequest":
        if self.execution_engine is ExecutionEngine.AUTO:
            raise ValueError("Fabric capture request requires a concrete execution_engine")
        return self


class FabricNativeRunEvidence(FrozenModel):
    """Provider evidence returned by a Fabric transport implementation."""

    native_run_id: str = Field(min_length=1)
    execution_kind: ExecutionKind
    status: FabricNativeRunStatus
    rows_read: int = Field(ge=0)
    rows_written: int = Field(ge=0)
    source_reference: str | None = None
    landing_reference: str = Field(min_length=1)
    source_lower_bound: Any | None = None
    source_upper_bound: Any | None = None
    snapshot_id: str | None = None
    complete_snapshot: bool | None = None
    external_checkpoint_reference: str | None = None
    schema_version: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence(self) -> "FabricNativeRunEvidence":
        require_aware_datetime(self.started_at, "started_at")
        require_aware_datetime(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")
        if self.rows_written > self.rows_read:
            raise ValueError("rows_written cannot exceed rows_read")
        return self


class FabricCaptureTransport(Protocol):
    """Injected API/SDK transport used by a Fabric capture adapter."""

    def invoke_capture(self, request: FabricCaptureRequest) -> FabricNativeRunEvidence:
        """Invoke one physical Fabric capture and return immutable native evidence."""
        ...


__all__ = [
    "FabricCaptureRequest",
    "FabricCaptureTransport",
    "FabricNativeRunEvidence",
    "FabricNativeRunStatus",
]
