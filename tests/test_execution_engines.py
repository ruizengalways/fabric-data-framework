from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
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
from fabric_data_framework.contracts.capture_receipt import CaptureReceipt
from fabric_data_framework.contracts.execution_plan import (
    ExecutionKind,
    compile_execution_plan,
)
from fabric_data_framework.extensions import (
    ExtensionKind,
    ExtensionNotFoundError,
    ExtensionRegistrationError,
    ExtensionRegistry,
)
from fabric_data_framework.metadata import (
    DEFAULT_CAPABILITY_REGISTRY,
    UnsupportedExecutionCombination,
)
from fabric_data_framework.metadata.capabilities import (
    DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
)


def _config(
    *,
    capture: CaptureStrategy = CaptureStrategy.FULL,
    apply: ApplyStrategy = ApplyStrategy.REPLACE,
    engine: ExecutionEngine = ExecutionEngine.AUTO,
    progress_owner: ProgressOwner = ProgressOwner.FRAMEWORK,
    capability_profile: str | None = None,
    watermark: WatermarkConfig | None = None,
    extensions: ExtensionConfig | None = None,
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id="erp.customer",
        source=SourceConfig(system="erp", object="dbo.Customer", connection_ref="erp_sql"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=capture,
            apply_strategy=apply,
            merge_key=("customer_id",)
            if apply in {
                ApplyStrategy.UPSERT,
                ApplyStrategy.SCD1,
                ApplyStrategy.SCD2,
                ApplyStrategy.SNAPSHOT_DIFF,
            }
            else (),
            business_key=("customer_id",) if apply is ApplyStrategy.SCD2 else (),
            watermark=watermark,
            event_time_column="modified_at" if apply in {ApplyStrategy.SCD1, ApplyStrategy.SCD2} else None,
        ),
        orchestration=OrchestrationPolicy(
            execution_group="erp_daily",
            criticality=Criticality.HIGH,
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
        execution=ExecutionPolicy(
            engine=engine,
            progress_owner=progress_owner,
            capability_profile=capability_profile,
        ),
        extensions=extensions or ExtensionConfig(),
    )


def test_auto_execution_is_conservative_framework_spark_default():
    config = _config()
    assert DEFAULT_CAPABILITY_REGISTRY.validate(config) is ExecutionEngine.SPARK

    plan = compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)

    assert len(plan.units) == 1
    assert plan.units[0].execution_kind is ExecutionKind.SPARK_JOB_DEFINITION
    assert plan.units[0].state_commit_boundary is True


def test_capability_profile_requires_explicit_engine():
    config = _config(capability_profile=DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE)

    with pytest.raises(UnsupportedExecutionCombination, match="explicit execution engine"):
        DEFAULT_CAPABILITY_REGISTRY.validate(config)


def test_copy_job_full_is_native_capture_plus_framework_processing():
    config = _config(
        engine=ExecutionEngine.FABRIC_COPY_JOB,
        progress_owner=ProgressOwner.FABRIC_NATIVE,
    )
    plan = compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)

    assert [unit.execution_kind for unit in plan.units] == [
        ExecutionKind.FABRIC_COPY_JOB,
        ExecutionKind.SPARK_JOB_DEFINITION,
    ]
    assert plan.units[0].state_commit_boundary is False
    assert plan.units[1].state_commit_boundary is True


def test_copy_job_rejects_composite_watermark_when_profile_cannot_prove_ordering():
    config = _config(
        capture=CaptureStrategy.WATERMARK,
        apply=ApplyStrategy.UPSERT,
        engine=ExecutionEngine.FABRIC_COPY_JOB,
        progress_owner=ProgressOwner.FABRIC_NATIVE,
        watermark=WatermarkConfig(column="modified_at", tie_breaker=("customer_id",)),
    )

    with pytest.raises(UnsupportedExecutionCombination, match="composite WATERMARK"):
        DEFAULT_CAPABILITY_REGISTRY.validate(config)


def test_copy_job_accepts_native_watermark_with_overlap_and_native_progress():
    config = _config(
        capture=CaptureStrategy.WATERMARK,
        apply=ApplyStrategy.UPSERT,
        engine=ExecutionEngine.FABRIC_COPY_JOB,
        progress_owner=ProgressOwner.FABRIC_NATIVE,
        watermark=WatermarkConfig(column="modified_at", overlap_window_seconds=60),
    )
    assert DEFAULT_CAPABILITY_REGISTRY.validate(config) is ExecutionEngine.FABRIC_COPY_JOB


def test_dataflow_incremental_profile_can_land_for_framework_scd1():
    config = _config(
        capture=CaptureStrategy.WATERMARK,
        apply=ApplyStrategy.SCD1,
        engine=ExecutionEngine.DATAFLOW_GEN2,
        progress_owner=ProgressOwner.FABRIC_NATIVE,
        capability_profile=DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
        watermark=WatermarkConfig(column="modified_at", overlap_window_seconds=60),
    )

    assert DEFAULT_CAPABILITY_REGISTRY.validate(config) is ExecutionEngine.DATAFLOW_GEN2
    plan = compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)

    assert [unit.execution_kind for unit in plan.units] == [
        ExecutionKind.DATAFLOW_GEN2,
        ExecutionKind.SPARK_JOB_DEFINITION,
    ]
    assert plan.units[0].roles == (
        plan.units[0].roles[0],
        plan.units[0].roles[1],
    )
    assert ExecutionKind.SPARK_JOB_DEFINITION is plan.units[1].execution_kind
    assert plan.units[1].state_commit_boundary is True


