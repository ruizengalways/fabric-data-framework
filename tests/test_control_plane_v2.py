from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, select

from fabric_data_framework.config import (
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
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.control_plane.schema import (
    CONTROL_PLANE_SCHEMA_VERSION,
    ENVIRONMENT_LOCAL_STATE_TABLES,
    PROMOTABLE_DEFINITION_TABLES,
    capture_receipt,
    current_schema_version,
    execution_policy,
    ordering_policy,
    schema_migration_history,
)
from fabric_data_framework.control_plane.io import record_capture_receipt
from fabric_data_framework.contracts.capture_receipt import CaptureReceipt
from fabric_data_framework.delivery import materialize_semantic_metadata


def _config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="erp.order",
        source=SourceConfig(system="erp", object="dbo.Order", connection_ref="erp_sql"),
        target=TargetConfig(layer="silver", object="order"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.CDC,
            apply_strategy=ApplyStrategy.UPSERT,
            merge_key=("tenant_id", "order_id"),
            event_time_column="event_ts",
            version_column="source_version",
            sequence_column="source_lsn",
        ),
        orchestration=OrchestrationPolicy(execution_group="erp_cdc"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="count_and_key"),
        execution=ExecutionPolicy(
            engine=ExecutionEngine.EXTERNAL_CDC,
            progress_owner=ProgressOwner.EXTERNAL,
            capability_profile="debezium_v1",
        ),
        extensions=ExtensionConfig(parser="debezium_envelope_v1"),
    )


def test_schema_v2_guarantees_survive_later_additive_migrations(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    materialize_semantic_metadata(
        engine,
        configs=(_config(),),
        domain="orders",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )

    assert current_schema_version(engine) == CONTROL_PLANE_SCHEMA_VERSION
    assert CONTROL_PLANE_SCHEMA_VERSION >= 2
    with engine.connect() as connection:
        migrations = connection.execute(
            select(schema_migration_history).order_by(schema_migration_history.c.version)
        ).mappings().all()
    versions = [item["version"] for item in migrations]
    assert versions[:2] == [1, 2]
    assert versions == list(range(1, CONTROL_PLANE_SCHEMA_VERSION + 1))
    assert "execution_policy" in PROMOTABLE_DEFINITION_TABLES
    assert "ordering_policy" in PROMOTABLE_DEFINITION_TABLES
    assert "capture_receipt" in ENVIRONMENT_LOCAL_STATE_TABLES


def test_materialization_persists_engine_progress_extensions_and_ordering(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    materialize_semantic_metadata(
        engine,
        configs=(_config(),),
        domain="orders",
        domain_git_sha="b" * 40,
        framework_version="0.4.0",
    )

    with engine.connect() as connection:
        execution = connection.execute(select(execution_policy)).mappings().one()
        ordering = connection.execute(select(ordering_policy)).mappings().one()

    assert execution["execution_engine"] == "EXTERNAL_CDC"
    assert execution["progress_owner"] == "EXTERNAL"
    assert execution["capability_profile"] == "debezium_v1"
    assert execution["extensions"]["parser"] == "debezium_envelope_v1"
    assert ordering["event_time_column"] == "event_ts"
    assert ordering["version_column"] == "source_version"
    assert ordering["sequence_column"] == "source_lsn"


def test_capture_receipt_is_append_only_relational_evidence(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    materialize_semantic_metadata(
        engine,
        configs=(_config(),),
        domain="orders",
        domain_git_sha="c" * 40,
        framework_version="0.4.0",
    )
    receipt = CaptureReceipt(
        dataset_run_id=uuid4(),
        dataset_id="erp.order",
        capture_strategy=CaptureStrategy.CDC,
        execution_engine=ExecutionEngine.EXTERNAL_CDC,
        progress_owner=ProgressOwner.EXTERNAL,
        native_run_id="consumer-run-42",
        landing_reference="bronze.erp_order",
        rows_read=11,
        rows_written=11,
        external_checkpoint_reference="orders:partition=0:offset=123",
        source_lower_bound=100,
        source_upper_bound=123,
        started_at=datetime(2026, 8, 28, 12, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 28, 12, 1, tzinfo=timezone.utc),
    )

    record_capture_receipt(engine, receipt)
    with engine.connect() as connection:
        row = connection.execute(select(capture_receipt)).mappings().one()
    assert row["native_run_id"] == "consumer-run-42"
    assert row["progress_owner"] == "EXTERNAL"
    assert row["source_upper_bound"] == 123

    try:
        record_capture_receipt(engine, receipt)
    except ValueError as exc:
        assert "already recorded" in str(exc)
    else:
        raise AssertionError("capture receipt overwrite must be refused")
