"""Metadata-driven multi-dataset dispatcher and failure-isolation contracts."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Protocol
from uuid import UUID, uuid4

from .config import (
    Criticality,
    DatasetStatus,
    EffectiveDatasetConfig,
    PipelineStatus,
    RunMode,
    RuntimeOverride,
    resolve_effective_config,
)
from .operations import DatasetRunAudit, PipelineRunAudit
from .repository import ControlPlaneRepository


_TERMINAL_DATASET_STATUSES = frozenset(
    {
        DatasetStatus.SUCCEEDED,
        DatasetStatus.FAILED,
        DatasetStatus.QUARANTINED,
        DatasetStatus.SKIPPED,
        DatasetStatus.BLOCKED,
        DatasetStatus.CANCELLED,
    }
)
_DEFAULT_REQUIRED_CRITICALITIES = frozenset({Criticality.HIGH, Criticality.CRITICAL})


class OrchestrationIntegrityError(RuntimeError):
    """Raised when deployed metadata cannot be scheduled safely."""


@dataclass(frozen=True)
class DatasetDispatchRequest:
    """Small immutable contract passed from the dispatcher to a dataset executor."""

    pipeline_run_id: UUID
    dataset_run_id: UUID
    dataset_id: str
    run_mode: RunMode
    effective_config: EffectiveDatasetConfig
    attempt: int = 1


@dataclass(frozen=True)
class DatasetDispatchOutcome:
    """Terminal executor outcome consumed by the parent dispatcher."""

    dataset_run_id: UUID
    status: DatasetStatus
    retryable: bool | None = None
    error_code: str | None = None
    error_message: str | None = None


class DatasetExecutor(Protocol):
    def __call__(self, request: DatasetDispatchRequest) -> DatasetDispatchOutcome: ...


ExecutorResolver = Callable[[EffectiveDatasetConfig], DatasetExecutor]


@dataclass(frozen=True)
class PipelineDispatchResult:
    pipeline_run_id: UUID
    status: PipelineStatus
    selected_dataset_ids: tuple[str, ...]
    outcomes: tuple[tuple[str, DatasetDispatchOutcome], ...]
    max_concurrency: int

    def outcome_for(self, dataset_id: str) -> DatasetDispatchOutcome:
        for candidate, outcome in self.outcomes:
            if candidate == dataset_id:
                return outcome
        raise KeyError(f"dataset not part of dispatch result: {dataset_id}")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _overrides_by_dataset(
    overrides: Iterable[RuntimeOverride],
) -> dict[str, tuple[RuntimeOverride, ...]]:
    grouped: dict[str, list[RuntimeOverride]] = defaultdict(list)
    for override in overrides:
        grouped[override.dataset_id].append(override)
    return {dataset_id: tuple(items) for dataset_id, items in grouped.items()}


def _validate_dependency_graph(
    selected: dict[str, EffectiveDatasetConfig],
    deployed_ids: frozenset[str],
) -> None:
    for dataset_id, effective in selected.items():
        for dependency in effective.config.orchestration.dependencies:
            if dependency not in deployed_ids:
                raise OrchestrationIntegrityError(
                    f"dataset {dataset_id} depends on undeployed dataset {dependency}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(dataset_id: str) -> None:
        if dataset_id in visited:
            return
        if dataset_id in visiting:
            raise OrchestrationIntegrityError(
                f"dependency cycle detected at dataset {dataset_id}"
            )
        visiting.add(dataset_id)
        for dependency in selected[dataset_id].config.orchestration.dependencies:
            if dependency in selected:
                visit(dependency)
        visiting.remove(dataset_id)
        visited.add(dataset_id)

    for dataset_id in sorted(selected):
        visit(dataset_id)


def _record_blocked_dataset(
    repository: ControlPlaneRepository,
    *,
    pipeline_run_id: UUID,
    effective: EffectiveDatasetConfig,
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


def _execute_one(
    *,
    repository: ControlPlaneRepository,
    resolver: ExecutorResolver,
    pipeline_run_id: UUID,
    effective: EffectiveDatasetConfig,
    run_mode: RunMode,
) -> DatasetDispatchOutcome:
    dataset_run_id = uuid4()
    request = DatasetDispatchRequest(
        pipeline_run_id=pipeline_run_id,
        dataset_run_id=dataset_run_id,
        dataset_id=effective.config.dataset_id,
        run_mode=run_mode,
        effective_config=effective,
    )
    try:
        executor = resolver(effective)
        outcome = executor(request)
        if outcome.dataset_run_id != dataset_run_id:
            raise OrchestrationIntegrityError(
                f"executor returned mismatched dataset_run_id for {request.dataset_id}"
            )
        if outcome.status not in _TERMINAL_DATASET_STATUSES:
            raise OrchestrationIntegrityError(
                f"executor returned non-terminal status {outcome.status.value} "
                f"for {request.dataset_id}"
            )
        return outcome
    except Exception as exc:  # dataset fault boundary: siblings must still continue
        repository.record_dataset_run(
            DatasetRunAudit(
                dataset_run_id=dataset_run_id,
                pipeline_run_id=pipeline_run_id,
                dataset_id=effective.config.dataset_id,
                attempt=1,
                run_mode=run_mode,
                status=DatasetStatus.FAILED,
                effective_config_hash=effective.effective_config_hash,
                error_code="EXECUTOR_EXCEPTION",
                error_message=f"{type(exc).__name__}: {exc}",
                retryable=None,
            )
        )
        return DatasetDispatchOutcome(
            dataset_run_id=dataset_run_id,
            status=DatasetStatus.FAILED,
            error_code="EXECUTOR_EXCEPTION",
            error_message=f"{type(exc).__name__}: {exc}",
        )


def _aggregate_pipeline_status(
    selected: dict[str, EffectiveDatasetConfig],
    outcomes: dict[str, DatasetDispatchOutcome],
    required_criticalities: frozenset[Criticality],
) -> PipelineStatus:
    if not selected:
        return PipelineStatus.SUCCESS
    if all(outcome.status is DatasetStatus.SUCCEEDED for outcome in outcomes.values()):
        return PipelineStatus.SUCCESS

    for dataset_id, outcome in outcomes.items():
        if (
            outcome.status is not DatasetStatus.SUCCEEDED
            and selected[dataset_id].config.orchestration.criticality in required_criticalities
        ):
            return PipelineStatus.FAILED
    return PipelineStatus.PARTIAL_SUCCESS


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
    required_criticalities: frozenset[Criticality] = _DEFAULT_REQUIRED_CRITICALITIES,
    pipeline_run_id: UUID | None = None,
    as_of: datetime | None = None,
) -> PipelineDispatchResult:
    """Dispatch a metadata-selected dataset graph with bounded sibling isolation.

    Dataset executors own their normal dataset/step audit records. The dispatcher
    creates dataset audit records only when a dataset is dependency-blocked or an
    executor raises before it can return a terminal outcome.
    """

    if max_concurrency <= 0:
        raise ValueError("max_concurrency must be positive")

    started_at = _utcnow()
    evaluation_time = as_of or started_at
    pipeline_run_id = pipeline_run_id or uuid4()
    deployed = {config.dataset_id: config for config in repository.list_datasets()}
    deployed_ids = frozenset(deployed)
    requested = None if requested_dataset_ids is None else frozenset(requested_dataset_ids)

    if requested is not None:
        unknown = sorted(requested - deployed_ids)
        if unknown:
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
                f"requested datasets are not deployed: {','.join(unknown)}"
            )

    overrides_by_dataset = _overrides_by_dataset(overrides)
    unknown_override_ids = sorted(set(overrides_by_dataset) - deployed_ids)
    if unknown_override_ids:
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
            "runtime overrides target undeployed datasets: " + ",".join(unknown_override_ids)
        )

    effective_by_id: dict[str, EffectiveDatasetConfig] = {}
    for dataset_id, base in deployed.items():
        effective = resolve_effective_config(
            base,
            overrides_by_dataset.get(dataset_id, ()),
            as_of=evaluation_time,
        )
        config = effective.config
        if not config.enabled:
            continue
        if execution_group is not None and config.orchestration.execution_group != execution_group:
            continue
        if requested is not None and dataset_id not in requested:
            continue
        effective_by_id[dataset_id] = effective

    selected_ids = tuple(
        sorted(
            effective_by_id,
            key=lambda dataset_id: (
                effective_by_id[dataset_id].config.orchestration.priority,
                dataset_id,
            ),
        )
    )
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

    try:
        _validate_dependency_graph(effective_by_id, deployed_ids)
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

    if effective_by_id:
        config_limit = min(
            item.config.orchestration.max_concurrency for item in effective_by_id.values()
        )
        effective_concurrency = min(max_concurrency, config_limit, len(effective_by_id))
    else:
        effective_concurrency = 1

    remaining = set(effective_by_id)
    outcomes: dict[str, DatasetDispatchOutcome] = {}

    while remaining:
        newly_blocked: list[tuple[str, tuple[str, ...]]] = []
        for dataset_id in sorted(remaining):
            dependencies = effective_by_id[dataset_id].config.orchestration.dependencies
            unavailable = tuple(
                sorted(dependency for dependency in dependencies if dependency not in effective_by_id)
            )
            failed = tuple(
                sorted(
                    dependency
                    for dependency in dependencies
                    if dependency in outcomes
                    and outcomes[dependency].status is not DatasetStatus.SUCCEEDED
                )
            )
            blockers = tuple(sorted(set(unavailable + failed)))
            if blockers:
                newly_blocked.append((dataset_id, blockers))

        for dataset_id, blockers in newly_blocked:
            outcomes[dataset_id] = _record_blocked_dataset(
                repository,
                pipeline_run_id=pipeline_run_id,
                effective=effective_by_id[dataset_id],
                run_mode=run_mode,
                blocking_dependencies=blockers,
            )
            remaining.remove(dataset_id)

        ready = [
            dataset_id
            for dataset_id in selected_ids
            if dataset_id in remaining
            and all(
                dependency in outcomes
                and outcomes[dependency].status is DatasetStatus.SUCCEEDED
                for dependency in effective_by_id[dataset_id].config.orchestration.dependencies
            )
        ]

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

        with ThreadPoolExecutor(max_workers=effective_concurrency) as pool:
            future_to_dataset = {
                pool.submit(
                    _execute_one,
                    repository=repository,
                    resolver=executor_resolver,
                    pipeline_run_id=pipeline_run_id,
                    effective=effective_by_id[dataset_id],
                    run_mode=run_mode,
                ): dataset_id
                for dataset_id in ready
            }
            for future in as_completed(future_to_dataset):
                dataset_id = future_to_dataset[future]
                outcomes[dataset_id] = future.result()
                remaining.remove(dataset_id)

    final_status = _aggregate_pipeline_status(
        effective_by_id,
        outcomes,
        required_criticalities,
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
        selected_dataset_ids=selected_ids,
        outcomes=tuple((dataset_id, outcomes[dataset_id]) for dataset_id in selected_ids),
        max_concurrency=effective_concurrency,
    )