def test_dataflow_incremental_profile_rejects_composite_watermark():
    config = _config(
        capture=CaptureStrategy.WATERMARK,
        apply=ApplyStrategy.SCD1,
        engine=ExecutionEngine.DATAFLOW_GEN2,
        progress_owner=ProgressOwner.FABRIC_NATIVE,
        capability_profile=DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
        watermark=WatermarkConfig(column="modified_at", tie_breaker=("customer_id",)),
    )

    with pytest.raises(UnsupportedExecutionCombination, match="composite WATERMARK"):
        DEFAULT_CAPABILITY_REGISTRY.validate(config)


def test_external_cdc_requires_external_progress_owner():
    bad = _config(
        capture=CaptureStrategy.CDC,
        apply=ApplyStrategy.UPSERT,
        engine=ExecutionEngine.EXTERNAL_CDC,
        progress_owner=ProgressOwner.FRAMEWORK,
    )
    with pytest.raises(UnsupportedExecutionCombination, match="progress owner"):
        DEFAULT_CAPABILITY_REGISTRY.validate(bad)

    good = bad.model_copy(
        update={
            "execution": ExecutionPolicy(
                engine=ExecutionEngine.EXTERNAL_CDC,
                progress_owner=ProgressOwner.EXTERNAL,
            )
        }
    )
    assert DEFAULT_CAPABILITY_REGISTRY.validate(good) is ExecutionEngine.EXTERNAL_CDC


def test_custom_execution_requires_declared_capture_extension():
    with pytest.raises(ValueError, match="CUSTOM execution requires"):
        _config(engine=ExecutionEngine.CUSTOM)

    config = _config(
        engine=ExecutionEngine.CUSTOM,
        extensions=ExtensionConfig(capture="vendor_feed_v1"),
    )
    assert config.extensions.capture == "vendor_feed_v1"


def test_capture_receipt_requires_full_snapshot_completeness_evidence():
    with pytest.raises(ValueError, match="snapshot_id"):
        CaptureReceipt(
            dataset_run_id=uuid4(),
            dataset_id="erp.country",
            capture_strategy=CaptureStrategy.FULL,
            execution_engine=ExecutionEngine.FABRIC_COPY_JOB,
            progress_owner=ProgressOwner.FABRIC_NATIVE,
            landing_reference="bronze.erp_country",
            rows_read=10,
            rows_written=10,
        )

    receipt = CaptureReceipt(
        dataset_run_id=uuid4(),
        dataset_id="erp.country",
        capture_strategy=CaptureStrategy.FULL,
        execution_engine=ExecutionEngine.FABRIC_COPY_JOB,
        progress_owner=ProgressOwner.FABRIC_NATIVE,
        native_run_id="copy-job-run-1",
        landing_reference="bronze.erp_country",
        rows_read=10,
        rows_written=10,
        snapshot_id="snapshot-1",
        complete_snapshot=True,
    )
    assert receipt.complete_snapshot is True


def test_capture_receipt_external_stateful_progress_requires_checkpoint_reference():
    with pytest.raises(ValueError, match="external_checkpoint_reference"):
        CaptureReceipt(
            dataset_run_id=uuid4(),
            dataset_id="erp.order",
            capture_strategy=CaptureStrategy.CDC,
            execution_engine=ExecutionEngine.EXTERNAL_CDC,
            progress_owner=ProgressOwner.EXTERNAL,
            landing_reference="bronze.erp_order",
            rows_read=5,
            rows_written=5,
        )

    receipt = CaptureReceipt(
        dataset_run_id=uuid4(),
        dataset_id="erp.order",
        capture_strategy=CaptureStrategy.CDC,
        execution_engine=ExecutionEngine.EXTERNAL_CDC,
        progress_owner=ProgressOwner.EXTERNAL,
        landing_reference="bronze.erp_order",
        rows_read=5,
        rows_written=5,
        external_checkpoint_reference="kafka:topic=orders;partition=0;offset=42",
        started_at=datetime(2026, 8, 28, 10, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 28, 10, 1, tzinfo=timezone.utc),
    )
    assert receipt.external_checkpoint_reference is not None


def test_extension_registry_uses_logical_names_and_rejects_duplicate_registration():
    registry = ExtensionRegistry()

    def handler(value):
        return value

    registry.register(ExtensionKind.TRANSFORM, "weird_feed_v1", handler)

    assert registry.resolve(ExtensionKind.TRANSFORM, "weird_feed_v1") is handler
    assert registry.factory(ExtensionKind.TRANSFORM, "weird_feed_v1") is handler

    with pytest.raises(ExtensionRegistrationError, match="already registered"):
        registry.register(ExtensionKind.TRANSFORM, "weird_feed_v1", handler)

    with pytest.raises(ExtensionNotFoundError, match="not registered"):
        registry.resolve(ExtensionKind.CAPTURE, "missing")


def test_extension_metadata_rejects_arbitrary_python_import_paths():
    with pytest.raises(ValueError):
        ExtensionConfig(transform="fabric_customer.extensions:run()")
