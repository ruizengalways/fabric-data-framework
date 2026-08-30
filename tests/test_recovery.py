from uuid import uuid4

import pytest

from fabric_data_framework.metadata.config import DatasetStatus, RunMode
from fabric_data_framework.contracts.recovery import (
    DatasetAttemptLineage,
    ReprocessRequest,
    ReprocessRequestStatus,
    UnknownOutcomeResolution,
)
from fabric_data_framework.recovery import (
    FailureDisposition,
    PermanentExecutionError,
    RecoveryExhaustedError,
    RetryPolicy,
    RetryableExecutionError,
    UnknownCommitOutcomeError,
    UnknownOutcomeUnresolvedError,
    classify_failure,
    execute_with_retry,
)
from fabric_data_framework.control_plane.repository import InMemoryControlPlane


_CONFIG_HASH = "a" * 64


def test_reprocess_request_modes_validate_required_scope_and_authorization():
    original = uuid4()

    with pytest.raises(ValueError, match="cannot use NORMAL"):
        ReprocessRequest(
            dataset_id="erp.order",
            run_mode=RunMode.NORMAL,
            reason="not valid",
            requested_by="operator",
        )
    with pytest.raises(ValueError, match="RETRY request requires"):
        ReprocessRequest(
            dataset_id="erp.order",
            run_mode=RunMode.RETRY,
            reason="retry",
            requested_by="operator",
        )
    with pytest.raises(ValueError, match="lower and upper"):
        ReprocessRequest(
            dataset_id="erp.order",
            run_mode=RunMode.BACKFILL,
            reason="backfill",
            requested_by="operator",
            range_json={"lower": 10},
        )
    with pytest.raises(ValueError, match="quarantine_ids"):
        ReprocessRequest(
            dataset_id="erp.order",
            run_mode=RunMode.REPLAY,
            reason="replay",
            requested_by="operator",
        )
    with pytest.raises(ValueError, match="authoritative_reset"):
        ReprocessRequest(
            dataset_id="erp.order",
            run_mode=RunMode.FULL_REBUILD,
            reason="rebuild",
            requested_by="operator",
        )

    retry = ReprocessRequest(
        dataset_id="erp.order",
        run_mode=RunMode.RETRY,
        reason="retry transient failure",
        requested_by="operator",
        original_dataset_run_id=original,
    )
    backfill = ReprocessRequest(
        dataset_id="erp.order",
        run_mode=RunMode.BACKFILL,
        reason="repair source range",
        requested_by="operator",
        range_json={"lower": 10, "upper": 20},
    )
    replay = ReprocessRequest(
        dataset_id="erp.order",
        run_mode=RunMode.REPLAY,
        reason="replay quarantine",
        requested_by="operator",
        range_json={"quarantine_ids": [str(uuid4())]},
    )
    rebuild = ReprocessRequest(
        dataset_id="erp.order",
        run_mode=RunMode.FULL_REBUILD,
        reason="approved rebuild",
        requested_by="operator",
        range_json={"authoritative_reset": True},
    )

    assert retry.original_dataset_run_id == original
    assert backfill.range_json == {"lower": 10, "upper": 20}
    assert replay.run_mode is RunMode.REPLAY
    assert rebuild.run_mode is RunMode.FULL_REBUILD


def test_failure_classification_is_conservative():
    assert classify_failure(RetryableExecutionError("temporary")).disposition is (
        FailureDisposition.RETRYABLE
    )
    assert classify_failure(PermanentExecutionError("bad config")).disposition is (
        FailureDisposition.NON_RETRYABLE
    )
    assert classify_failure(UnknownCommitOutcomeError("timeout after write")).disposition is (
        FailureDisposition.UNKNOWN_OUTCOME
    )
    assert classify_failure(ValueError("unexpected")).disposition is (
        FailureDisposition.NON_RETRYABLE
    )


