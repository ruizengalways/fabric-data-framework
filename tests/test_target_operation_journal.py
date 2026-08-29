from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.control_plane import (
    CONTROL_PLANE_SCHEMA_VERSION,
    ENVIRONMENT_LOCAL_STATE_TABLES,
    apply_baseline_schema,
    dataset,
    table_names,
)
from fabric_data_framework.contracts.recovery import UnknownOutcomeResolution
from fabric_data_framework.target_operation_io import (
    TargetOperationVersionConflict,
    claim_target_operation,
    mark_target_operation_succeeded,
    mark_target_operation_unknown,
    read_target_operation_events,
    reconcile_target_operation,
)
from fabric_data_framework.target_operations import (
    TargetOperationAction,
    TargetOperationIntent,
    TargetOperationStatus,
    fingerprint_semantic_payload,
    resolution_for_target_operation,
)


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            dataset.insert().values(
                dataset_id="crm.customer",
                domain="crm",
                source_system="dynamics",
                source_object="account",
                target_layer="silver",
                target_object="customer",
                enabled_default=True,
                criticality="HIGH",
                execution_group="crm",
                config_schema_version=1,
                config_hash="a" * 64,
                domain_git_sha="b" * 40,
                framework_version="0.4.0",
                created_at=now,
                updated_at=None,
            )
        )
    return engine


def _intent(input_payload=None) -> TargetOperationIntent:
    payload = input_payload or {
        "capture_receipt": "receipt-42",
        "watermark": {"lower": "2026-08-28T00:00:00Z", "upper": "2026-08-29T00:00:00Z"},
    }
    return TargetOperationIntent(
        dataset_id="crm.customer",
        operation_kind="SCD1",
        target_reference="silver.customer",
        effective_config_hash="c" * 64,
        input_fingerprint=fingerprint_semantic_payload(payload),
    )


def test_control_plane_v4_owns_target_operation_state_and_events():
    engine = _engine()
    assert CONTROL_PLANE_SCHEMA_VERSION == 4
    assert "target_operation" in ENVIRONMENT_LOCAL_STATE_TABLES
    assert "target_operation_event" in ENVIRONMENT_LOCAL_STATE_TABLES
    assert "target_operation" in table_names()
    assert "target_operation_event" in table_names()
    assert apply_baseline_schema(engine) == 4


def test_operation_key_is_semantic_and_attempt_independent():
    first = _intent(
        {
            "snapshot_id": "2026-08-29",
            "manifest": ["part-2.parquet", "part-1.parquet"],
        }
    )
    same = _intent(
        {
            "manifest": ["part-2.parquet", "part-1.parquet"],
            "snapshot_id": "2026-08-29",
        }
    )
    different = _intent(
        {
            "snapshot_id": "2026-08-30",
            "manifest": ["part-2.parquet", "part-1.parquet"],
        }
    )

    assert first.operation_key == same.operation_key
    assert first.operation_key != different.operation_key


def test_unknown_commit_requires_reconciliation_before_safe_retry():
    engine = _engine()
    intent = _intent()
    first_run = uuid4()
    retry_run = uuid4()

    first = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=first_run,
        attempt=1,
    )
    assert first.action is TargetOperationAction.EXECUTE
    assert first.record.status is TargetOperationStatus.IN_PROGRESS
    assert first.record.version == 1

    reentry = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=retry_run,
        attempt=2,
    )
    assert reentry.action is TargetOperationAction.RECONCILE_REQUIRED
    assert reentry.record.owner_dataset_run_id == first_run

    unknown = mark_target_operation_unknown(
        engine,
        operation_key=intent.operation_key,
        expected_version=1,
        dataset_run_id=first_run,
        attempt=1,
        error_message="warehouse request timed out after submit",
    )
    assert unknown.status is TargetOperationStatus.UNKNOWN
    assert resolution_for_target_operation(unknown.status) is UnknownOutcomeResolution.UNRESOLVED

    still_blocked = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=retry_run,
        attempt=2,
    )
    assert still_blocked.action is TargetOperationAction.RECONCILE_REQUIRED

    not_committed = reconcile_target_operation(
        engine,
        operation_key=intent.operation_key,
        expected_version=2,
        resolution=UnknownOutcomeResolution.NOT_COMMITTED,
        dataset_run_id=retry_run,
        attempt=2,
        outcome_reference="warehouse-history:op-42:not-found",
    )
    assert not_committed.status is TargetOperationStatus.NOT_COMMITTED
    assert not_committed.version == 3

    safe_retry = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=retry_run,
        attempt=2,
    )
    assert safe_retry.action is TargetOperationAction.EXECUTE
    assert safe_retry.record.status is TargetOperationStatus.IN_PROGRESS
    assert safe_retry.record.version == 4
    assert safe_retry.record.owner_dataset_run_id == retry_run

    succeeded = mark_target_operation_succeeded(
        engine,
        operation_key=intent.operation_key,
        expected_version=4,
        dataset_run_id=retry_run,
        attempt=2,
        outcome_reference="delta-version:9182",
    )
    assert succeeded.status is TargetOperationStatus.SUCCEEDED
    assert succeeded.version == 5
    assert resolution_for_target_operation(succeeded.status) is UnknownOutcomeResolution.COMMITTED

    later_run = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=uuid4(),
        attempt=3,
    )
    assert later_run.action is TargetOperationAction.SKIP_SUCCEEDED
    assert later_run.record.version == 5

    events = read_target_operation_events(engine, intent.operation_key)
    assert [event.to_status for event in events] == [
        TargetOperationStatus.IN_PROGRESS,
        TargetOperationStatus.UNKNOWN,
        TargetOperationStatus.NOT_COMMITTED,
        TargetOperationStatus.IN_PROGRESS,
        TargetOperationStatus.SUCCEEDED,
    ]
    assert [event.version for event in events] == [1, 2, 3, 4, 5]


def test_unresolved_reconciliation_remains_fail_closed():
    engine = _engine()
    intent = _intent()
    dataset_run_id = uuid4()

    claim = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=dataset_run_id,
        attempt=1,
    )
    unknown = mark_target_operation_unknown(
        engine,
        operation_key=intent.operation_key,
        expected_version=claim.record.version,
        dataset_run_id=dataset_run_id,
        attempt=1,
    )
    unresolved = reconcile_target_operation(
        engine,
        operation_key=intent.operation_key,
        expected_version=unknown.version,
        resolution=UnknownOutcomeResolution.UNRESOLVED,
        dataset_run_id=dataset_run_id,
        attempt=1,
        error_message="provider cannot prove commit outcome",
    )

    assert unresolved.status is TargetOperationStatus.UNKNOWN
    assert unresolved.version == 3
    blocked = claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=uuid4(),
        attempt=2,
    )
    assert blocked.action is TargetOperationAction.RECONCILE_REQUIRED


def test_stale_writer_cannot_overwrite_newer_operation_state():
    engine = _engine()
    intent = _intent()
    dataset_run_id = uuid4()
    claim_target_operation(
        engine,
        intent=intent,
        dataset_run_id=dataset_run_id,
        attempt=1,
    )
    mark_target_operation_unknown(
        engine,
        operation_key=intent.operation_key,
        expected_version=1,
        dataset_run_id=dataset_run_id,
        attempt=1,
    )

    with pytest.raises(TargetOperationVersionConflict):
        mark_target_operation_succeeded(
            engine,
            operation_key=intent.operation_key,
            expected_version=1,
            dataset_run_id=dataset_run_id,
            attempt=1,
        )
