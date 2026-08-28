"""Provider-neutral dataset execution-plan contracts.

An ExecutionPlan describes *how a bounded dataset request is hosted/executed* without
moving capture/apply correctness into a Fabric Pipeline or other provider adapter.
A single physical unit may own multiple semantic roles; activity count is therefore
not equivalent to framework step count.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from ..config import (
    ApplyStrategy,
    CaptureStrategy,
    EffectiveDatasetConfig,
    FrozenModel,
    RunMode,
    canonical_hash,
)


class ExecutionKind(str, Enum):
    """Physical execution mechanisms understood by framework adapters."""

    IN_PROCESS = "IN_PROCESS"
    FABRIC_COPY = "FABRIC_COPY"
    SPARK_JOB_DEFINITION = "SPARK_JOB_DEFINITION"
    FABRIC_NOTEBOOK = "FABRIC_NOTEBOOK"
    SQL_SCRIPT = "SQL_SCRIPT"


class ExecutionRole(str, Enum):
    """Semantic responsibilities that may be grouped into one physical unit."""

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
    """One physical execution boundary inside a dataset plan."""

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
    """Immutable provider-neutral execution snapshot for one dataset attempt."""

    dataset_id: str = Field(min_length=1)
    run_mode: RunMode
    capture_strategy: CaptureStrategy
    apply_strategy: ApplyStrategy
    effective_config_hash: str = Field(min_length=1)
    units: tuple[ExecutionUnit, ...]
    required_bindings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_plan(self) -> "ExecutionPlan":
        if not self.units:
            raise ValueError("execution plan requires at least one execution unit")
        unit_ids = [unit.unit_id for unit in self.units]
        if len(set(unit_ids)) != len(unit_ids):
            raise ValueError("execution plan unit_id values must be unique")
        if len(set(self.required_bindings)) != len(self.required_bindings):
            raise ValueError("execution plan required_bindings must be unique")
        return self

    @property
    def plan_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


def build_default_execution_plan(
    effective: EffectiveDatasetConfig,
    *,
    run_mode: RunMode,
    execution_kind: ExecutionKind = ExecutionKind.IN_PROCESS,
) -> ExecutionPlan:
    """Compile the current generic one-unit dataset execution contract.

    The default plan intentionally has one physical unit with semantic role EXECUTE.
    Future FULL/REPLACE, Copy+Spark/SQL and Fabric Pipeline adapters may compile the
    same effective metadata into multiple explicit units without changing capture or
    apply strategy semantics.
    """

    config = effective.config
    required_bindings = tuple(
        binding
        for binding in (config.source.connection_ref,)
        if binding is not None
    )
    return ExecutionPlan(
        dataset_id=config.dataset_id,
        run_mode=run_mode,
        capture_strategy=config.load.capture_strategy,
        apply_strategy=config.load.apply_strategy,
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
