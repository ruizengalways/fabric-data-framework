from uuid import uuid4

import pytest

from fabric_data_framework.config import RunMode
from fabric_data_framework.contracts.recovery import ReprocessRequest, ReprocessRequestStatus
from fabric_data_framework.recovery import RetryPolicy, execute_with_retry
from fabric_data_framework.repository import InMemoryControlPlane


_CONFIG_HASH = "b" * 64


def test_process_control_exceptions_are_not_swallowed_as_dataset_failures():
    repository = InMemoryControlPlane()

    with pytest.raises(KeyboardInterrupt):
        execute_with_retry(
            repository=repository,
            pipeline_run_id=uuid4(),
            dataset_id="erp.order",
            effective_config_hash=_CONFIG_HASH,
            execute_attempt=lambda _context: (_ for _ in ()).throw(KeyboardInterrupt()),
            retry_policy=RetryPolicy(max_attempts=3),
        )

    assert repository.dataset_runs == []
    assert len(repository.attempt_lineage) == 1


def test_reprocess_lifecycle_updates_have_a_real_updated_timestamp():
    repository = InMemoryControlPlane()
    request = ReprocessRequest(
        dataset_id="erp.order",
        run_mode=RunMode.BACKFILL,
        reason="repair interval",
        requested_by="data-ops",
        range_json={"lower": 1, "upper": 2},
    )

    execute_with_retry(
        repository=repository,
        pipeline_run_id=uuid4(),
        dataset_id="erp.order",
        effective_config_hash=_CONFIG_HASH,
        execute_attempt=lambda _context: "ok",
        run_mode=RunMode.BACKFILL,
        reprocess_request=request,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    persisted = repository.get_reprocess_request(request.reprocess_request_id)
    assert persisted.status is ReprocessRequestStatus.SUCCEEDED
    assert persisted.updated_at is not None
    assert persisted.updated_at >= persisted.created_at
