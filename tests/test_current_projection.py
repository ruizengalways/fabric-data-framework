from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select

from fabric_data_framework.adapters.cdc.delta_cdf import DeltaCDFChangeType, DeltaCDFRecord
from fabric_data_framework.apply.current_projection import (
    CurrentProjectionError,
    apply_current_projection,
    rebuild_current_projection,
)
from fabric_data_framework.contracts.current_projection import (
    CurrentProjectionConfig,
    CurrentProjectionHealthStatus,
    CurrentProjectionMode,
    MaterializedCurrentImplementation,
    evaluate_current_projection_health,
)
from fabric_data_framework.contracts.runtime import StateCommitGate
from fabric_data_framework.contracts.schema import LogicalType, SchemaContract, SchemaField
from fabric_data_framework.control_plane.current_projection import read_current_projection_health
from fabric_data_framework.control_plane.io import read_cdc_checkpoint
from fabric_data_framework.control_plane.schema import (
    CONTROL_PLANE_SCHEMA_VERSION,
    current_projection_policy,
    dataset_run,
)
from fabric_data_framework.deployment.current_projection import (
    compile_current_projection_deployment,
    validate_current_projection_bundle,
)
from fabric_data_framework.deployment.delivery import materialize_semantic_metadata
from fabric_data_framework.execution.current_projection import (
    CurrentProjectionExecutionError,
    InMemoryCurrentProjectionTarget,
    execute_delta_current_projection,
)
from fabric_data_framework.execution.plan_compiler import compile_execution_plan
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)


NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def _schema() -> SchemaContract:
    return SchemaContract(
        fields=(
            SchemaField(name="customer_id", logical_type=LogicalType.STRING, nullable=False),
            SchemaField(name="email", logical_type=LogicalType.STRING),
        )
    )


def _quality() -> DataQualityPolicy:
    return DataQualityPolicy(policy_name="standard", quarantine_policy="default")


def _reconciliation() -> ReconciliationPolicy:
    return ReconciliationPolicy(policy_name="standard")


def _history_config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="crm.customer_history",
        source=SourceConfig(system="crm", object="customer"),
        target=TargetConfig(layer="silver", object="customer_history"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.SCD2,
            business_key=("customer_id",),
            merge_key=("customer_id",),
            tracked_columns=("email",),
            event_time_column="changed_at",
            watermark={"column": "changed_at", "tie_breaker": ["customer_id"]},
        ),
        orchestration=OrchestrationPolicy(
            execution_group="crm",
            criticality=Criticality.HIGH,
        ),
        quality=_quality(),
        reconciliation=_reconciliation(),
        schema_contract=_schema(),
    )


def _projection_config(
    mode: CurrentProjectionMode,
    *,
    implementation: MaterializedCurrentImplementation = MaterializedCurrentImplementation.AUTO,
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id=f"crm.customer.current.{mode.value.lower()}",
        source=SourceConfig(system="framework_dataset", object="silver.customer_history"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.PROJECTION,
            apply_strategy=ApplyStrategy.CURRENT_PROJECTION,
            business_key=("customer_id",),
            merge_key=("customer_id",),
            delete_policy="DERIVE_FROM_HISTORY",
        ),
        current_projection=CurrentProjectionConfig(
            authoritative_history_dataset_id="crm.customer_history",
            mode=mode,
            materialized_implementation=implementation,
            lag_warning_versions=2,
            lag_error_versions=5,
        ),
        orchestration=OrchestrationPolicy(
            execution_group="crm",
            criticality=Criticality.HIGH,
            dependencies=("crm.customer_history",),
        ),
        quality=_quality(),
        reconciliation=_reconciliation(),
        schema_contract=_schema(),
    )


def test_projection_metadata_requires_explicit_derived_semantics():
    config = _projection_config(CurrentProjectionMode.VIEW)
    assert config.load.capture_strategy is CaptureStrategy.PROJECTION
    assert config.load.apply_strategy is ApplyStrategy.CURRENT_PROJECTION
    assert config.current_projection is not None

    payload = config.model_dump(mode="json")
    payload["load"]["delete_policy"] = "IGNORE"
    with pytest.raises(ValueError, match="DERIVE_FROM_HISTORY"):
        DatasetConfig.model_validate(payload)


