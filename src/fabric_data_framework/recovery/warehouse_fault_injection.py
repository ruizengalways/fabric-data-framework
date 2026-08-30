"""Approved real-fault contract for ambiguous Fabric Warehouse COMMIT evidence.

This module deliberately does not implement a generic network breaker. Provider or
enterprise code supplies a bounded fault injector through the controlled extension
registry. The framework retains only sanitized arm/verification evidence and requires
an actually observed execution exception before a fault-drill can PASS.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from ..recovery.target_probe import TargetCommitProbeEvidence
from ..evidence.safety import assert_safe_retained_text


class WarehouseCommitFaultPhase(str, Enum):
    COMMIT_ACKNOWLEDGEMENT = "COMMIT_ACKNOWLEDGEMENT"


class FabricWarehouseCommitFaultRequest(FrozenModel):
    operation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_id: str = Field(min_length=1, max_length=255)
    dataset_run_id: UUID
    attempt: int = Field(ge=1)
    target_reference: str = Field(min_length=1, max_length=1024)
    phase: WarehouseCommitFaultPhase = WarehouseCommitFaultPhase.COMMIT_ACKNOWLEDGEMENT


class FabricWarehouseCommitFaultArmEvidence(FrozenModel):
    armed: bool
    phase: WarehouseCommitFaultPhase
    evidence_reference: str | None = Field(default=None, max_length=2048)
    provider_fault_id: str | None = Field(default=None, max_length=1024)
    detail: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_evidence(self) -> "FabricWarehouseCommitFaultArmEvidence":
        if self.armed and self.evidence_reference is None and self.provider_fault_id is None:
            raise ValueError(
                "armed Warehouse fault evidence requires evidence_reference or provider_fault_id"
            )
        assert_safe_retained_text(
            self.model_dump_json(),
            "Warehouse fault arm evidence",
        )
        return self


class FabricWarehouseCommitFaultVerification(FrozenModel):
    triggered: bool
    phase: WarehouseCommitFaultPhase
    evidence_reference: str | None = Field(default=None, max_length=2048)
    provider_fault_id: str | None = Field(default=None, max_length=1024)
    detail: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_evidence(self) -> "FabricWarehouseCommitFaultVerification":
        if self.triggered and self.evidence_reference is None and self.provider_fault_id is None:
            raise ValueError(
                "triggered Warehouse fault verification requires evidence_reference or provider_fault_id"
            )
        assert_safe_retained_text(
            self.model_dump_json(),
            "Warehouse fault verification",
        )
        return self


@runtime_checkable
class FabricWarehouseCommitFaultInjector(Protocol):
    """Provider-specific bounded controller for one approved ambiguous-COMMIT drill."""

    def arm(
        self,
        request: FabricWarehouseCommitFaultRequest,
    ) -> FabricWarehouseCommitFaultArmEvidence:
        """Arm the approved provider/session fault before the target transaction."""

    def disarm(self, request: FabricWarehouseCommitFaultRequest) -> None:
        """Remove fault machinery before the framework performs the marker probe."""

    def verify(
        self,
        request: FabricWarehouseCommitFaultRequest,
        *,
        observed_exception_type: str | None,
        probe_evidence: TargetCommitProbeEvidence,
    ) -> FabricWarehouseCommitFaultVerification:
        """Verify the intended real fault actually fired for this exact operation."""


__all__ = [
    "FabricWarehouseCommitFaultArmEvidence",
    "FabricWarehouseCommitFaultInjector",
    "FabricWarehouseCommitFaultRequest",
    "FabricWarehouseCommitFaultVerification",
    "WarehouseCommitFaultPhase",
]
