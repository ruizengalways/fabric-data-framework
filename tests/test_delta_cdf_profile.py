from datetime import datetime, timezone

import pytest

from fabric_data_framework.adapters.cdc import (
    DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY,
    DeltaCDFCDCAdapter,
    DeltaCDFChangeType,
    DeltaCDFRecord,
)
from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    ExecutionEngine,
    ExecutionPolicy,
    LoadPolicy,
    OrchestrationPolicy,
    ProgressOwner,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)
from fabric_data_framework.contracts.execution_plan import (
    ExecutionKind,
    ExecutionRole,
    compile_execution_plan,
)
from fabric_data_framework.metadata import (
    DEFAULT_CAPABILITY_REGISTRY,
    DELTA_CDF_PROFILE,
    UnsupportedExecutionCombination,
)


def _config(*, progress_owner: ProgressOwner = ProgressOwner.FRAMEWORK) -> DatasetConfig:
    return DatasetConfig(
        dataset_id="lakehouse.customer_cdf",
        source=SourceConfig(
            system="fabric_lakehouse",
            object="bronze.customer",
            connection_ref="customer_lakehouse",
        ),
        target=TargetConfig(layer="silver", object="customer_history"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.CDC,
            apply_strategy=ApplyStrategy.SCD2,
            business_key=("customer_id",),
            merge_key=("customer_id",),
        ),
        orchestration=OrchestrationPolicy(execution_group="lakehouse_cdf"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
        execution=ExecutionPolicy(
            engine=ExecutionEngine.SPARK,
            progress_owner=progress_owner,
            capability_profile=DELTA_CDF_PROFILE,
            apply_engine=ExecutionEngine.SPARK,
        ),
    )


def test_delta_cdf_profile_compiles_as_one_framework_spark_dataset_unit():
    config = _config()
    assert DEFAULT_CAPABILITY_REGISTRY.validate(config) is ExecutionEngine.SPARK

    plan = compile_execution_plan(
        resolve_effective_config(config),
        run_mode=RunMode.NORMAL,
    )
    assert plan.capture_engine is ExecutionEngine.SPARK
    assert plan.apply_engine is ExecutionEngine.SPARK
    assert plan.capture_capability_profile == DELTA_CDF_PROFILE
    assert len(plan.units) == 1
    assert plan.units[0].execution_kind is ExecutionKind.SPARK_JOB_DEFINITION
    assert plan.units[0].roles == (
        ExecutionRole.EXTRACT,
        ExecutionRole.STAGE,
        ExecutionRole.NORMALIZE,
        ExecutionRole.VALIDATE,
        ExecutionRole.APPLY,
        ExecutionRole.RECONCILE,
        ExecutionRole.COMMIT_STATE,
    )
    assert plan.units[0].state_commit_boundary is True


def test_delta_cdf_profile_rejects_external_progress_owner():
    with pytest.raises(UnsupportedExecutionCombination, match="progress owner"):
        DEFAULT_CAPABILITY_REGISTRY.validate_capture(
            _config(progress_owner=ProgressOwner.EXTERNAL)
        )


def test_default_provider_registry_resolves_delta_cdf_profile_and_normalizes():
    adapter = DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY.resolve(
        ExecutionEngine.SPARK,
        DELTA_CDF_PROFILE,
    )
    assert isinstance(adapter, DeltaCDFCDCAdapter)

    result = adapter.normalize(
        (
            DeltaCDFRecord(
                change_type=DeltaCDFChangeType.INSERT,
                commit_version=7,
                commit_timestamp=datetime(2026, 8, 29, 5, tzinfo=timezone.utc),
                data={"customer_id": 1, "name": "Ada"},
            ),
        ),
        table_reference="bronze.customer",
        key_columns=("customer_id",),
        upper_commit_version=7,
        complete_through_upper=True,
    )
    event = result.normalized_batch.events[0]
    assert event.after["name"] == "Ada"
    assert event.position.values == (7, 0)
