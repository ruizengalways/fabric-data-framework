from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.config import ApplyStrategy, DatasetStatus, RunMode
from fabric_data_framework.contracts.recovery import UnknownOutcomeResolution
from fabric_data_framework.contracts.target_operation import (
    TargetOperationReconciliation,
    TargetOperationSpec,
    TargetOperationStatus,
)
from fabric_data_framework.recovery import (
    RetryPolicy,
    RetryableExecutionError,
    TargetOperationUnresolvedError,
    UnknownCommitOutcomeError,
    execute_target_operation_once,
    execute_target_operation_with_retry,
)
from fabric_data_framework.target_operation_io import RelationalTargetOperationJournal


class FakeRecoveryRepository:
    def __init__(self):
        self.dataset_runs = []
        self.lineages = []
        self.reprocess_requests = []

    def record_dataset_run(self, audit):
        self.dataset_runs.append(audit)

    def record_attempt_lineage(self, lineage):
        self.lineages.append(lineage)

    def record_reprocess_request(self, request):
        self.reprocess_requests.append(request)


def _spec() -> TargetOperationSpec:
    return TargetOperationSpec(
        dataset_id="crm.customer",
        run_mode=RunMode.NORMAL,
        apply_strategy=ApplyStrategy.UPSERT,
        target_reference="silver.crm_customer",
        effective_config_hash="a" * 64,
        mutation_scope_hash="b" * 64,
    )


def test_committed_operation_converges_without_second_mutation():
    journal = RelationalTargetOperationJournal(create_engine("sqlite://"))
    spec = _spec()
    calls = []

    first = execute_target_operation_once(
        journal=journal,
        spec=spec,
        dataset_run_id=uuid4(),
        execute_mutation=lambda _entry: calls.append("write") or "ok",
    )
    second = execute_target_operation_once(
        journal=journal,
        spec=spec,
        dataset_run_id=uuid4(),
        execute_mutation=lambda _entry: calls.append("duplicate") or "bad",
    )

    assert first.value == "ok"
    assert first.operation.status is TargetOperationStatus.COMMITTED
    assert second.value is None
    assert second.mutation_executed is False
    assert second.converged_without_reexecution is True
    assert calls == ["write"]


def test_retryable_not_committed_failure_retries_same_operation_key():
    journal = RelationalTargetOperationJournal(create_engine("sqlite://"))
    repository = FakeRecoveryRepository()
    spec = _spec()
    operation_keys = []
    dataset_run_ids = []

    def mutate(context, entry):
        operation_keys.append(entry.operation_key)
        dataset_run_ids.append(context.dataset_run_id)
        if len(operation_keys) == 1:
            raise RetryableExecutionError("warehouse busy", error_code="WAREHOUSE_BUSY")
        return "done"

    result = execute_target_operation_with_retry(
        repository=repository,
        journal=journal,
        pipeline_run_id=uuid4(),
        spec=spec,
        execute_mutation=mutate,
        retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0),
    )

    assert operation_keys == [spec.operation_key, spec.operation_key]
    assert dataset_run_ids[0] != dataset_run_ids[1]
    assert result.attempts == 2
    assert result.value is not None
    assert result.value.value == "done"
    assert result.value.operation.status is TargetOperationStatus.COMMITTED
    assert result.value.operation.attempts_started == 2
    assert [item.status for item in repository.dataset_runs] == [
        DatasetStatus.FAILED,
        DatasetStatus.SUCCEEDED,
    ]


def test_unknown_outcome_without_reconciliation_blocks_blind_retry():
    journal = RelationalTargetOperationJournal(create_engine("sqlite://"))
    spec = _spec()

    with pytest.raises(TargetOperationUnresolvedError, match="uncertain commit outcome"):
        execute_target_operation_once(
            journal=journal,
            spec=spec,
            dataset_run_id=uuid4(),
            execute_mutation=lambda _entry: (_ for _ in ()).throw(
                UnknownCommitOutcomeError("timeout after commit request")
            ),
        )

    entry = journal.read(spec.operation_key)
    assert entry is not None
    assert entry.status is TargetOperationStatus.COMMIT_UNKNOWN
    assert entry.attempts_started == 1


