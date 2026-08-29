"""Fabric Data Pipeline execution backend for one planner-selected dataset wave.

A remote Fabric job reaching ``Completed`` is necessary but not sufficient for semantic
success. The child pipeline must persist a framework DatasetDispatchOutcome (or an
equivalent durable projection) for the exact dataset_run_id. Missing semantic outcome
evidence fails closed.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import UUID, uuid4

from ...adapters.fabric.pipeline import (
    FabricPipelineBinding,
    FabricPipelineInvocation,
    FabricPipelineTransport,
)
from ...adapters.fabric.rest import FabricJobStatus, FabricRestError
from ...config import DatasetStatus, EffectiveDatasetConfig, RunMode
from ...contracts.dispatch import DatasetDispatchOutcome
from ...contracts.execution_plan import compile_execution_plan
from ...operations import DatasetRunAudit
from ...repository import ControlPlaneRepository


FabricPipelineBindingResolver = Callable[[EffectiveDatasetConfig], FabricPipelineBinding]
FabricDatasetOutcomeReader = Callable[[UUID], DatasetDispatchOutcome | None]

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


class FabricPipelineBackend:
    """Execute dataset requests through a reusable Fabric Data Pipeline item."""

    def __init__(
        self,
        *,
        transport: FabricPipelineTransport,
        binding_resolver: FabricPipelineBindingResolver,
        outcome_reader: FabricDatasetOutcomeReader,
    ) -> None:
        self._transport = transport
        self._binding_resolver = binding_resolver
        self._outcome_reader = outcome_reader

    @staticmethod
    def _record_backend_failure(
        repository: ControlPlaneRepository,
        *,
        pipeline_run_id: UUID,
        dataset_run_id: UUID,
        effective: EffectiveDatasetConfig,
        run_mode: RunMode,
        status: DatasetStatus,
        error_code: str,
        error_message: str,
        retryable: bool | None,
    ) -> DatasetDispatchOutcome:
        repository.record_dataset_run(
            DatasetRunAudit(
                dataset_run_id=dataset_run_id,
                pipeline_run_id=pipeline_run_id,
                dataset_id=effective.config.dataset_id,
                attempt=1,
                run_mode=run_mode,
                status=status,
                effective_config_hash=effective.effective_config_hash,
                error_code=error_code,
                error_message=error_message,
                retryable=retryable,
            )
        )
        return DatasetDispatchOutcome(
            dataset_run_id=dataset_run_id,
            status=status,
            retryable=retryable,
            error_code=error_code,
            error_message=error_message,
        )

    def execute_one(
        self,
        *,
        repository: ControlPlaneRepository,
        pipeline_run_id: UUID,
        effective: EffectiveDatasetConfig,
        run_mode: RunMode,
    ) -> DatasetDispatchOutcome:
        dataset_run_id = uuid4()
        execution_plan = compile_execution_plan(effective, run_mode=run_mode)
        invocation = FabricPipelineInvocation(
            pipeline_run_id=pipeline_run_id,
            dataset_run_id=dataset_run_id,
            dataset_id=effective.config.dataset_id,
            run_mode=run_mode,
            attempt=1,
            effective_config_hash=effective.effective_config_hash,
            execution_plan=execution_plan,
            binding=self._binding_resolver(effective),
        )
        try:
            evidence = self._transport.invoke(invocation)
        except FabricRestError as exc:
            return self._record_backend_failure(
                repository,
                pipeline_run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                effective=effective,
                run_mode=run_mode,
                status=DatasetStatus.FAILED,
                error_code=exc.error_code or "FABRIC_REST_ERROR",
                error_message=f"{type(exc).__name__}: {exc}",
                retryable=exc.retriable,
            )
        except Exception as exc:  # provider boundary; sibling datasets must continue
            return self._record_backend_failure(
                repository,
                pipeline_run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                effective=effective,
                run_mode=run_mode,
                status=DatasetStatus.FAILED,
                error_code="FABRIC_PIPELINE_EXCEPTION",
                error_message=f"{type(exc).__name__}: {exc}",
                retryable=None,
            )

        if evidence.status is FabricJobStatus.DEDUPED:
            return self._record_backend_failure(
                repository,
                pipeline_run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                effective=effective,
                run_mode=run_mode,
                status=DatasetStatus.BLOCKED,
                error_code="FABRIC_PIPELINE_DEDUPED",
                error_message=(
                    f"Fabric job {evidence.job_instance_id} was deduped; this dataset run "
                    "has no proof of execution"
                ),
                retryable=True,
            )
        if evidence.status is FabricJobStatus.CANCELLED:
            return self._record_backend_failure(
                repository,
                pipeline_run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                effective=effective,
                run_mode=run_mode,
                status=DatasetStatus.CANCELLED,
                error_code="FABRIC_PIPELINE_CANCELLED",
                error_message=f"Fabric job {evidence.job_instance_id} was cancelled",
                retryable=None,
            )
        if evidence.status is FabricJobStatus.FAILED:
            return self._record_backend_failure(
                repository,
                pipeline_run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                effective=effective,
                run_mode=run_mode,
                status=DatasetStatus.FAILED,
                error_code="FABRIC_PIPELINE_FAILED",
                error_message=(
                    f"Fabric job {evidence.job_instance_id} failed; "
                    f"root_activity_id={evidence.root_activity_id}; "
                    f"failure_reason={evidence.failure_reason!r}"
                ),
                retryable=None,
            )
        if evidence.status is not FabricJobStatus.COMPLETED:
            return self._record_backend_failure(
                repository,
                pipeline_run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                effective=effective,
                run_mode=run_mode,
                status=DatasetStatus.FAILED,
                error_code="FABRIC_PIPELINE_NON_TERMINAL",
                error_message=(
                    f"Fabric transport returned non-terminal status {evidence.status.value} "
                    f"for job {evidence.job_instance_id}"
                ),
                retryable=None,
            )

        outcome = self._outcome_reader(dataset_run_id)
        if outcome is None:
            return self._record_backend_failure(
                repository,
                pipeline_run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                effective=effective,
                run_mode=run_mode,
                status=DatasetStatus.FAILED,
                error_code="FABRIC_PIPELINE_RESULT_MISSING",
                error_message=(
                    f"Fabric job {evidence.job_instance_id} completed but no durable framework "
                    f"dataset outcome exists for {dataset_run_id}"
                ),
                retryable=None,
            )
        if outcome.dataset_run_id != dataset_run_id:
            return self._record_backend_failure(
                repository,
                pipeline_run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                effective=effective,
                run_mode=run_mode,
                status=DatasetStatus.FAILED,
                error_code="FABRIC_PIPELINE_RESULT_MISMATCH",
                error_message=(
                    f"Fabric job {evidence.job_instance_id} completed but outcome reader returned "
                    f"dataset_run_id={outcome.dataset_run_id}, expected {dataset_run_id}"
                ),
                retryable=None,
            )
        if outcome.status not in _TERMINAL_DATASET_STATUSES:
            return self._record_backend_failure(
                repository,
                pipeline_run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                effective=effective,
                run_mode=run_mode,
                status=DatasetStatus.FAILED,
                error_code="FABRIC_PIPELINE_RESULT_NON_TERMINAL",
                error_message=(
                    f"Fabric job {evidence.job_instance_id} completed but framework outcome "
                    f"status {outcome.status.value} is non-terminal"
                ),
                retryable=None,
            )
        return outcome

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
        selected_ids = tuple(dataset_ids)
        if not selected_ids:
            return {}
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        outcomes: dict[str, DatasetDispatchOutcome] = {}
        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            future_to_dataset = {
                pool.submit(
                    self.execute_one,
                    repository=repository,
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


__all__ = [
    "FabricDatasetOutcomeReader",
    "FabricPipelineBackend",
    "FabricPipelineBindingResolver",
]
