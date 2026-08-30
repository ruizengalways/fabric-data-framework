"""Provider-neutral dataset execution-plan contracts.

An ExecutionPlan separates semantic requirements from physical Fabric/native/custom
execution. One physical unit may own multiple semantic roles; activity count is not
equivalent to framework step count.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    EffectiveDatasetConfig,
    ExecutionEngine,
    RunMode,
    canonical_hash,
)
from fabric_data_framework.contracts.base import FrozenModel
from ..metadata.capabilities import CapabilityRegistry, DEFAULT_CAPABILITY_REGISTRY


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


_ENGINE_TO_KIND = {
    ExecutionEngine.FABRIC_COPY_JOB: ExecutionKind.FABRIC_COPY_JOB,
    ExecutionEngine.FABRIC_COPY_ACTIVITY: ExecutionKind.FABRIC_COPY_ACTIVITY,
    ExecutionEngine.DATAFLOW_GEN2: ExecutionKind.DATAFLOW_GEN2,
    ExecutionEngine.SPARK: ExecutionKind.SPARK_JOB_DEFINITION,
    ExecutionEngine.FABRIC_MIRRORING: ExecutionKind.FABRIC_MIRRORING,
    ExecutionEngine.EXTERNAL_CDC: ExecutionKind.EXTERNAL_CDC,
    ExecutionEngine.SQL: ExecutionKind.SQL_SCRIPT,
    ExecutionEngine.CUSTOM: ExecutionKind.CUSTOM,
}


def _unit(
    *,
    unit_id: str,
    roles: tuple[ExecutionRole, ...],
    execution_kind: ExecutionKind,
    retry_count: int,
    timeout_seconds: int,
    reconciliation_gate: bool = False,
    state_commit_boundary: bool = False,
) -> ExecutionUnit:
    return ExecutionUnit(
        unit_id=unit_id,
        roles=roles,
        execution_kind=execution_kind,
        retry_count=retry_count,
        timeout_seconds=timeout_seconds,
        reconciliation_gate=reconciliation_gate,
        state_commit_boundary=state_commit_boundary,
    )


def compile_execution_plan(
    effective: EffectiveDatasetConfig,
    *,
    run_mode: RunMode,
    capability_registry: CapabilityRegistry = DEFAULT_CAPABILITY_REGISTRY,
) -> ExecutionPlan:
    """Compile effective metadata into a conservative provider-neutral plan.

    Capture/movement and final-target apply are independent physical decisions.
    Native capture therefore never implies native apply. Framework normalization,
    validation, reconciliation and state ownership remain explicit around any
    delegated apply stage.
    """

    config = effective.config
    capture_engine = capability_registry.validate_capture(config)
    apply_engine = capability_registry.validate_apply(config)
    required_bindings = tuple(
        binding for binding in (config.source.connection_ref,) if binding is not None
    )
    retry_count = config.orchestration.retry_count
    timeout_seconds = config.orchestration.timeout_seconds
    reconciliation_gate = config.reconciliation.required_for_state_commit
    capture_kind = _ENGINE_TO_KIND[capture_engine]
    apply_kind = _ENGINE_TO_KIND[apply_engine]

    if capture_engine is ExecutionEngine.SPARK and apply_engine is ExecutionEngine.SPARK:
        units = (
            _unit(
                unit_id="dataset_execute",
                roles=(
                    ExecutionRole.EXTRACT,
                    ExecutionRole.STAGE,
                    ExecutionRole.NORMALIZE,
                    ExecutionRole.VALIDATE,
                    ExecutionRole.APPLY,
                    ExecutionRole.RECONCILE,
                    ExecutionRole.COMMIT_STATE,
                ),
                execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
                reconciliation_gate=reconciliation_gate,
                state_commit_boundary=True,
            ),
        )
    elif apply_engine is ExecutionEngine.SPARK:
        units = (
            _unit(
                unit_id="capture",
                roles=(ExecutionRole.EXTRACT, ExecutionRole.STAGE),
                execution_kind=capture_kind,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
            ),
            _unit(
                unit_id="framework_process",
                roles=(
                    ExecutionRole.NORMALIZE,
                    ExecutionRole.VALIDATE,
                    ExecutionRole.APPLY,
                    ExecutionRole.RECONCILE,
                    ExecutionRole.COMMIT_STATE,
                ),
                execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
                reconciliation_gate=reconciliation_gate,
                state_commit_boundary=True,
            ),
        )
    else:
        units = (
            _unit(
                unit_id="capture",
                roles=(ExecutionRole.EXTRACT, ExecutionRole.STAGE),
                execution_kind=capture_kind,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
            ),
            _unit(
                unit_id="framework_prepare",
                roles=(ExecutionRole.NORMALIZE, ExecutionRole.VALIDATE),
                execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
            ),
            _unit(
                unit_id="apply",
                roles=(ExecutionRole.APPLY, ExecutionRole.PUBLISH),
                execution_kind=apply_kind,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
            ),
            _unit(
                unit_id="framework_finalize",
                roles=(ExecutionRole.RECONCILE, ExecutionRole.COMMIT_STATE),
                execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
                reconciliation_gate=reconciliation_gate,
                state_commit_boundary=True,
            ),
        )

    return ExecutionPlan(
        dataset_id=config.dataset_id,
        run_mode=run_mode,
        capture_strategy=config.load.capture_strategy,
        apply_strategy=config.load.apply_strategy,
        capture_engine=capture_engine,
        apply_engine=apply_engine,
        capture_capability_profile=config.execution.capability_profile,
        apply_capability_profile=config.execution.apply_capability_profile,
        effective_config_hash=effective.effective_config_hash,
        units=units,
        required_bindings=required_bindings,
    )


def build_default_execution_plan(
    effective: EffectiveDatasetConfig,
    *,
    run_mode: RunMode,
    execution_kind: ExecutionKind = ExecutionKind.IN_PROCESS,
) -> ExecutionPlan:
    """Backward-compatible in-process plan used by deterministic reference tests."""

    config = effective.config
    required_bindings = tuple(
        binding for binding in (config.source.connection_ref,) if binding is not None
    )
    capture_engine = (
        config.execution.engine
        if config.execution.engine is not ExecutionEngine.AUTO
        else ExecutionEngine.SPARK
    )
    apply_engine = (
        config.execution.apply_engine
        if config.execution.apply_engine is not ExecutionEngine.AUTO
        else ExecutionEngine.SPARK
    )
    return ExecutionPlan(
        dataset_id=config.dataset_id,
        run_mode=run_mode,
        capture_strategy=config.load.capture_strategy,
        apply_strategy=config.load.apply_strategy,
        capture_engine=capture_engine,
        apply_engine=apply_engine,
        capture_capability_profile=config.execution.capability_profile,
        apply_capability_profile=config.execution.apply_capability_profile,
        effective_config_hash=effective.effective_config_hash,
        units=(
            ExecutionUnit(
                unit_id="dataset_execute",
                execution_kind=execution_kind,
                retry_count=config.orchestration.retry_count,
                timeout_seconds=config.orchestration.timeout_seconds,
                reconciliation_gate=config.reconciliation.required_for_state_commit,
                state_commit_boundary=True,
            ),
        ),
        required_bindings=required_bindings,
    )
