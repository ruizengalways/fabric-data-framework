from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect

from fabric_data_framework.config import ApplyStrategy, RunMode
from fabric_data_framework.contracts.target_operation import (
    InvalidTargetOperationTransition,
    TargetOperationSpec,
    TargetOperationStatus,
)
from fabric_data_framework.control_plane import (
    CONTROL_PLANE_SCHEMA_VERSION,
    ENVIRONMENT_LOCAL_STATE_TABLES,
    apply_baseline_schema,
    current_schema_version,
    schema_migration_history,
    target_operation,
)
from fabric_data_framework.target_operation_io import (
    RelationalTargetOperationJournal,
    TargetOperationVersionConflict,
)


def _spec(**updates) -> TargetOperationSpec:
    values = {
        "dataset_id": "crm.customer",
        "run_mode": RunMode.NORMAL,
        "apply_strategy": ApplyStrategy.SCD1,
        "target_reference": "silver.crm_customer",
        "effective_config_hash": "a" * 64,
        "mutation_scope_hash": "b" * 64,
    }
    values.update(updates)
    return TargetOperationSpec(**values)


def test_operation_key_is_stable_across_attempts_and_sensitive_to_semantics():
    base = _spec()
    assert base.operation_key == _spec().operation_key
    assert len(base.operation_key) == 64
    assert base.operation_key != _spec(mutation_scope_hash="c" * 64).operation_key
    assert base.operation_key != _spec(target_reference="silver.other").operation_key
    assert base.operation_key != _spec(apply_strategy=ApplyStrategy.SCD2).operation_key
    assert base.operation_key != _spec(run_mode=RunMode.FULL_REBUILD).operation_key


def test_v4_control_plane_adds_environment_local_target_operation_table():
    engine = create_engine("sqlite://")
    schema_migration_history.create(engine)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            schema_migration_history.insert(),
            [
                {"version": 1, "name": "v1", "applied_at": now},
                {"version": 2, "name": "v2", "applied_at": now},
                {"version": 3, "name": "v3", "applied_at": now},
            ],
        )

    assert current_schema_version(engine) == 3
    assert apply_baseline_schema(engine) == 4
    assert CONTROL_PLANE_SCHEMA_VERSION == 4
    assert current_schema_version(engine) == 4
    assert inspect(engine).has_table(target_operation.name)
    assert "target_operation" in ENVIRONMENT_LOCAL_STATE_TABLES


def test_reserve_is_idempotent_and_persists_across_journal_instances():
    engine = create_engine("sqlite://")
    first_journal = RelationalTargetOperationJournal(engine)
    spec = _spec()
    first_run = uuid4()
    second_run = uuid4()

    first = first_journal.reserve(spec, dataset_run_id=first_run)
    repeated = first_journal.reserve(spec, dataset_run_id=second_run)
    reloaded = RelationalTargetOperationJournal(engine).read(spec.operation_key)

    assert first == repeated == reloaded
    assert first.status is TargetOperationStatus.PREPARED
    assert first.first_dataset_run_id == first_run
    assert first.last_dataset_run_id == first_run
    assert first.attempts_started == 0
    assert first.version == 1


def test_lifecycle_allows_retry_only_after_not_committed_and_counts_attempts():
    engine = create_engine("sqlite://")
    journal = RelationalTargetOperationJournal(engine)
    spec = _spec()
    run1 = uuid4()
    run2 = uuid4()

    prepared = journal.reserve(spec, dataset_run_id=run1)
    started1 = journal.transition(
        operation_key=spec.operation_key,
        expected_version=prepared.version,
        status=TargetOperationStatus.IN_PROGRESS,
        dataset_run_id=run1,
    )
    not_committed = journal.transition(
        operation_key=spec.operation_key,
        expected_version=started1.version,
        status=TargetOperationStatus.NOT_COMMITTED,
        dataset_run_id=run1,
        outcome_reference="reconcile:not-committed:1",
    )
    started2 = journal.transition(
        operation_key=spec.operation_key,
        expected_version=not_committed.version,
        status=TargetOperationStatus.IN_PROGRESS,
        dataset_run_id=run2,
    )
    committed = journal.transition(
        operation_key=spec.operation_key,
        expected_version=started2.version,
        status=TargetOperationStatus.COMMITTED,
        dataset_run_id=run2,
        outcome_reference="target:commit:42",
    )

    assert started1.attempts_started == 1
    assert started2.attempts_started == 2
    assert committed.status is TargetOperationStatus.COMMITTED
    assert committed.attempts_started == 2
    assert committed.last_dataset_run_id == run2
    assert committed.outcome_reference == "target:commit:42"
    assert committed.committed_at is not None


def test_stale_version_and_terminal_reexecution_fail_closed():
    engine = create_engine("sqlite://")
    journal = RelationalTargetOperationJournal(engine)
    spec = _spec()
    run_id = uuid4()
    prepared = journal.reserve(spec, dataset_run_id=run_id)
    started = journal.transition(
        operation_key=spec.operation_key,
        expected_version=prepared.version,
        status=TargetOperationStatus.IN_PROGRESS,
        dataset_run_id=run_id,
    )

    with pytest.raises(TargetOperationVersionConflict, match="expected version"):
        journal.transition(
            operation_key=spec.operation_key,
            expected_version=prepared.version,
            status=TargetOperationStatus.NOT_COMMITTED,
            dataset_run_id=run_id,
        )

    committed = journal.transition(
        operation_key=spec.operation_key,
        expected_version=started.version,
        status=TargetOperationStatus.COMMITTED,
        dataset_run_id=run_id,
    )
    with pytest.raises(InvalidTargetOperationTransition, match="COMMITTED -> IN_PROGRESS"):
        journal.transition(
            operation_key=spec.operation_key,
            expected_version=committed.version,
            status=TargetOperationStatus.IN_PROGRESS,
            dataset_run_id=uuid4(),
        )
