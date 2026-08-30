"""In-process reference execution backend for orchestration certification."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable
from uuid import UUID, uuid4

from ...config import DatasetStatus, EffectiveDatasetConfig, RunMode
from ...contracts.dispatch import (
    DatasetDispatchOutcome,
    DatasetDispatchRequest,
    ExecutorResolver,
)
from ...contracts.execution_plan import ExecutionKind, build_default_execution_plan
from ...operations import DatasetRunAudit
from ...orchestration.planner import OrchestrationIntegrityError
from ...control_plane.repository import ControlPlaneRepository


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


def execute_one_in_process(
    *,
    repository: ControlPlaneRepository,
    resolver: ExecutorResolver,
    pipeline_run_id: UUID,
    effective: EffectiveDatasetConfig,
    run_mode: RunMode,
) -> DatasetDispatchOutcome:
    """Execute one dataset behind the same immutable request used by future backends."""

    dataset_run_id = uuid4()
    request = DatasetDispatchRequest(
        pipeline_run_id=pipeline_run_id,
        dataset_run_id=dataset_run_id,
        dataset_id=effective.config.dataset_id,
        run_mode=run_mode,
        effective_config=effective,
        execution_plan=build_default_execution_plan(
            effective,
            run_mode=run_mode,
            execution_kind=ExecutionKind.IN_PROCESS,
        ),
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


def execute_ready_wave(
    *,
    repository: ControlPlaneRepository,
    resolver: ExecutorResolver,
    pipeline_run_id: UUID,
    effective_by_id: dict[str, EffectiveDatasetConfig],
    dataset_ids: Iterable[str],
    run_mode: RunMode,
    max_concurrency: int,
) -> dict[str, DatasetDispatchOutcome]:
    """Execute one planner-selected ready wave with bounded local concurrency."""

    selected_ids = tuple(dataset_ids)
    if not selected_ids:
        return {}
    if max_concurrency <= 0:
        raise ValueError("max_concurrency must be positive")

    outcomes: dict[str, DatasetDispatchOutcome] = {}
    with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
        future_to_dataset = {
            pool.submit(
                execute_one_in_process,
                repository=repository,
                resolver=resolver,
                pipeline_run_id=pipeline_run_id,
                effective=effective_by_id[dataset_id],
                run_mode=run_mode,
            ): dataset_id
            for dataset_id in selected_ids
        }
        for future in as_completed(future_to_dataset):
            dataset_id = future_to_dataset[future]
            outcomes[dataset_id] = future.result()
    return outcomes
