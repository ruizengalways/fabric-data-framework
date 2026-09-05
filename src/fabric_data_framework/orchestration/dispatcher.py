"""Metadata-driven dataset dispatch over planner-selected ready waves.

Planning/dependency decisions live in ``orchestration.planner`` while concrete
execution lives behind a ready-wave backend. Both in-process and Fabric/native backends
consume the same dependency and criticality semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Protocol
from uuid import UUID, uuid4

from fabric_data_framework.metadata.config import (
    Criticality,
    DatasetStatus,
    EffectiveDatasetConfig,
    PipelineStatus,
    RunMode,
    RuntimeOverride,
)
from ..contracts.dispatch import (
    DatasetDispatchOutcome,
    DatasetDispatchRequest,
    DatasetExecutor,
    ExecutorResolver,
    PipelineDispatchResult,
)
from ..execution.backends.in_process import execute_ready_wave
from fabric_data_framework.contracts.audit import (
    DatasetRunAudit,
    PipelineRunAudit,
)
from .planner import (
    DEFAULT_REQUIRED_CRITICALITIES,
    OrchestrationIntegrityError,
    PipelineFailurePolicy,
    aggregate_pipeline_status,
    blocking_dependencies,
    build_dispatch_plan,
    ready_dataset_ids,
)
from ..control_plane.repository import ControlPlaneRepository


_PIPELINE_ERROR_MESSAGE_LIMIT = 4096


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReadyWaveBackend(Protocol):
    """Physical executor for one dependency-ready dataset wave."""

    def execute_ready_wave(
        self,
        *,
        repository: ControlPlaneRepository,
        pipeline_run_id: UUID,
        effective_by_id: dict[str, EffectiveDatasetConfig],
        dataset_ids: Iterable[str],
        run_mode: RunMode,
        max_concurrency: int,
    ) -> dict[str, DatasetDispatchOutcome]: ...


class _InProcessBackend:
    def __init__(self, resolver: ExecutorResolver) -> None:
        self._resolver = resolver

    def execute_ready_wave(
        self,
        *,
        repository: ControlPlaneRepository,
        pipeline_run_id: UUID,
        effective_by_id: dict[str, EffectiveDatasetConfig],
        dataset_ids: Iterable[str],
        run_mode: RunMode,
        max_concurrency: int,
    ) -> dict[str, DatasetDispatchOutcome]:
        return execute_ready_wave(
            repository=repository,
            resolver=self._resolver,
            pipeline_run_id=pipeline_run_id,
            effective_by_id=effective_by_id,
            dataset_ids=dataset_ids,
            run_mode=run_mode,
            max_concurrency=max_concurrency,
        )


def _record_blocked_dataset(
    repository: ControlPlaneRepository,
    *,
    pipeline_run_id: UUID,
    effective,
    run_mode: RunMode,
    blocking_dependencies: tuple[str, ...],
) -> DatasetDispatchOutcome:
    dataset_run_id = uuid4()
    detail = ",".join(blocking_dependencies)
    repository.record_dataset_run(
        DatasetRunAudit(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=effective.config.dataset_id,
            attempt=1,
            run_mode=run_mode,
            status=DatasetStatus.BLOCKED,
            effective_config_hash=effective.effective_config_hash,
            error_code="BLOCKED_DEPENDENCY",
            error_message=f"blocked by dependencies: {detail}",
            retryable=False,
        )
    )
    return DatasetDispatchOutcome(
        dataset_run_id=dataset_run_id,
        status=DatasetStatus.BLOCKED,
        retryable=False,
        error_code="BLOCKED_DEPENDENCY",
        error_message=f"blocked by dependencies: {detail}",
    )


def _pipeline_audit(
    *,
    pipeline_run_id: UUID,
    environment: str,
    domain: str,
    status: PipelineStatus,
    run_mode: RunMode,
    started_at: datetime,
    completed_at: datetime | None,
    domain_git_sha: str,
    framework_version: str,
    config_bundle_hash: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> PipelineRunAudit:
    return PipelineRunAudit(
        pipeline_run_id=pipeline_run_id,
        environment=environment,
        domain=domain,
        status=status,
        run_mode=run_mode,
        started_at=started_at,
        completed_at=completed_at,
        domain_git_sha=domain_git_sha,
        framework_version=framework_version,
        config_bundle_hash=config_bundle_hash,
        error_code=error_code,
        error_message=error_message,
    )


def _bounded_message(value: str) -> str:
    if len(value) <= _PIPELINE_ERROR_MESSAGE_LIMIT:
        return value
    suffix = "... [truncated]"
    return value[: _PIPELINE_ERROR_MESSAGE_LIMIT - len(suffix)] + suffix


def _aggregate_outcome_error(
    selected_dataset_ids: tuple[str, ...],
    outcomes: dict[str, DatasetDispatchOutcome],
) -> str:
    failures: list[str] = []
    for dataset_id in selected_dataset_ids:
        outcome = outcomes.get(dataset_id)
        if outcome is None or outcome.status is DatasetStatus.SUCCEEDED:
            continue
        error_code = outcome.error_code or outcome.status.value
        error_message = outcome.error_message or "no dataset error detail"
        failures.append(
            f"{dataset_id}[{outcome.status.value}/{error_code}]: {error_message}"
        )
    return _bounded_message("; ".join(failures) or "pipeline contained non-success dataset outcomes")


def _record_failed_pipeline(
    repository: ControlPlaneRepository,
    *,
    pipeline_run_id: UUID,
    environment: str,
    domain: str,
    run_mode: RunMode,
    started_at: datetime,
    domain_git_sha: str,
    framework_version: str,
    config_bundle_hash: str,
    error_code: str,
    error_message: str,
) -> None:
    repository.record_pipeline_run(
        _pipeline_audit(
            pipeline_run_id=pipeline_run_id,
            environment=environment,
            domain=domain,
            status=PipelineStatus.FAILED,
            run_mode=run_mode,
            started_at=started_at,
            completed_at=_utcnow(),
            domain_git_sha=domain_git_sha,
            framework_version=framework_version,
            config_bundle_hash=config_bundle_hash,
            error_code=error_code,
            error_message=_bounded_message(error_message),
        )
    )


def dispatch_datasets_with_backend(
    *,
    repository: ControlPlaneRepository,
    backend: ReadyWaveBackend,
    environment: str,
    domain: str,
    domain_git_sha: str,
    framework_version: str,
    config_bundle_hash: str,
    run_mode: RunMode = RunMode.NORMAL,
    execution_group: str | None = None,
    requested_dataset_ids: Iterable[str] | None = None,
    overrides: Iterable[RuntimeOverride] = (),
    max_concurrency: int = 4,
    failure_policy: PipelineFailurePolicy = PipelineFailurePolicy.FAIL_AT_END,
    required_criticalities: frozenset[Criticality] = DEFAULT_REQUIRED_CRITICALITIES,
    pipeline_run_id: UUID | None = None,
    as_of: datetime | None = None,
) -> PipelineDispatchResult:
    """Plan once, isolate dataset faults, then aggregate the Pipeline after all work.

    Dataset/provider exceptions are converted to terminal dataset outcomes by the
    execution backend.  Failed dependencies block only their dependents.  Independent
    siblings continue, so the default FAIL_AT_END policy reports parent failure only
    after every runnable selected dataset has reached a terminal outcome.
    """

    started_at = _utcnow()
    pipeline_run_id = pipeline_run_id or uuid4()

    try:
        plan = build_dispatch_plan(
            repository=repository,
            execution_group=execution_group,
            requested_dataset_ids=requested_dataset_ids,
            overrides=overrides,
            max_concurrency=max_concurrency,
            as_of=as_of or started_at,
        )
    except OrchestrationIntegrityError as exc:
        _record_failed_pipeline(
            repository,
            pipeline_run_id=pipeline_run_id,
            environment=environment,
            domain=domain,
            run_mode=run_mode,
            started_at=started_at,
            domain_git_sha=domain_git_sha,
            framework_version=framework_version,
            config_bundle_hash=config_bundle_hash,
            error_code="ORCHESTRATION_INTEGRITY_ERROR",
            error_message=f"{type(exc).__name__}: {exc}",
        )
        raise

    repository.record_pipeline_run(
        _pipeline_audit(
            pipeline_run_id=pipeline_run_id,
            environment=environment,
            domain=domain,
            status=PipelineStatus.RUNNING,
            run_mode=run_mode,
            started_at=started_at,
            completed_at=None,
            domain_git_sha=domain_git_sha,
            framework_version=framework_version,
            config_bundle_hash=config_bundle_hash,
        )
    )

    effective_by_id = dict(plan.effective_configs)
    remaining = set(plan.selected_dataset_ids)
    outcomes: dict[str, DatasetDispatchOutcome] = {}

    while remaining:
        newly_blocked: list[tuple[str, tuple[str, ...]]] = []
        for dataset_id in sorted(remaining):
            blockers = blocking_dependencies(plan, dataset_id, outcomes)
            if blockers:
                newly_blocked.append((dataset_id, blockers))

        for dataset_id, blockers in newly_blocked:
            outcomes[dataset_id] = _record_blocked_dataset(
                repository,
                pipeline_run_id=pipeline_run_id,
                effective=plan.effective_for(dataset_id),
                run_mode=run_mode,
                blocking_dependencies=blockers,
            )
            remaining.remove(dataset_id)

        ready = ready_dataset_ids(plan, remaining, outcomes)
        if not ready:
            if remaining:
                message = "dispatcher made no progress; dependency graph is not schedulable"
                _record_failed_pipeline(
                    repository,
                    pipeline_run_id=pipeline_run_id,
                    environment=environment,
                    domain=domain,
                    run_mode=run_mode,
                    started_at=started_at,
                    domain_git_sha=domain_git_sha,
                    framework_version=framework_version,
                    config_bundle_hash=config_bundle_hash,
                    error_code="ORCHESTRATION_NO_PROGRESS",
                    error_message=message,
                )
                raise OrchestrationIntegrityError(message)
            break

        wave_outcomes = backend.execute_ready_wave(
            repository=repository,
            pipeline_run_id=pipeline_run_id,
            effective_by_id=effective_by_id,
            dataset_ids=ready,
            run_mode=run_mode,
            max_concurrency=plan.max_concurrency,
        )
        unexpected = sorted(set(wave_outcomes) - set(ready))
        missing = sorted(set(ready) - set(wave_outcomes))
        if unexpected or missing:
            message = (
                "execution backend returned an invalid ready-wave result: "
                f"missing={missing}, unexpected={unexpected}"
            )
            _record_failed_pipeline(
                repository,
                pipeline_run_id=pipeline_run_id,
                environment=environment,
                domain=domain,
                run_mode=run_mode,
                started_at=started_at,
                domain_git_sha=domain_git_sha,
                framework_version=framework_version,
                config_bundle_hash=config_bundle_hash,
                error_code="INVALID_READY_WAVE_RESULT",
                error_message=message,
            )
            raise OrchestrationIntegrityError(message)
        outcomes.update(wave_outcomes)
        remaining.difference_update(wave_outcomes)

    final_status = aggregate_pipeline_status(
        plan,
        outcomes,
        failure_policy=failure_policy,
        required_criticalities=required_criticalities,
    )
    final_error_code: str | None = None
    final_error_message: str | None = None
    if final_status is PipelineStatus.FAILED:
        final_error_code = "DATASET_FAILURES_AT_END"
        final_error_message = _aggregate_outcome_error(plan.selected_dataset_ids, outcomes)
    elif final_status is PipelineStatus.PARTIAL_SUCCESS:
        final_error_code = "DATASET_WARNINGS_AT_END"
        final_error_message = _aggregate_outcome_error(plan.selected_dataset_ids, outcomes)

    repository.record_pipeline_run(
        _pipeline_audit(
            pipeline_run_id=pipeline_run_id,
            environment=environment,
            domain=domain,
            status=final_status,
            run_mode=run_mode,
            started_at=started_at,
            completed_at=_utcnow(),
            domain_git_sha=domain_git_sha,
            framework_version=framework_version,
            config_bundle_hash=config_bundle_hash,
            error_code=final_error_code,
            error_message=final_error_message,
        )
    )

    return PipelineDispatchResult(
        pipeline_run_id=pipeline_run_id,
        status=final_status,
        selected_dataset_ids=plan.selected_dataset_ids,
        outcomes=tuple(
            (dataset_id, outcomes[dataset_id]) for dataset_id in plan.selected_dataset_ids
        ),
        max_concurrency=plan.max_concurrency,
    )


def dispatch_datasets(
    *,
    repository: ControlPlaneRepository,
    executor_resolver: ExecutorResolver,
    environment: str,
    domain: str,
    domain_git_sha: str,
    framework_version: str,
    config_bundle_hash: str,
    run_mode: RunMode = RunMode.NORMAL,
    execution_group: str | None = None,
    requested_dataset_ids: Iterable[str] | None = None,
    overrides: Iterable[RuntimeOverride] = (),
    max_concurrency: int = 4,
    failure_policy: PipelineFailurePolicy = PipelineFailurePolicy.FAIL_AT_END,
    required_criticalities: frozenset[Criticality] = DEFAULT_REQUIRED_CRITICALITIES,
    pipeline_run_id: UUID | None = None,
    as_of: datetime | None = None,
) -> PipelineDispatchResult:
    """Backward-compatible in-process dispatcher with fail-at-end aggregation."""

    return dispatch_datasets_with_backend(
        repository=repository,
        backend=_InProcessBackend(executor_resolver),
        environment=environment,
        domain=domain,
        domain_git_sha=domain_git_sha,
        framework_version=framework_version,
        config_bundle_hash=config_bundle_hash,
        run_mode=run_mode,
        execution_group=execution_group,
        requested_dataset_ids=requested_dataset_ids,
        overrides=overrides,
        max_concurrency=max_concurrency,
        failure_policy=failure_policy,
        required_criticalities=required_criticalities,
        pipeline_run_id=pipeline_run_id,
        as_of=as_of,
    )


__all__ = [
    "DatasetDispatchOutcome",
    "DatasetDispatchRequest",
    "DatasetExecutor",
    "ExecutorResolver",
    "OrchestrationIntegrityError",
    "PipelineDispatchResult",
    "PipelineFailurePolicy",
    "ReadyWaveBackend",
    "dispatch_datasets",
    "dispatch_datasets_with_backend",
]