def test_projection_bundle_requires_scd2_authority_and_matching_key():
    history = _history_config()
    projection = _projection_config(CurrentProjectionMode.VIEW)
    assert validate_current_projection_bundle((history, projection)) == ()

    bad = projection.model_copy(
        update={
            "load": projection.load.model_copy(
                update={"business_key": ("other",), "merge_key": ("other",)}
            )
        }
    )
    with pytest.raises(ValueError, match="business_key"):
        validate_current_projection_bundle((history, bad))


def test_mode1_compiles_stable_current_view_over_history():
    plan = compile_current_projection_deployment(_projection_config(CurrentProjectionMode.VIEW))
    assert plan.mode is CurrentProjectionMode.VIEW
    assert plan.create_or_replace_sql == (
        "CREATE OR REPLACE VIEW `silver`.`customer` AS "
        "SELECT `customer_id`, `email` FROM `silver`.`customer_history` "
        "WHERE `_framework_is_current` = true"
    )
    assert plan.refresh_sql is None
    assert plan.requires_incremental_runtime is False


def test_mode2_compiles_materialized_lake_view_and_marks_incremental_as_not_expected():
    plan = compile_current_projection_deployment(
        _projection_config(CurrentProjectionMode.MATERIALIZED)
    )
    assert plan.materialized_implementation is MaterializedCurrentImplementation.FABRIC_MATERIALIZED_LAKE_VIEW
    assert plan.create_or_replace_sql is not None
    assert plan.create_or_replace_sql.startswith(
        "CREATE OR REPLACE MATERIALIZED LAKE VIEW `silver`.`customer`"
    )
    assert plan.refresh_sql == "REFRESH MATERIALIZED LAKE VIEW `silver`.`customer`"
    assert "delta.enableChangeDataFeed" in (plan.enable_history_cdf_sql or "")
    assert plan.incremental_refresh_expected is False


def test_mode2_can_use_predictable_delta_table_full_refresh_without_changing_consumer_name():
    plan = compile_current_projection_deployment(
        _projection_config(
            CurrentProjectionMode.MATERIALIZED,
            implementation=MaterializedCurrentImplementation.DELTA_TABLE_REFRESH,
        )
    )
    assert plan.target_relation == "`silver`.`customer`"
    assert plan.refresh_sql == plan.create_or_replace_sql
    assert "CREATE OR REPLACE TABLE `silver`.`customer` USING DELTA" in (plan.refresh_sql or "")


def test_mode3_compiles_cdf_prerequisite_and_incremental_runtime_intent():
    config = _projection_config(CurrentProjectionMode.DELTA_PROJECTION)
    plan = compile_current_projection_deployment(config)
    assert plan.requires_incremental_runtime is True
    assert plan.create_or_replace_sql is None
    assert "delta.enableChangeDataFeed" in (plan.enable_history_cdf_sql or "")

    execution = compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)
    assert [unit.unit_id for unit in execution.units] == ["current_projection_incremental"]
    assert execution.units[0].state_commit_boundary is True


def test_view_and_materialized_plans_do_not_claim_framework_checkpoint_state():
    for mode in (CurrentProjectionMode.VIEW, CurrentProjectionMode.MATERIALIZED):
        config = _projection_config(mode)
        plan = compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)
        assert [unit.unit_id for unit in plan.units] == ["current_projection_publish"]
        assert plan.units[0].state_commit_boundary is False


