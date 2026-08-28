"""Logical relational control-plane schema and additive migration contract."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    inspect,
    select,
)
from sqlalchemy.engine import Engine


CONTROL_PLANE_SCHEMA_VERSION = 2
CONTROL_PLANE_MIGRATIONS = (
    (1, "phase1_initial_control_plane_schema"),
    (2, "execution_policy_ordering_capture_receipt_recovery_and_cdc"),
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _audit_columns() -> tuple[Column, Column]:
    return (
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=True),
    )


schema_migration_history = Table(
    "schema_migration_history",
    metadata,
    Column("version", Integer, primary_key=True),
    Column("name", String(200), nullable=False),
    Column("applied_at", DateTime(timezone=True), nullable=False),
)

dataset = Table(
    "dataset",
    metadata,
    Column("dataset_id", String(255), primary_key=True),
    Column("domain", String(128), nullable=False),
    Column("source_system", String(128), nullable=False),
    Column("source_object", String(512), nullable=False),
    Column("target_layer", String(64), nullable=False),
    Column("target_object", String(512), nullable=False),
    Column("enabled_default", Boolean, nullable=False),
    Column("criticality", String(32), nullable=False),
    Column("execution_group", String(128), nullable=False),
    Column("config_schema_version", Integer, nullable=False),
    Column("config_hash", String(64), nullable=False),
    Column("domain_git_sha", String(64), nullable=False),
    Column("framework_version", String(64), nullable=False),
    *_audit_columns(),
)

dataset_contract = Table(
    "dataset_contract",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("contract_version", Integer, primary_key=True),
    Column("schema_fingerprint", String(128), nullable=False),
    Column("compatibility_policy", String(64), nullable=False),
    Column("definition", JSON, nullable=False),
    *_audit_columns(),
)

load_policy = Table(
    "load_policy",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
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
    *_audit_columns(),
)

ordering_policy = Table(
    "ordering_policy",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("event_time_column", String(255), nullable=True),
    Column("version_column", String(255), nullable=True),
    Column("sequence_column", String(255), nullable=True),
    *_audit_columns(),
)

execution_policy = Table(
    "execution_policy",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("execution_engine", String(64), nullable=False),
    Column("progress_owner", String(64), nullable=False),
    Column("capability_profile", String(255), nullable=True),
    Column("extensions", JSON, nullable=False),
    *_audit_columns(),
)

apply_execution_policy = Table(
    "apply_execution_policy",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("execution_engine", String(64), nullable=False),
    Column("capability_profile", String(255), nullable=True),
    *_audit_columns(),
)

orchestration_policy = Table(
    "orchestration_policy",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("execution_group", String(128), nullable=False),
    Column("criticality", String(32), nullable=False),
    Column("dependencies", JSON, nullable=False),
    Column("priority", Integer, nullable=False),
    Column("retry_count", Integer, nullable=False),
    Column("timeout_seconds", Integer, nullable=False),
    Column("batch_size", Integer, nullable=False),
    Column("max_concurrency", Integer, nullable=False),
    *_audit_columns(),
)

data_quality_policy = Table(
    "data_quality_policy",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("policy_name", String(128), nullable=False),
    Column("quarantine_policy", String(128), nullable=False),
    Column("definition", JSON, nullable=True),
    *_audit_columns(),
)

reconciliation_policy = Table(
    "reconciliation_policy",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("policy_name", String(128), nullable=False),
    Column("required_for_state_commit", Boolean, nullable=False),
    Column("definition", JSON, nullable=True),
    *_audit_columns(),
)

runtime_override = Table(
    "runtime_override",
    metadata,
    Column("override_id", String(36), primary_key=True),
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), nullable=False),
    Column("field_name", String(128), nullable=False),
    Column("value_json", JSON, nullable=False),
    Column("reason", Text, nullable=False),
    Column("requested_by", String(255), nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=False),
    Column("valid_to", DateTime(timezone=True), nullable=True),
    Column("precedence", Integer, nullable=False),
    Column("enabled", Boolean, nullable=False),
    *_audit_columns(),
)

watermark = Table(
    "watermark",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("committed_value", JSON, nullable=True),
    Column("committed_tie_breaker", JSON, nullable=True),
    Column("committed_dataset_run_id", String(36), nullable=True),
    Column("version", Integer, nullable=False),
    *_audit_columns(),
)

cdc_checkpoint = Table(
    "cdc_checkpoint",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("positions", JSON, nullable=False),
    Column("committed_dataset_run_id", String(36), nullable=False),
    Column("version", Integer, nullable=False),
    *_audit_columns(),
)

dataset_state = Table(
    "dataset_state",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("state_version", Integer, nullable=False),
    Column("state_json", JSON, nullable=False),
    Column("last_successful_dataset_run_id", String(36), nullable=True),
    *_audit_columns(),
)

dataset_lease = Table(
    "dataset_lease",
    metadata,
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), primary_key=True),
    Column("lease_owner", String(255), nullable=False),
    Column("dataset_run_id", String(36), nullable=False),
    Column("lease_version", Integer, nullable=False),
    Column("acquired_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

pipeline_run = Table(
    "pipeline_run",
    metadata,
    Column("pipeline_run_id", String(36), primary_key=True),
    Column("environment", String(32), nullable=False),
    Column("domain", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("run_mode", String(32), nullable=False),
    Column("domain_git_sha", String(64), nullable=False),
    Column("framework_version", String(64), nullable=False),
    Column("config_bundle_hash", String(64), nullable=False),
    Column("deployment_id", String(36), nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
)

dataset_run = Table(
    "dataset_run",
    metadata,
    Column("dataset_run_id", String(36), primary_key=True),
    Column("pipeline_run_id", String(36), ForeignKey("pipeline_run.pipeline_run_id"), nullable=False),
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("effective_config_hash", String(64), nullable=False),
    Column("rows_read", Integer, nullable=True),
    Column("rows_accepted", Integer, nullable=True),
    Column("rows_quarantined", Integer, nullable=True),
    Column("rows_filtered", Integer, nullable=True),
    Column("rows_inserted", Integer, nullable=True),
    Column("rows_updated", Integer, nullable=True),
    Column("rows_deleted", Integer, nullable=True),
    Column("error_code", String(128), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("retryable", Boolean, nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
)

capture_receipt = Table(
    "capture_receipt",
    metadata,
    Column("capture_receipt_id", String(36), primary_key=True),
    Column("dataset_run_id", String(36), nullable=False),
    Column("dataset_id", String(255), nullable=False),
    Column("capture_strategy", String(32), nullable=False),
    Column("execution_engine", String(64), nullable=False),
    Column("progress_owner", String(64), nullable=False),
    Column("native_run_id", String(512), nullable=True),
    Column("source_reference", String(1024), nullable=True),
    Column("landing_reference", String(1024), nullable=False),
    Column("rows_read", Integer, nullable=False),
    Column("rows_written", Integer, nullable=False),
    Column("source_lower_bound", JSON, nullable=True),
    Column("source_upper_bound", JSON, nullable=True),
    Column("snapshot_id", String(512), nullable=True),
    Column("complete_snapshot", Boolean, nullable=True),
    Column("external_checkpoint_reference", String(2048), nullable=True),
    Column("schema_version", String(255), nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

step_run = Table(
    "step_run",
    metadata,
    Column("step_run_id", String(36), primary_key=True),
    Column("dataset_run_id", String(36), ForeignKey("dataset_run.dataset_run_id"), nullable=False),
    Column("step_name", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("details", JSON, nullable=True),
)

reconciliation_result = Table(
    "reconciliation_result",
    metadata,
    Column("reconciliation_id", String(36), primary_key=True),
    Column("dataset_run_id", String(36), ForeignKey("dataset_run.dataset_run_id"), nullable=False),
    Column("dataset_id", String(255), nullable=False),
    Column("policy_name", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("metrics", JSON, nullable=False),
    Column("blocks_state_advance", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

quarantine_batch = Table(
    "quarantine_batch",
    metadata,
    Column("quarantine_id", String(36), primary_key=True),
    Column("dataset_run_id", String(36), ForeignKey("dataset_run.dataset_run_id"), nullable=False),
    Column("dataset_id", String(255), nullable=False),
    Column("scope", String(32), nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("reason_code", String(128), nullable=False),
    Column("reason_detail", Text, nullable=True),
    Column("source_reference", String(1024), nullable=True),
    Column("replayed_by_dataset_run_id", String(36), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

schema_change = Table(
    "schema_change",
    metadata,
    Column("schema_change_id", String(36), primary_key=True),
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), nullable=False),
    Column("dataset_run_id", String(36), nullable=True),
    Column("observed_fingerprint", String(128), nullable=False),
    Column("expected_fingerprint", String(128), nullable=True),
    Column("classification", String(64), nullable=False),
    Column("details", JSON, nullable=True),
    Column("observed_at", DateTime(timezone=True), nullable=False),
)

reprocess_request = Table(
    "reprocess_request",
    metadata,
    Column("reprocess_request_id", String(36), primary_key=True),
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), nullable=False),
    Column("run_mode", String(32), nullable=False),
    Column("reason", Text, nullable=False),
    Column("requested_by", String(255), nullable=False),
    Column("original_pipeline_run_id", String(36), nullable=True),
    Column("original_dataset_run_id", String(36), nullable=True),
    Column("range_json", JSON, nullable=True),
    Column("status", String(32), nullable=False),
    *_audit_columns(),
)

dataset_attempt_lineage = Table(
    "dataset_attempt_lineage",
    metadata,
    Column("dataset_run_id", String(36), primary_key=True),
    Column("dataset_id", String(255), ForeignKey("dataset.dataset_id"), nullable=False),
    Column("root_dataset_run_id", String(36), nullable=False),
    Column("previous_dataset_run_id", String(36), nullable=True),
    Column("attempt", Integer, nullable=False),
    Column("run_mode", String(32), nullable=False),
    Column(
        "reprocess_request_id",
        String(36),
        ForeignKey("reprocess_request.reprocess_request_id"),
        nullable=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

deployment_history = Table(
    "deployment_history",
    metadata,
    Column("deployment_id", String(36), primary_key=True),
    Column("environment", String(32), nullable=False),
    Column("domain", String(128), nullable=False),
    Column("domain_release_version", String(64), nullable=False),
    Column("domain_git_sha", String(64), nullable=False),
    Column("framework_version", String(64), nullable=False),
    Column("config_bundle_hash", String(64), nullable=False),
    Column("control_plane_schema_version", Integer, nullable=False),
    Column("fabric_item_manifest_version", String(64), nullable=False),
    Column("deployment_mechanism", String(64), nullable=False),
    Column("ci_provider", String(64), nullable=False),
    Column("build_id", String(255), nullable=False),
    Column("initiated_by", String(255), nullable=False),
    Column("approved_by", String(255), nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("status", String(32), nullable=False),
    Column("previous_deployment_id", String(36), nullable=True),
)

PROMOTABLE_DEFINITION_TABLES = frozenset(
    {
        "dataset",
        "dataset_contract",
        "load_policy",
        "ordering_policy",
        "execution_policy",
        "apply_execution_policy",
        "orchestration_policy",
        "data_quality_policy",
        "reconciliation_policy",
    }
)
ENVIRONMENT_LOCAL_STATE_TABLES = frozenset(
    {
        "schema_migration_history",
        "runtime_override",
        "watermark",
        "cdc_checkpoint",
        "dataset_state",
        "dataset_lease",
        "pipeline_run",
        "dataset_run",
        "dataset_attempt_lineage",
        "capture_receipt",
        "step_run",
        "reconciliation_result",
        "quarantine_batch",
        "schema_change",
        "reprocess_request",
        "deployment_history",
    }
)


def table_names() -> frozenset[str]:
    return frozenset(metadata.tables)


def current_schema_version(engine: Engine) -> int:
    inspector = inspect(engine)
    if not inspector.has_table(schema_migration_history.name):
        return 0
    with engine.connect() as connection:
        versions = connection.execute(
            select(schema_migration_history.c.version)
        ).scalars().all()
    return max(versions, default=0)


def apply_baseline_schema(engine: Engine) -> int:
    """Idempotently create additive schema and record every missing migration."""

    metadata.create_all(engine, checkfirst=True)
    current = current_schema_version(engine)
    pending = [item for item in CONTROL_PLANE_MIGRATIONS if item[0] > current]
    if pending:
        now = datetime.now(timezone.utc)
        with engine.begin() as connection:
            for version, name in pending:
                connection.execute(
                    schema_migration_history.insert().values(
                        version=version,
                        name=name,
                        applied_at=now,
                    )
                )
    return CONTROL_PLANE_SCHEMA_VERSION


__all__ = [
    "CONTROL_PLANE_MIGRATIONS",
    "CONTROL_PLANE_SCHEMA_VERSION",
    "ENVIRONMENT_LOCAL_STATE_TABLES",
    "PROMOTABLE_DEFINITION_TABLES",
    "apply_baseline_schema",
    "apply_execution_policy",
    "capture_receipt",
    "cdc_checkpoint",
    "current_schema_version",
    "dataset_attempt_lineage",
    "execution_policy",
    "metadata",
    "ordering_policy",
    "reprocess_request",
    "table_names",
]
