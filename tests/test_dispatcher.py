from __future__ import annotations

from threading import Lock
from time import sleep

import pytest

from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    PipelineStatus,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.orchestration.dispatcher import (
    DatasetDispatchOutcome,
    OrchestrationIntegrityError,
    dispatch_datasets,
)
from fabric_data_framework.contracts.audit import DatasetRunAudit
from fabric_data_framework.control_plane.repository import InMemoryControlPlane


CONFIG_HASH = "a" * 64
GIT_SHA = "abcdef0"


def _config(
    dataset_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    criticality: Criticality = Criticality.MEDIUM,
    execution_group: str = "daily",
    priority: int = 100,
    max_concurrency: int = 4,
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(system="crm", object=dataset_id),
        target=TargetConfig(layer="silver", object=dataset_id),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(
            execution_group=execution_group,
            criticality=criticality,
            dependencies=dependencies,
            priority=priority,
            max_concurrency=max_concurrency,
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
    )


def _resolver(repository, statuses, calls, *, active=None):
    def resolve(effective):
        def execute(request):
            if active is not None:
                lock, state = active
                with lock:
                    state["active"] += 1
                    state["max_active"] = max(state["max_active"], state["active"])
                sleep(0.05)
                with lock:
                    state["active"] -= 1

            calls.append(request.dataset_id)
            requested = statuses[request.dataset_id]
            if isinstance(requested, Exception):
                raise requested
            outcome = DatasetDispatchOutcome(
                dataset_run_id=request.dataset_run_id,
                status=requested,
                error_code=None if requested is DatasetStatus.SUCCEEDED else "TEST_FAILURE",
                error_message=None
                if requested is DatasetStatus.SUCCEEDED
                else "intentional test failure",
                retryable=False if requested is DatasetStatus.FAILED else None,
            )
            repository.record_dataset_run(
                DatasetRunAudit(
                    dataset_run_id=request.dataset_run_id,
                    pipeline_run_id=request.pipeline_run_id,
                    dataset_id=request.dataset_id,
                    attempt=request.attempt,
                    run_mode=request.run_mode,
                    status=requested,
                    effective_config_hash=request.effective_config.effective_config_hash,
                    error_code=outcome.error_code,
                    error_message=outcome.error_message,
                    retryable=outcome.retryable,
                )
            )
            return outcome

        return execute

    return resolve


def _dispatch(repository, resolver, **kwargs):
    return dispatch_datasets(
        repository=repository,
        executor_resolver=resolver,
        environment="dev",
        domain="customer",
        domain_git_sha=GIT_SHA,
        framework_version="0.4.0",
        config_bundle_hash=CONFIG_HASH,
        **kwargs,
    )


def test_non_critical_failure_is_partial_success_and_siblings_continue():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("customer", criticality=Criticality.HIGH))
    repository.deploy_dataset(_config("contact", criticality=Criticality.LOW))
    repository.deploy_dataset(_config("address", criticality=Criticality.MEDIUM))
    calls: list[str] = []

    result = _dispatch(
        repository,
        _resolver(
            repository,
            {
                "customer": DatasetStatus.SUCCEEDED,
                "contact": DatasetStatus.FAILED,
                "address": DatasetStatus.SUCCEEDED,
            },
            calls,
        ),
    )

    assert result.status is PipelineStatus.PARTIAL_SUCCESS
    assert set(calls) == {"customer", "contact", "address"}
    assert result.outcome_for("contact").status is DatasetStatus.FAILED
    assert repository.pipeline_runs[-1].status is PipelineStatus.PARTIAL_SUCCESS


def test_critical_failure_fails_parent_only_after_independent_sibling_runs():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("customer", criticality=Criticality.HIGH))
    repository.deploy_dataset(_config("address", criticality=Criticality.MEDIUM))
    calls: list[str] = []

    result = _dispatch(
        repository,
        _resolver(
            repository,
            {
                "customer": DatasetStatus.FAILED,
                "address": DatasetStatus.SUCCEEDED,
            },
            calls,
        ),
    )

    assert result.status is PipelineStatus.FAILED
    assert set(calls) == {"customer", "address"}
    assert repository.pipeline_runs[-1].status is PipelineStatus.FAILED