def test_current_projection_uses_history_as_truth_for_update_delete_and_retry():
    existing = (
        {"customer_id": "C1", "email": "old@example.test"},
        {"customer_id": "C2", "email": "deleted@example.test"},
    )
    history = (
        {
            "customer_id": "C1",
            "email": "old@example.test",
            "_framework_is_current": False,
        },
        {
            "customer_id": "C1",
            "email": "new@example.test",
            "_framework_is_current": True,
        },
        {
            "customer_id": "C2",
            "email": "deleted@example.test",
            "_framework_is_current": False,
        },
    )
    result = apply_current_projection(
        existing,
        history,
        business_key=("customer_id",),
        projected_columns=("customer_id", "email"),
        affected_keys=(("C1",), ("C2",)),
    )
    assert result.mutations.updated == 1
    assert result.mutations.deleted == 1
    assert result.rows == ({"customer_id": "C1", "email": "new@example.test"},)

    retry = apply_current_projection(
        result.rows,
        history,
        business_key=("customer_id",),
        projected_columns=("customer_id", "email"),
        affected_keys=(("C1",), ("C2",)),
    )
    assert retry.mutations.inserted == retry.mutations.updated == retry.mutations.deleted == 0


def test_projection_fails_closed_on_multiple_history_current_rows():
    history = (
        {"customer_id": "C1", "email": "a", "_framework_is_current": True},
        {"customer_id": "C1", "email": "b", "_framework_is_current": True},
    )
    with pytest.raises(CurrentProjectionError, match="more than one current row"):
        rebuild_current_projection(
            (),
            history,
            business_key=("customer_id",),
            projected_columns=("customer_id", "email"),
        )


def test_projection_comparison_preserves_business_value_types():
    existing = ({"customer_id": "C1", "email": Decimal("1")},)
    history = (
        {"customer_id": "C1", "email": "1", "_framework_is_current": True},
    )
    result = apply_current_projection(
        existing,
        history,
        business_key=("customer_id",),
        projected_columns=("customer_id", "email"),
        affected_keys=(("C1",),),
    )
    assert result.mutations.updated == 1
    assert result.rows[0]["email"] == "1"
    assert type(result.rows[0]["email"]) is str


def _cdf(version: int, customer_id: str, email: str) -> DeltaCDFRecord:
    return DeltaCDFRecord(
        change_type=DeltaCDFChangeType.UPDATE_POSTIMAGE,
        commit_version=version,
        commit_timestamp=NOW,
        data={"customer_id": customer_id, "email": email, "_framework_is_current": True},
    )


def _control_plane(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'projection.db'}")
    history = _history_config()
    projection = _projection_config(CurrentProjectionMode.DELTA_PROJECTION)
    materialize_semantic_metadata(
        engine,
        configs=(history, projection),
        domain="crm",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )
    return engine, projection


def test_mode3_commits_own_checkpoint_only_after_target_and_reconciliation(tmp_path):
    engine, projection = _control_plane(tmp_path)
    target = InMemoryCurrentProjectionTarget()
    run_id = uuid4()
    result = execute_delta_current_projection(
        control_plane_engine=engine,
        dataset_id=projection.dataset_id,
        dataset_run_id=run_id,
        table_reference=projection.source.object,
        business_key=("customer_id",),
        projected_columns=("customer_id", "email"),
        history_cdf_records=(_cdf(3, "C1", "new@example.test"),),
        history_rows_at_upper=(
            {"customer_id": "C1", "email": "new@example.test", "_framework_is_current": True},
        ),
        history_snapshot_version=3,
        earliest_available_version=1,
        latest_available_version=3,
        target=target,
        reconcile=lambda _: True,
    )
    assert result.upper_processed_version == 3
    assert result.affected_keys == 1
    assert target.read() == ({"customer_id": "C1", "email": "new@example.test"},)
    state = read_cdc_checkpoint(engine, projection.dataset_id)
    assert state is not None
    assert state.checkpoint.position_for(f"delta-cdf:{projection.source.object}")[0] == 3


