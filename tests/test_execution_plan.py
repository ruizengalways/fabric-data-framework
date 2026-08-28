from __future__ import annotations

import pytest
from pydantic import ValidationError

from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)
from fabric_data_framework.contracts.execution_plan import (
    ExecutionKind,
    ExecutionPlan,
    ExecutionRole,
    ExecutionUnit,
    build_default_execution_plan,
)


def _config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="crm.full_customer",
        source=SourceConfig(
            system="crm",
            object="dbo.Customer",
            connection_ref="crm-readonly",
        ),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(
            execution_group="daily",
            criticality=Criticality.HIGH,
            retry_count=3,
            timeout_seconds=900,
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(
            policy_name="count_and_completeness",
            required_for_state_commit=True,
        ),
    )


def test_default_execution_plan_preserves_semantics_and_runtime_policy():
    effective = resolve_effective_config(_config())

    plan = build_default_execution_plan(
        effective,
        run_mode=RunMode.NORMAL,
        execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
    )

    assert plan.dataset_id == "crm.full_customer"
    assert plan.capture_strategy is CaptureStrategy.FULL
    assert plan.apply_strategy is ApplyStrategy.REPLACE
    assert plan.effective_config_hash == effective.effective_config_hash
    assert plan.required_bindings == ("crm-readonly",)
    assert len(plan.units) == 1
    unit = plan.units[0]
    assert unit.unit_id == "dataset_execute"
    assert unit.roles == (ExecutionRole.EXECUTE,)
    assert unit.execution_kind is ExecutionKind.SPARK_JOB_DEFINITION
    assert unit.retry_count == 3
    assert unit.timeout_seconds == 900
    assert unit.reconciliation_gate is True
    assert unit.state_commit_boundary is True


def test_execution_plan_hash_is_deterministic_for_same_immutable_plan():
    effective = resolve_effective_config(_config())
    left = build_default_execution_plan(effective, run_mode=RunMode.NORMAL)
    right = build_default_execution_plan(effective, run_mode=RunMode.NORMAL)

    assert left == right
    assert left.plan_hash == right.plan_hash


def test_execution_plan_rejects_duplicate_unit_ids_and_roles():
    with pytest.raises(ValidationError, match="roles must be unique"):
        ExecutionUnit(
            unit_id="spark",
            roles=(ExecutionRole.EXTRACT, ExecutionRole.EXTRACT),
            execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
        )

    unit = ExecutionUnit(
        unit_id="spark",
        roles=(ExecutionRole.EXTRACT, ExecutionRole.APPLY),
        execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
    )
    with pytest.raises(ValidationError, match="unit_id values must be unique"):
        ExecutionPlan(
            dataset_id="crm.full_customer",
            run_mode=RunMode.NORMAL,
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
            effective_config_hash="a" * 64,
            units=(unit, unit),
        )