def test_failed_dependency_blocks_only_dependents():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("source", criticality=Criticality.LOW))
    repository.deploy_dataset(
        _config(
            "dependent",
            dependencies=("source",),
            criticality=Criticality.HIGH,
        )
    )
    repository.deploy_dataset(_config("independent", criticality=Criticality.MEDIUM))
    calls: list[str] = []

    result = _dispatch(
        repository,
        _resolver(
            repository,
            {
                "source": DatasetStatus.FAILED,
                "dependent": DatasetStatus.SUCCEEDED,
                "independent": DatasetStatus.SUCCEEDED,
            },
            calls,
        ),
    )

    assert result.status is PipelineStatus.FAILED
    assert set(calls) == {"source", "independent"}
    assert result.outcome_for("dependent").status is DatasetStatus.BLOCKED
    blocked_audit = next(
        item for item in repository.dataset_runs if item.dataset_id == "dependent"
    )
    assert blocked_audit.error_code == "BLOCKED_DEPENDENCY"


def test_executor_exception_is_isolated_and_audited():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("bad", criticality=Criticality.LOW))
    repository.deploy_dataset(_config("good", criticality=Criticality.MEDIUM))
    calls: list[str] = []

    result = _dispatch(
        repository,
        _resolver(
            repository,
            {
                "bad": RuntimeError("boom"),
                "good": DatasetStatus.SUCCEEDED,
            },
            calls,
        ),
    )

    assert result.status is PipelineStatus.PARTIAL_SUCCESS
    assert set(calls) == {"bad", "good"}
    failure = result.outcome_for("bad")
    assert failure.status is DatasetStatus.FAILED
    assert failure.error_code == "EXECUTOR_EXCEPTION"
    fallback = next(item for item in repository.dataset_runs if item.dataset_id == "bad")
    assert fallback.error_code == "EXECUTOR_EXCEPTION"


def test_dispatcher_respects_bounded_concurrency():
    repository = InMemoryControlPlane()
    statuses = {}
    for index in range(4):
        dataset_id = f"dataset_{index}"
        repository.deploy_dataset(_config(dataset_id, max_concurrency=3))
        statuses[dataset_id] = DatasetStatus.SUCCEEDED
    calls: list[str] = []
    lock = Lock()
    state = {"active": 0, "max_active": 0}

    result = _dispatch(
        repository,
        _resolver(repository, statuses, calls, active=(lock, state)),
        max_concurrency=2,
    )

    assert result.status is PipelineStatus.SUCCESS
    assert result.max_concurrency == 2
    assert state["max_active"] == 2
    assert len(calls) == 4


def test_execution_group_filter_selects_only_requested_group():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("daily", execution_group="daily"))
    repository.deploy_dataset(_config("hourly", execution_group="hourly"))
    calls: list[str] = []

    result = _dispatch(
        repository,
        _resolver(
            repository,
            {
                "daily": DatasetStatus.SUCCEEDED,
                "hourly": DatasetStatus.SUCCEEDED,
            },
            calls,
        ),
        execution_group="daily",
        run_mode=RunMode.NORMAL,
    )

    assert result.selected_dataset_ids == ("daily",)
    assert calls == ["daily"]
    assert result.status is PipelineStatus.SUCCESS


def test_dependency_cycle_fails_as_orchestration_integrity_error_before_execution():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("a", dependencies=("b",)))
    repository.deploy_dataset(_config("b", dependencies=("a",)))
    calls: list[str] = []

    with pytest.raises(OrchestrationIntegrityError, match="dependency cycle"):
        _dispatch(
            repository,
            _resolver(
                repository,
                {"a": DatasetStatus.SUCCEEDED, "b": DatasetStatus.SUCCEEDED},
                calls,
            ),
        )

    assert calls == []
    assert repository.pipeline_runs[-1].status is PipelineStatus.FAILED
