"""Control-plane repository contracts and a deterministic in-memory test adapter."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Protocol, runtime_checkable
from uuid import UUID

from .config import DatasetConfig
from .operations import (
    DatasetRunAudit,
    PipelineRunAudit,
    QuarantineBatch,
    ReconciliationResult,
    StepRunAudit,
)
from .runtime import WatermarkPosition


@runtime_checkable
class ControlPlaneRepository(Protocol):
    def deploy_dataset(self, config: DatasetConfig) -> None: ...
    def get_dataset(self, dataset_id: str) -> DatasetConfig: ...
    def list_datasets(self) -> tuple[DatasetConfig, ...]: ...
    def get_watermark(self, dataset_id: str) -> WatermarkPosition | None: ...
    def commit_watermark(self, dataset_id: str, position: WatermarkPosition) -> None: ...
    def record_pipeline_run(self, audit: PipelineRunAudit) -> None: ...
    def record_dataset_run(self, audit: DatasetRunAudit) -> None: ...
    def record_step_run(self, audit: StepRunAudit) -> None: ...
    def record_reconciliation(self, result: ReconciliationResult) -> None: ...
    def record_quarantine(self, batch: QuarantineBatch) -> None: ...


class InMemoryControlPlane:
    """Small environment-local adapter used by framework/domain integration tests.

    It intentionally models only control-plane state; business target rows live in a
    separate target adapter. The adapter is lock-protected because the reference
    dispatcher may execute independent datasets concurrently.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._datasets: dict[str, DatasetConfig] = {}
        self._watermarks: dict[str, WatermarkPosition] = {}
        self.pipeline_runs: list[PipelineRunAudit] = []
        self.dataset_runs: list[DatasetRunAudit] = []
        self.step_runs: list[StepRunAudit] = []
        self.reconciliation_results: list[ReconciliationResult] = []
        self.quarantine_batches: list[QuarantineBatch] = []

    def deploy_dataset(self, config: DatasetConfig) -> None:
        with self._lock:
            self._datasets[config.dataset_id] = config

    def get_dataset(self, dataset_id: str) -> DatasetConfig:
        with self._lock:
            try:
                return self._datasets[dataset_id]
            except KeyError as exc:
                raise KeyError(f"dataset not deployed: {dataset_id}") from exc

    def list_datasets(self) -> tuple[DatasetConfig, ...]:
        with self._lock:
            return tuple(deepcopy(self._datasets[key]) for key in sorted(self._datasets))

    def get_watermark(self, dataset_id: str) -> WatermarkPosition | None:
        with self._lock:
            position = self._watermarks.get(dataset_id)
            return deepcopy(position)

    def commit_watermark(self, dataset_id: str, position: WatermarkPosition) -> None:
        with self._lock:
            if dataset_id not in self._datasets:
                raise KeyError(f"dataset not deployed: {dataset_id}")
            self._watermarks[dataset_id] = deepcopy(position)

    def record_pipeline_run(self, audit: PipelineRunAudit) -> None:
        with self._lock:
            for index, existing in enumerate(self.pipeline_runs):
                if existing.pipeline_run_id == audit.pipeline_run_id:
                    self.pipeline_runs[index] = audit
                    return
            self.pipeline_runs.append(audit)

    def record_dataset_run(self, audit: DatasetRunAudit) -> None:
        with self._lock:
            self.dataset_runs.append(audit)

    def record_step_run(self, audit: StepRunAudit) -> None:
        with self._lock:
            self.step_runs.append(audit)

    def record_reconciliation(self, result: ReconciliationResult) -> None:
        with self._lock:
            self.reconciliation_results.append(result)

    def record_quarantine(self, batch: QuarantineBatch) -> None:
        with self._lock:
            self.quarantine_batches.append(batch)

    def quarantines_for_run(self, dataset_run_id: UUID) -> tuple[QuarantineBatch, ...]:
        with self._lock:
            return tuple(
                item for item in self.quarantine_batches if item.dataset_run_id == dataset_run_id
            )
