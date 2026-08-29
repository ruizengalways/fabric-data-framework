from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, Table, create_engine, inspect, select

from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
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
from fabric_data_framework.contracts.execution_plan import ExecutionKind, compile_execution_plan
from fabric_data_framework.control_plane import (
    CONTROL_PLANE_SCHEMA_VERSION,
    apply_baseline_schema,
    current_schema_version,
    load_policy,
)
from fabric_data_framework.delivery import materialize_semantic_metadata


def _append_config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="events.order_event",
        source=SourceConfig(system="events", object="order_event"),
        target=TargetConfig(layer="silver", object="order_event"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.APPEND,
            append_identity=("source_system", "event_id"),
        ),
        orchestration=OrchestrationPolicy(execution_group="events_daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="row_accounting"),
    )


def test_append_metadata_requires_explicit_unique_identity():
    with pytest.raises(ValidationError, match="requires append_identity"):
        LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.APPEND,
        )
    with pytest.raises(ValidationError, match="append_identity columns must be unique"):
        LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.APPEND,
            append_identity=("event_id", "event_id"),
        )

    policy = _append_config().load
    assert policy.append_identity == ("source_system", "event_id")


def test_framework_spark_capability_and_execution_plan_certify_append():
    config = _append_config()
    plan = compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)

    assert plan.apply_strategy is ApplyStrategy.APPEND
    assert len(plan.units) == 1
    assert plan.units[0].execution_kind is ExecutionKind.SPARK_JOB_DEFINITION
    assert plan.units[0].state_commit_boundary is True


def test_append_identity_is_materialized_as_promotable_semantic_metadata():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    config = _append_config()

    materialize_semantic_metadata(
        engine,
        configs=(config,),
        domain="events",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )

    with engine.connect() as connection:
        row = connection.execute(
            select(load_policy).where(load_policy.c.dataset_id == config.dataset_id)
        ).mappings().one()

    assert row["append_identity"] == ["source_system", "event_id"]
    assert row["apply_strategy"] == "APPEND"


def test_control_plane_v3_migration_adds_append_identity_to_existing_v2_load_policy():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    old = MetaData()
    migration_history = Table(
        "schema_migration_history",
        old,
        Column("version", Integer, primary_key=True),
        Column("name", String(200), nullable=False),
        Column("applied_at", DateTime(timezone=True), nullable=False),
    )
    old_load_policy = Table(
        "load_policy",
        old,
        Column("dataset_id", String(255), primary_key=True),
        Column("capture_strategy", String(32), nullable=False),
        Column("apply_strategy", String(32), nullable=False),
        Column("business_key", JSON, nullable=False),
        Column("merge_key", JSON, nullable=False),
        Column("watermark_column", String(255), nullable=True),
        Column("watermark_tie_breaker", JSON, nullable=True),
        Column("watermark_overlap_seconds", Integer, nullable=False),
        Column("event_time_column", String(255), nullable=True),
        Column("tracked_columns", JSON, nullable=False),
        Column("delete_policy", String(64), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=True),
    )
    old.create_all(engine)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            migration_history.insert(),
            [
                {"version": 1, "name": "phase1_initial_control_plane_schema", "applied_at": now},
                {
                    "version": 2,
                    "name": "execution_policy_ordering_capture_receipt_recovery_and_cdc",
                    "applied_at": now,
                },
            ],
        )
        connection.execute(
            old_load_policy.insert().values(
                dataset_id="legacy.events",
                capture_strategy="FULL",
                apply_strategy="REPLACE",
                business_key=[],
                merge_key=[],
                watermark_column=None,
                watermark_tie_breaker=None,
                watermark_overlap_seconds=0,
                event_time_column=None,
                tracked_columns=[],
                delete_policy="IGNORE",
                created_at=now,
                updated_at=None,
            )
        )

    assert current_schema_version(engine) == 2
    assert apply_baseline_schema(engine) == CONTROL_PLANE_SCHEMA_VERSION == 4

    columns = {column["name"] for column in inspect(engine).get_columns("load_policy")}
    assert "append_identity" in columns
    with engine.connect() as connection:
        row = connection.execute(
            select(load_policy.c.append_identity).where(
                load_policy.c.dataset_id == "legacy.events"
            )
        ).one()
    assert row.append_identity == []
