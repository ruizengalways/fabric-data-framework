"""Compile effective dataset metadata into immutable execution-plan contracts.

This module owns planning/compiler logic. Stable provider-neutral plan structures live
in :mod:`fabric_data_framework.contracts.execution_plan` and contain no capability or
engine-resolution behavior.
"""

from __future__ import annotations

from fabric_data_framework.contracts.current_projection import CurrentProjectionMode
from fabric_data_framework.contracts.execution_plan import (
    ExecutionKind,
    ExecutionPlan,
    ExecutionRole,
    ExecutionUnit,
)
from fabric_data_framework.metadata.capabilities import (
    DEFAULT_CAPABILITY_REGISTRY,
    CapabilityRegistry,
)
from fabric_data_framework.metadata.config import (
    EffectiveDatasetConfig,
    ExecutionEngine,
    RunMode,
)


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

    if config.load.apply_strategy.value == "CURRENT_PROJECTION":
        projection = config.current_projection
        if projection is None:
            raise ValueError("CURRENT_PROJECTION execution requires projection metadata")
        if projection.mode in {CurrentProjectionMode.VIEW, CurrentProjectionMode.MATERIALIZED}:
            units = (
                _unit(
                    unit_id="current_projection_publish",
                    roles=(ExecutionRole.PREPARE, ExecutionRole.APPLY, ExecutionRole.PUBLISH, ExecutionRole.RECONCILE),
                    execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
                    retry_count=retry_count,
                    timeout_seconds=timeout_seconds,
                    reconciliation_gate=reconciliation_gate,
                    state_commit_boundary=False,
                ),
            )
        else:
            units = (
                _unit(
                    unit_id="current_projection_incremental",
                    roles=(
                        ExecutionRole.EXTRACT,
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
    elif capture_engine is ExecutionEngine.SPARK and apply_engine is ExecutionEngine.SPARK:
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
    """Build the deterministic single-unit plan used by the in-process backend."""

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
    if config.load.apply_strategy.value == "CURRENT_PROJECTION":
        projection = config.current_projection
        if projection is None:
            raise ValueError("CURRENT_PROJECTION execution requires projection metadata")
        is_incremental = projection.mode is CurrentProjectionMode.DELTA_PROJECTION
        units = (
            ExecutionUnit(
                unit_id=(
                    "current_projection_incremental"
                    if is_incremental
                    else "current_projection_publish"
                ),
                roles=(
                    (
                        ExecutionRole.EXTRACT,
                        ExecutionRole.NORMALIZE,
                        ExecutionRole.VALIDATE,
                        ExecutionRole.APPLY,
                        ExecutionRole.RECONCILE,
                        ExecutionRole.COMMIT_STATE,
                    )
                    if is_incremental
                    else (ExecutionRole.PREPARE, ExecutionRole.APPLY, ExecutionRole.PUBLISH, ExecutionRole.RECONCILE)
                ),
                execution_kind=execution_kind,
                retry_count=config.orchestration.retry_count,
                timeout_seconds=config.orchestration.timeout_seconds,
                reconciliation_gate=config.reconciliation.required_for_state_commit,
                state_commit_boundary=is_incremental,
            ),
        )
    else:
        units = (
            ExecutionUnit(
                unit_id="dataset_execute",
                execution_kind=execution_kind,
                retry_count=config.orchestration.retry_count,
                timeout_seconds=config.orchestration.timeout_seconds,
                reconciliation_gate=config.reconciliation.required_for_state_commit,
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


__all__ = ["build_default_execution_plan", "compile_execution_plan"]