def test_mode3_failed_reconciliation_does_not_advance_checkpoint_and_retry_is_idempotent(tmp_path):
    engine, projection = _control_plane(tmp_path)
    target = InMemoryCurrentProjectionTarget()
    kwargs = dict(
        control_plane_engine=engine,
        dataset_id=projection.dataset_id,
        table_reference=projection.source.object,
        business_key=("customer_id",),
        projected_columns=("customer_id", "email"),
        history_cdf_records=(_cdf(2, "C1", "x@example.test"),),
        history_rows_at_upper=(
            {"customer_id": "C1", "email": "x@example.test", "_framework_is_current": True},
        ),
        history_snapshot_version=2,
        earliest_available_version=1,
        latest_available_version=2,
        target=target,
    )
    with pytest.raises(CurrentProjectionExecutionError, match="reconciliation failed"):
        execute_delta_current_projection(
            dataset_run_id=uuid4(),
            reconcile=lambda _: False,
            **kwargs,
        )
    assert read_cdc_checkpoint(engine, projection.dataset_id) is None
    assert target.read() == ({"customer_id": "C1", "email": "x@example.test"},)

    retry = execute_delta_current_projection(
        dataset_run_id=uuid4(),
        reconcile=lambda _: True,
        **kwargs,
    )
    assert retry.mutations.inserted == retry.mutations.updated == retry.mutations.deleted == 0
    assert retry.upper_processed_version == 2


def test_mode3_requires_history_snapshot_exactly_at_frozen_upper_version(tmp_path):
    engine, projection = _control_plane(tmp_path)
    with pytest.raises(CurrentProjectionExecutionError, match="exact frozen upper"):
        execute_delta_current_projection(
            control_plane_engine=engine,
            dataset_id=projection.dataset_id,
            dataset_run_id=uuid4(),
            table_reference=projection.source.object,
            business_key=("customer_id",),
            projected_columns=("customer_id", "email"),
            history_cdf_records=(_cdf(2, "C1", "x@example.test"),),
            history_rows_at_upper=(
                {"customer_id": "C1", "email": "later@example.test", "_framework_is_current": True},
            ),
            history_snapshot_version=3,
            earliest_available_version=1,
            latest_available_version=2,
            target=InMemoryCurrentProjectionTarget(),
            reconcile=lambda _: True,
        )


def test_projection_health_is_derived_from_versions_not_a_second_state_store():
    healthy = evaluate_current_projection_health(
        dataset_id="crm.customer.current",
        history_latest_delta_version=108,
        processed_version=108,
    )
    assert healthy.projection_lag == 0
    assert healthy.status is CurrentProjectionHealthStatus.HEALTHY

    lagging = evaluate_current_projection_health(
        dataset_id="crm.customer.current",
        history_latest_delta_version=108,
        processed_version=105,
        lag_warning_versions=1,
        lag_error_versions=5,
    )
    assert lagging.projection_lag == 3
    assert lagging.status is CurrentProjectionHealthStatus.LAGGING


def test_projection_policy_is_promotable_metadata_and_health_reuses_existing_ops_tables(tmp_path):
    engine, projection = _control_plane(tmp_path)
    assert CONTROL_PLANE_SCHEMA_VERSION == 7
    with engine.connect() as connection:
        row = connection.execute(
            select(current_projection_policy).where(
                current_projection_policy.c.dataset_id == projection.dataset_id
            )
        ).mappings().one()
    assert row["mode"] == CurrentProjectionMode.DELTA_PROJECTION.value
    assert row["authoritative_history_dataset_id"] == "crm.customer_history"

    dataset_run_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            dataset_run.insert().values(
                dataset_run_id=str(dataset_run_id),
                pipeline_run_id=str(UUID(int=0)),
                dataset_id=projection.dataset_id,
                attempt=1,
                status=DatasetStatus.SUCCEEDED.value,
                effective_config_hash=projection.config_hash,
                rows_read=None,
                rows_accepted=None,
                rows_quarantined=None,
                rows_filtered=None,
                rows_inserted=None,
                rows_updated=None,
                rows_deleted=None,
                error_code=None,
                error_message=None,
                retryable=None,
                started_at=NOW,
                completed_at=NOW,
            )
        )
    # No CDC checkpoint yet: health is explicitly uninitialized rather than guessed.
    health = read_current_projection_health(
        engine,
        config=projection,
        history_latest_delta_version=8,
    )
    assert health.status is CurrentProjectionHealthStatus.UNINITIALIZED
    assert health.last_successful_projection_run_id == dataset_run_id
