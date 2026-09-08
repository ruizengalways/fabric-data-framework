"""Stable provider-neutral dataset execution-plan contracts.

An ExecutionPlan separates semantic requirements from physical Fabric/native/custom
execution. One physical unit may own multiple semantic roles; activity count is not
equivalent to framework step count. Compiler/capability resolution belongs to the
execution layer and must not be defined here.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    ExecutionEngine,
    RunMode,
    canonical_hash,
)


class ExecutionKind(str, Enum):
    IN_PROCESS = "IN_PROCESS"
    FABRIC_COPY_JOB = "FABRIC_COPY_JOB"
    FABRIC_COPY_ACTIVITY = "FABRIC_COPY_ACTIVITY"
    DATAFLOW_GEN2 = "DATAFLOW_GEN2"
    SPARK_JOB_DEFINITION = "SPARK_JOB_DEFINITION"
    FABRIC_NOTEBOOK = "FABRIC_NOTEBOOK"
    FABRIC_MIRRORING = "FABRIC_MIRRORING"
    EXTERNAL_CDC = "EXTERNAL_CDC"
    SQL_SCRIPT = "SQL_SCRIPT"
    CUSTOM = "CUSTOM"


class ExecutionRole(str, Enum):
    EXECUTE = "EXECUTE"
    PREPARE = "PREPARE"
    EXTRACT = "EXTRACT"
    STAGE = "STAGE"
    VALIDATE = "VALIDATE"
    NORMALIZE = "NORMALIZE"
    APPLY = "APPLY"
    RECONCILE = "RECONCILE"
    PUBLISH = "PUBLISH"
    COMMIT_STATE = "COMMIT_STATE"
    FINALIZE = "FINALIZE"


class ExecutionUnit(FrozenModel):
    unit_id: str = Field(min_length=1)
    roles: tuple[ExecutionRole, ...] = (ExecutionRole.EXECUTE,)
    execution_kind: ExecutionKind
    retry_count: int = Field(default=0, ge=0)
    timeout_seconds: int = Field(default=3600, gt=0)
    reconciliation_gate: bool = False
    state_commit_boundary: bool = False

    @model_validator(mode="after")
    def validate_roles(self) -> "ExecutionUnit":
        if not self.roles:
            raise ValueError("execution unit requires at least one semantic role")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("execution unit roles must be unique")
        return self


class ExecutionPlan(FrozenModel):
    dataset_id: str = Field(min_length=1)
    run_mode: RunMode
    capture_strategy: CaptureStrategy
    apply_strategy: ApplyStrategy
    capture_engine: ExecutionEngine = ExecutionEngine.SPARK
    apply_engine: ExecutionEngine = ExecutionEngine.SPARK
    capture_capability_profile: str | None = None
    apply_capability_profile: str | None = None
    effective_config_hash: str = Field(min_length=1)
    units: tuple[ExecutionUnit, ...]
    required_bindings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_plan(self) -> "ExecutionPlan":
        if not self.units:
            raise ValueError("execution plan requires at least one execution unit")
        if self.capture_engine is ExecutionEngine.AUTO:
            raise ValueError("execution plan capture_engine must be concrete")
        if self.apply_engine is ExecutionEngine.AUTO:
            raise ValueError("execution plan apply_engine must be concrete")
        unit_ids = [unit.unit_id for unit in self.units]
        if len(set(unit_ids)) != len(unit_ids):
            raise ValueError("execution plan unit_id values must be unique")
        if len(set(self.required_bindings)) != len(self.required_bindings):
            raise ValueError("execution plan required_bindings must be unique")
        state_boundaries = sum(unit.state_commit_boundary for unit in self.units)
        if state_boundaries > 1:
            raise ValueError("execution plan may contain at most one state commit boundary")
        return self

    @property
    def plan_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


__all__ = ["ExecutionKind", "ExecutionPlan", "ExecutionRole", "ExecutionUnit"]
