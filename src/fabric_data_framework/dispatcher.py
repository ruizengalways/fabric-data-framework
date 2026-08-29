"""Compatibility facade for metadata-driven dataset orchestration.

Planning/dependency decisions live in ``orchestration.planner`` while concrete
execution lives behind an execution backend. This module keeps the established
``dispatch_datasets`` public surface during the compatibility-conscious restructure.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID, uuid4

from .config import Criticality, DatasetStatus, PipelineStatus, RunMode, RuntimeOverride
from .contracts.dispatch import (
    DatasetDispatchOutcome,
    DatasetDispatchRequest,
    DatasetExecutor,
    ExecutorResolver,
    PipelineDispatchResult,
)
from .execution.backends.in_process import execute_ready_wave
from .operations import DatasetRunAudit, PipelineRunAudit
from .orchestration.planner import (
    DEFAULT_REQUIRED_CRITICALITIES,
    OrchestrationIntegrityError,
    aggregate_pipeline_status,
    blocking_dependencies,
    build_dispatch_plan,
    ready_dataset_ids,
)
from .repository import ControlPlaneRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    started_at: datetime,
    completed_at: datetime | None,
    domain_git_sha: str,
    framework_version: str,
    config_bundle_hash: str,
) -> PipelineRunAudit:
    return PipelineRunAudit(
        pipeline_run_id=pipeline_run_id,
        environment=environment,
        domain=domain,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        domain_git_sha=domain_git_sha,
        framework_version=framework_version,
        config_bundle_hash=config_bundle_hash,
    )


def _record_failed_pipeline(
    repository: ControlPlaneRepository,
    *,
    pipeline_run_id: UUID,
    environment: str,
    domain: str,
    started_at: datetime,
    domain_git_sha: str,
    framework_version: str,
    config_bundle_hash: str,
) -> None:
    repository.record_pipeline_run(
        _pipeline_audit(
            pipeline_run_id=pipeline_run_id,
            environment=environment,
            domain=domain,
            status=PipelineStatus.FAILED,
            started_at=started_at,
            completed_at=_utcnow(),
            domain_git_sha=domain_git_sha,
            framework_version=framework_version,
            config_bundle_hash=config_bundle_hash,
        )
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
    required_criticalities: frozenset[Criticality] = DEFAULT_REQUIRED_CRITICALITIES,
    pipeline_run_id: UUID | None = None,
    as_of: datetime | None = None,
) -> PipelineDispatchResult:
    """Plan and execute a metadata-selected graph using the in-process backend.

    The public function remains intentionally compatible with the Phase 4 API while
    orchestration decisions and physical execution are now separate. A future Fabric
    backend can consume the same provider-neutral dispatch/execution-plan contracts.
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
    except OrchestrationIntegrityError:
        _record_failed_pipeline(
            repository,
            pipeline_run_id=pipeline_run_id,
            environment=environment,
            domain=domain,
            started_at=started_at,
            domain_git_sha=domain_git_sha,
            framework_version=framework_version,
            config_bundle_hash=config_bundle_hash,
        )
        raise

    repository.record_pipeline_run(
        _pipeline_audit(
            pipeline_run_id=pipeline_run_id,
            environment=environment,
            domain=domain,
            status=PipelineStatus.RUNNING,
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
                _record_failed_pipeline(
                    repository,
                    pipeline_run_id=pipeline_run_id,
                    environment=environment,
                    domain=domain,
                    started_at=started_at,
                    domain_git_sha=domain_git_sha,
                    framework_version=framework_version,
                    config_bundle_hash=config_bundle_hash,
                )
                raise OrchestrationIntegrityError(
                    "dispatcher made no progress; dependency graph is not schedulable"
                )
            break

        wave_outcomes = execute_ready_wave(
            repository=repository,
            resolver=executor_resolver,
            pipeline_run_id=pipeline_run_id,
            effective_by_id=effective_by_id,
            dataset_ids=ready,
            run_mode=run_mode,
            max_concurrency=plan.max_concurrency,
        )
        outcomes.update(wave_outcomes)
        remaining.difference_update(wave_outcomes)

    final_status = aggregate_pipeline_status(
        plan,
        outcomes,
        required_criticalities=required_criticalities,
    )
    repository.record_pipeline_run(
        _pipeline_audit(
            pipeline_run_id=pipeline_run_id,
            environment=environment,
            domain=domain,
            status=final_status,
            started_at=started_at,
            completed_at=_utcnow(),
            domain_git_sha=domain_git_sha,
            framework_version=framework_version,
            config_bundle_hash=config_bundle_hash,
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


__all__ = [
    "DatasetDispatchOutcome",
    "DatasetDispatchRequest",
    "DatasetExecutor",
    "ExecutorResolver",
    "OrchestrationIntegrityError",
    "PipelineDispatchResult",
    "dispatch_datasets",
]
