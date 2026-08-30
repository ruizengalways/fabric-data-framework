import pytest

from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    ExecutionEngine,
    ExecutionPolicy,
    ExtensionConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ProgressOwner,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
    resolve_effective_config,
)
from fabric_data_framework.contracts.execution_plan import (
    ExecutionKind,
    ExecutionRole,
    compile_execution_plan,
)
from fabric_data_framework.metadata import UnsupportedExecutionCombination
from fabric_data_framework.metadata.capabilities import (
    DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
)


def _config(
    *,
    apply: ApplyStrategy = ApplyStrategy.SCD1,
    execution: ExecutionPolicy | None = None,
    extensions: ExtensionConfig | None = None,
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id="erp.customer",
        source=SourceConfig(system="erp", object="dbo.Customer", connection_ref="erp_sql"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=apply,
            merge_key=("customer_id",),
            watermark=WatermarkConfig(column="modified_at", overlap_window_seconds=60),
            event_time_column="modified_at",
            version_column="source_version",
            sequence_column="source_sequence",
        ),
        orchestration=OrchestrationPolicy(execution_group="erp_current"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
        execution=execution or ExecutionPolicy(),
        extensions=extensions or ExtensionConfig(),
    )


def test_load_policy_exposes_declared_apply_ordering_tuple():
    config = _config()
    assert config.load.ordering_columns == (
        "modified_at",
        "source_version",
        "source_sequence",
    )


def test_dataflow_incremental_capture_defaults_to_framework_scd1_apply():
    config = _config(
        execution=ExecutionPolicy(
            engine=ExecutionEngine.DATAFLOW_GEN2,
            progress_owner=ProgressOwner.FABRIC_NATIVE,
            capability_profile=DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
        )
    )

    plan = compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)

    assert plan.capture_engine is ExecutionEngine.DATAFLOW_GEN2
    assert plan.apply_engine is ExecutionEngine.SPARK
    assert plan.capture_capability_profile == DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE
    assert plan.apply_capability_profile is None
    assert [unit.execution_kind for unit in plan.units] == [
        ExecutionKind.DATAFLOW_GEN2,
        ExecutionKind.SPARK_JOB_DEFINITION,
    ]
    assert plan.units[0].roles == (ExecutionRole.EXTRACT, ExecutionRole.STAGE)
    assert ExecutionRole.APPLY in plan.units[1].roles
    assert plan.units[1].state_commit_boundary is True


def test_native_capture_profile_cannot_be_reused_as_native_scd1_apply_profile():
    config = _config(
        execution=ExecutionPolicy(
            engine=ExecutionEngine.DATAFLOW_GEN2,
            progress_owner=ProgressOwner.FABRIC_NATIVE,
            capability_profile=DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
            apply_engine=ExecutionEngine.DATAFLOW_GEN2,
            apply_capability_profile=DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
        )
    )

    with pytest.raises(UnsupportedExecutionCombination, match="does not certify apply strategy SCD1"):
        compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)


def test_generic_sql_profile_does_not_claim_upsert_apply_semantics():
    config = _config(
        apply=ApplyStrategy.UPSERT,
        execution=ExecutionPolicy(apply_engine=ExecutionEngine.SQL),
    )

    with pytest.raises(UnsupportedExecutionCombination, match="does not certify apply strategy UPSERT"):
        compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)


def test_custom_apply_requires_registered_domain_extension_reference():
    with pytest.raises(ValueError, match="CUSTOM apply execution requires extensions.apply"):
        _config(execution=ExecutionPolicy(apply_engine=ExecutionEngine.CUSTOM))

    config = _config(
        apply=ApplyStrategy.UPSERT,
        execution=ExecutionPolicy(apply_engine=ExecutionEngine.CUSTOM),
        extensions=ExtensionConfig(apply="vendor_current_state_v1"),
    )
    plan = compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)

    assert plan.apply_engine is ExecutionEngine.CUSTOM
    assert [unit.unit_id for unit in plan.units] == [
        "capture",
        "framework_prepare",
        "apply",
        "framework_finalize",
    ]
    assert plan.units[2].execution_kind is ExecutionKind.CUSTOM
    assert plan.units[3].state_commit_boundary is True