def test_retryable_failure_records_attempt1_failed_then_attempt2_success():
    repository = InMemoryControlPlane()
    pipeline_run_id = uuid4()
    seen = []
    delays = []

    def execute(context):
        seen.append(context)
        if context.attempt == 1:
            raise RetryableExecutionError("gateway temporarily unavailable", error_code="SOURCE_IO")
        return "ok"

    result = execute_with_retry(
        repository=repository,
        pipeline_run_id=pipeline_run_id,
        dataset_id="erp.order",
        effective_config_hash=_CONFIG_HASH,
        execute_attempt=execute,
        retry_policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=2),
        backoff=delays.append,
    )

    assert result.value == "ok"
    assert result.attempts == 2
    assert [item.attempt for item in repository.dataset_runs] == [1, 2]
    assert [item.status for item in repository.dataset_runs] == [
        DatasetStatus.FAILED,
        DatasetStatus.SUCCEEDED,
    ]
    assert repository.dataset_runs[0].retryable is True
    assert repository.dataset_runs[0].error_code == "SOURCE_IO"
    assert delays == [2]

    lineage = repository.lineage_for_root(result.root_dataset_run_id)
    assert [item.attempt for item in lineage] == [1, 2]
    assert lineage[0].root_dataset_run_id == lineage[0].dataset_run_id
    assert lineage[1].previous_dataset_run_id == lineage[0].dataset_run_id
    assert lineage[1].root_dataset_run_id == lineage[0].dataset_run_id


def test_permanent_failure_does_not_retry():
    repository = InMemoryControlPlane()
    calls = 0

    def execute(_context):
        nonlocal calls
        calls += 1
        raise PermanentExecutionError("semantic contract invalid", error_code="CONTRACT")

    with pytest.raises(PermanentExecutionError, match="semantic contract invalid"):
        execute_with_retry(
            repository=repository,
            pipeline_run_id=uuid4(),
            dataset_id="erp.order",
            effective_config_hash=_CONFIG_HASH,
            execute_attempt=execute,
            retry_policy=RetryPolicy(max_attempts=5),
        )

    assert calls == 1
    assert len(repository.dataset_runs) == 1
    assert repository.dataset_runs[0].retryable is False
    assert repository.dataset_runs[0].error_code == "CONTRACT"


def test_retryable_failure_exhaustion_is_explicit():
    repository = InMemoryControlPlane()

    def execute(_context):
        raise RetryableExecutionError("still unavailable")

    with pytest.raises(RecoveryExhaustedError, match="attempts exhausted") as exc_info:
        execute_with_retry(
            repository=repository,
            pipeline_run_id=uuid4(),
            dataset_id="erp.order",
            effective_config_hash=_CONFIG_HASH,
            execute_attempt=execute,
            retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0),
        )

    assert isinstance(exc_info.value.last_error, RetryableExecutionError)
    assert [item.retryable for item in repository.dataset_runs] == [True, False]


def test_unknown_commit_resolved_committed_converges_without_duplicate_write():
    repository = InMemoryControlPlane()
    calls = 0
    reconciliations = 0

    def execute(_context):
        nonlocal calls
        calls += 1
        raise UnknownCommitOutcomeError("response lost after target commit")

    def reconcile(_context, _exc):
        nonlocal reconciliations
        reconciliations += 1
        return UnknownOutcomeResolution.COMMITTED

    result = execute_with_retry(
        repository=repository,
        pipeline_run_id=uuid4(),
        dataset_id="erp.order",
        effective_config_hash=_CONFIG_HASH,
        execute_attempt=execute,
        retry_policy=RetryPolicy(max_attempts=3),
        resolve_unknown_outcome=reconcile,
    )

    assert calls == 1
    assert reconciliations == 1
    assert result.resolved_unknown_outcome is UnknownOutcomeResolution.COMMITTED
    assert repository.dataset_runs[0].status is DatasetStatus.SUCCEEDED


def test_unknown_commit_not_committed_is_reconciled_before_retry():
    repository = InMemoryControlPlane()
    events = []

    def execute(context):
        events.append(f"execute-{context.attempt}")
        if context.attempt == 1:
            raise UnknownCommitOutcomeError("write acknowledgement lost")
        return "recovered"

    def reconcile(context, _exc):
        events.append(f"reconcile-{context.attempt}")
        return UnknownOutcomeResolution.NOT_COMMITTED

    result = execute_with_retry(
        repository=repository,
        pipeline_run_id=uuid4(),
        dataset_id="erp.order",
        effective_config_hash=_CONFIG_HASH,
        execute_attempt=execute,
        retry_policy=RetryPolicy(max_attempts=2, initial_backoff_seconds=0),
        resolve_unknown_outcome=reconcile,
    )

    assert result.value == "recovered"
    assert events == ["execute-1", "reconcile-1", "execute-2"]
    assert repository.dataset_runs[0].error_code == "UNKNOWN_COMMIT_NOT_COMMITTED"
    assert repository.dataset_runs[0].retryable is True