def test_unknown_outcome_reconciled_committed_converges_successfully():
    journal = RelationalTargetOperationJournal(create_engine("sqlite://"))
    spec = _spec()
    calls = []

    result = execute_target_operation_once(
        journal=journal,
        spec=spec,
        dataset_run_id=uuid4(),
        execute_mutation=lambda _entry: calls.append("write")
        or (_ for _ in ()).throw(UnknownCommitOutcomeError("lost response")),
        reconcile_unknown=lambda _entry: TargetOperationReconciliation(
            resolution=UnknownOutcomeResolution.COMMITTED,
            evidence_reference="delta-version:88",
        ),
    )

    assert calls == ["write"]
    assert result.operation.status is TargetOperationStatus.COMMITTED
    assert result.operation.outcome_reference == "delta-version:88"
    assert result.unknown_outcome_resolution is UnknownOutcomeResolution.COMMITTED
    assert result.mutation_executed is True


def test_unknown_outcome_reconciled_not_committed_retries_same_operation():
    journal = RelationalTargetOperationJournal(create_engine("sqlite://"))
    repository = FakeRecoveryRepository()
    spec = _spec()
    calls = []
    reconciliations = []

    def mutate(_context, entry):
        calls.append(entry.operation_key)
        if len(calls) == 1:
            raise UnknownCommitOutcomeError("lost response")
        return "done"

    def reconcile(_context, _entry):
        reconciliations.append("checked")
        return TargetOperationReconciliation(
            resolution=UnknownOutcomeResolution.NOT_COMMITTED,
            evidence_reference="target-query:not-found",
        )

    result = execute_target_operation_with_retry(
        repository=repository,
        journal=journal,
        pipeline_run_id=uuid4(),
        spec=spec,
        execute_mutation=mutate,
        reconcile_unknown=reconcile,
        retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0),
    )

    assert calls == [spec.operation_key, spec.operation_key]
    assert reconciliations == ["checked"]
    assert result.attempts == 2
    assert result.value is not None
    assert result.value.operation.status is TargetOperationStatus.COMMITTED
    assert result.value.operation.attempts_started == 2


def test_preexisting_in_progress_is_reconciled_before_any_reexecution():
    journal = RelationalTargetOperationJournal(create_engine("sqlite://"))
    spec = _spec()
    previous_run = uuid4()
    prepared = journal.reserve(spec, dataset_run_id=previous_run)
    journal.transition(
        operation_key=spec.operation_key,
        expected_version=prepared.version,
        status=TargetOperationStatus.IN_PROGRESS,
        dataset_run_id=previous_run,
    )
    calls = []

    result = execute_target_operation_once(
        journal=journal,
        spec=spec,
        dataset_run_id=uuid4(),
        execute_mutation=lambda _entry: calls.append("should-not-run"),
        reconcile_unknown=lambda _entry: TargetOperationReconciliation(
            resolution=UnknownOutcomeResolution.COMMITTED,
            evidence_reference="target:existing-commit",
        ),
    )

    assert calls == []
    assert result.mutation_executed is False
    assert result.converged_without_reexecution is True
    assert result.operation.status is TargetOperationStatus.COMMITTED


def test_unclassified_exception_is_treated_as_unknown_target_outcome():
    journal = RelationalTargetOperationJournal(create_engine("sqlite://"))
    spec = _spec()

    with pytest.raises(TargetOperationUnresolvedError):
        execute_target_operation_once(
            journal=journal,
            spec=spec,
            dataset_run_id=uuid4(),
            execute_mutation=lambda _entry: (_ for _ in ()).throw(RuntimeError("socket reset")),
        )

    entry = journal.read(spec.operation_key)
    assert entry is not None
    assert entry.status is TargetOperationStatus.COMMIT_UNKNOWN
    assert entry.last_error_code == "UNCLASSIFIED_TARGET_MUTATION_EXCEPTION"
