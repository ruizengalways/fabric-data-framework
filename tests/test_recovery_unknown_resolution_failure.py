from __future__ import annotations

from uuid import uuid4

import pytest

from fabric_data_framework.contracts.recovery import (
    ReprocessRequest,
    ReprocessRequestStatus,
)
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.metadata.config import DatasetStatus, RunMode
from fabric_data_framework.recovery.runtime import (
    RetryPolicy,
    UnknownCommitOutcomeError,
    UnknownOutcomeResolutionFailedError,
    execute_with_retry,
)


def _request() -> ReprocessRequest:
    return ReprocessRequest(
        dataset_id="crm.customer",
        run_mode=RunMode.RETRY,
        reason="recover uncertain target commit",
        requested_by="test",
        original_dataset_run_id=uuid4(),
    )


def _unknown(_context):
    raise UnknownCommitOutcomeError("target response lost password=original-secret")


def test_resolver_exception_records_terminal_audit_and_fails_reprocess_request():
    repository = InMemoryControlPlane()
    request = _request()

    def resolver(_context, _exc):
        raise TimeoutError("resolver timed out token=resolver-secret")

    with pytest.raises(UnknownOutcomeResolutionFailedError) as raised:
        execute_with_retry(
            repository=repository,
            pipeline_run_id=uuid4(),
            dataset_id=request.dataset_id,
            effective_config_hash="a" * 64,
            execute_attempt=_unknown,
            retry_policy=RetryPolicy(max_attempts=1),
            run_mode=RunMode.RETRY,
            reprocess_request=request,
            resolve_unknown_outcome=resolver,
        )

    assert isinstance(raised.value.unknown_outcome_error, UnknownCommitOutcomeError)
    assert isinstance(raised.value.resolver_error, TimeoutError)
    audit = repository.dataset_runs[-1]
    assert audit.status is DatasetStatus.FAILED
    assert audit.error_code == "UNKNOWN_COMMIT_RESOLUTION_FAILED"
    assert "original-secret" not in (audit.error_message or "")
    assert "resolver-secret" not in (audit.error_message or "")
    assert repository.reprocess_requests[-1].status is ReprocessRequestStatus.FAILED


def test_invalid_resolver_value_fails_closed_without_retry():
    repository = InMemoryControlPlane()
    request = _request()
    attempts = 0

    def execute(context):
        nonlocal attempts
        attempts += 1
        return _unknown(context)

    def resolver(_context, _exc):
        return "NOT_COMMITTED"

    with pytest.raises(UnknownOutcomeResolutionFailedError):
        execute_with_retry(
            repository=repository,
            pipeline_run_id=uuid4(),
            dataset_id=request.dataset_id,
            effective_config_hash="b" * 64,
            execute_attempt=execute,
            retry_policy=RetryPolicy(max_attempts=3),
            run_mode=RunMode.RETRY,
            reprocess_request=request,
            resolve_unknown_outcome=resolver,  # type: ignore[arg-type]
        )

    assert attempts == 1
    assert repository.dataset_runs[-1].error_code == "UNKNOWN_COMMIT_RESOLUTION_FAILED"
    assert repository.reprocess_requests[-1].status is ReprocessRequestStatus.FAILED