def test_unknown_commit_unresolved_refuses_blind_retry():
    repository = InMemoryControlPlane()
    calls = 0

    def execute(_context):
        nonlocal calls
        calls += 1
        raise UnknownCommitOutcomeError("ambiguous target state")

    with pytest.raises(UnknownOutcomeUnresolvedError, match="refusing blind retry"):
        execute_with_retry(
            repository=repository,
            pipeline_run_id=uuid4(),
            dataset_id="erp.order",
            effective_config_hash=_CONFIG_HASH,
            execute_attempt=execute,
            retry_policy=RetryPolicy(max_attempts=5),
            resolve_unknown_outcome=lambda _context, _exc: UnknownOutcomeResolution.UNRESOLVED,
        )

    assert calls == 1
    assert repository.dataset_runs[0].retryable is False
    assert repository.dataset_runs[0].error_code == "UNKNOWN_COMMIT_UNRESOLVED"


def test_unknown_commit_without_reconciler_refuses_retry():
    repository = InMemoryControlPlane()

    with pytest.raises(UnknownOutcomeUnresolvedError, match="requires reconciliation"):
        execute_with_retry(
            repository=repository,
            pipeline_run_id=uuid4(),
            dataset_id="erp.order",
            effective_config_hash=_CONFIG_HASH,
            execute_attempt=lambda _context: (_ for _ in ()).throw(
                UnknownCommitOutcomeError("uncertain")
            ),
            retry_policy=RetryPolicy(max_attempts=3),
        )

    assert len(repository.dataset_runs) == 1


def test_backfill_request_lifecycle_and_lineage_are_audited():
    repository = InMemoryControlPlane()
    request = ReprocessRequest(
        dataset_id="erp.order",
        run_mode=RunMode.BACKFILL,
        reason="repair missing interval",
        requested_by="data-ops",
        range_json={"lower": "2026-08-01", "upper": "2026-08-02"},
    )

    result = execute_with_retry(
        repository=repository,
        pipeline_run_id=uuid4(),
        dataset_id="erp.order",
        effective_config_hash=_CONFIG_HASH,
        execute_attempt=lambda _context: "backfilled",
        run_mode=RunMode.BACKFILL,
        reprocess_request=request,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    persisted = repository.get_reprocess_request(request.reprocess_request_id)
    assert persisted.status is ReprocessRequestStatus.SUCCEEDED
    lineage = repository.lineage_for_root(result.root_dataset_run_id)
    assert lineage[0].run_mode is RunMode.BACKFILL
    assert lineage[0].reprocess_request_id == request.reprocess_request_id


def test_explicit_retry_can_continue_existing_attempt_chain():
    repository = InMemoryControlPlane()
    root = uuid4()
    previous = root
    request = ReprocessRequest(
        dataset_id="erp.order",
        run_mode=RunMode.RETRY,
        reason="operator approved exact retry",
        requested_by="data-ops",
        original_dataset_run_id=previous,
    )

    result = execute_with_retry(
        repository=repository,
        pipeline_run_id=uuid4(),
        dataset_id="erp.order",
        effective_config_hash=_CONFIG_HASH,
        execute_attempt=lambda context: context.attempt,
        run_mode=RunMode.RETRY,
        reprocess_request=request,
        retry_policy=RetryPolicy(max_attempts=1),
        initial_attempt=2,
        root_dataset_run_id=root,
        previous_dataset_run_id=previous,
    )

    assert result.value == 2
    assert repository.attempt_lineage[0] == DatasetAttemptLineage(
        dataset_run_id=result.dataset_run_id,
        dataset_id="erp.order",
        root_dataset_run_id=root,
        previous_dataset_run_id=previous,
        attempt=2,
        run_mode=RunMode.RETRY,
        reprocess_request_id=request.reprocess_request_id,
        created_at=repository.attempt_lineage[0].created_at,
    )
