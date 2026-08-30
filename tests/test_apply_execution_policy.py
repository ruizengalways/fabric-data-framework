from sqlalchemy import create_engine, inspect, select

from fabric_data_framework.metadata.config import (
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
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
)
from fabric_data_framework.control_plane.schema import (
    PROMOTABLE_DEFINITION_TABLES,
    apply_baseline_schema,
    apply_execution_policy,
)
from fabric_data_framework.deployment.delivery import materialize_semantic_metadata
from fabric_data_framework.metadata.capabilities import (
    DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
)


def _config(*, apply_engine: ExecutionEngine = ExecutionEngine.SPARK) -> DatasetConfig:
    return DatasetConfig(
        dataset_id="erp.customer",
        source=SourceConfig(system="erp", object="dbo.Customer", connection_ref="erp_sql"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.SCD1,
            merge_key=("customer_id",),
            watermark=WatermarkConfig(column="modified_at", overlap_window_seconds=60),
            event_time_column="modified_at",
            version_column="source_version",
        ),
        orchestration=OrchestrationPolicy(execution_group="erp_current"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
        execution=ExecutionPolicy(
            engine=ExecutionEngine.DATAFLOW_GEN2,
            progress_owner=ProgressOwner.FABRIC_NATIVE,
            capability_profile=DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
            apply_engine=apply_engine,
        ),
    )


def test_apply_execution_policy_is_promotable_and_created_by_baseline_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")

    apply_baseline_schema(engine)

    assert "apply_execution_policy" in PROMOTABLE_DEFINITION_TABLES
    assert inspect(engine).has_table("apply_execution_policy")


def test_materialization_persists_apply_execution_independently_from_capture(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")

    materialize_semantic_metadata(
        engine,
        configs=(_config(),),
        domain="customer",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )

    with engine.connect() as connection:
        row = connection.execute(select(apply_execution_policy)).mappings().one()

    assert row["dataset_id"] == "erp.customer"
    assert row["execution_engine"] == "SPARK"
    assert row["capability_profile"] is None


def test_apply_execution_policy_materialization_is_idempotent_and_updates_definition(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")

    materialize_semantic_metadata(
        engine,
        configs=(_config(),),
        domain="customer",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )
    materialize_semantic_metadata(
        engine,
        configs=(_config(apply_engine=ExecutionEngine.AUTO),),
        domain="customer",
        domain_git_sha="b" * 40,
        framework_version="0.4.0",
    )

    with engine.connect() as connection:
        rows = connection.execute(select(apply_execution_policy)).mappings().all()

    assert len(rows) == 1
    assert rows[0]["execution_engine"] == "AUTO"
