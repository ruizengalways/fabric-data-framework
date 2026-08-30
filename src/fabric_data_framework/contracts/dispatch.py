"""Stable orchestration request/result contracts shared by execution backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID

from fabric_data_framework.metadata.config import DatasetStatus, EffectiveDatasetConfig, PipelineStatus, RunMode
from .execution_plan import ExecutionPlan


@dataclass(frozen=True)
class DatasetDispatchRequest:
    """Immutable request passed from orchestration into one dataset executor."""

    pipeline_run_id: UUID
    dataset_run_id: UUID
    dataset_id: str
    run_mode: RunMode
    effective_config: EffectiveDatasetConfig
    execution_plan: ExecutionPlan
    attempt: int = 1


@dataclass(frozen=True)
class DatasetDispatchOutcome:
    """Terminal dataset outcome consumed by the parent orchestration layer."""

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
