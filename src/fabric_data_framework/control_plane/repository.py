"""Control-plane repository contracts and a deterministic in-memory test adapter."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Protocol, runtime_checkable
from uuid import UUID

from fabric_data_framework.metadata.config import DatasetConfig
from ..contracts.capture_receipt import CaptureReceipt
from ..contracts.dispatch import DatasetDispatchOutcome
from ..contracts.recovery import DatasetAttemptLineage, ReprocessRequest
from fabric_data_framework.contracts.audit import (
    DatasetRunAudit,
    PipelineRunAudit,
    StepRunAudit,
)
from fabric_data_framework.contracts.quarantine import QuarantineBatch
from fabric_data_framework.contracts.reconciliation import ReconciliationResult
from fabric_data_framework.contracts.runtime import WatermarkPosition


@runtime_checkable
class ControlPlaneRepository(Protocol):
    def deploy_dataset(self, config: DatasetConfig) -> None: ...
    def get_dataset(self, dataset_id: str) -> DatasetConfig: ...
    def list_datasets(self) -> tuple[DatasetConfig, ...]: ...
    def get_watermark(self, dataset_id: str) -> WatermarkPosition | None: ...
    def commit_watermark(self, dataset_id: str, position: WatermarkPosition) -> None: ...
    def record_pipeline_run(self, audit: PipelineRunAudit) -> None: ...
    def record_dataset_run(self, audit: DatasetRunAudit) -> None: ...
    def get_dataset_outcome(self, dataset_run_id: UUID) -> DatasetDispatchOutcome | None: ...
    def record_capture_receipt(self, receipt: CaptureReceipt) -> None: ...
    def record_step_run(self, audit: StepRunAudit) -> None: ...
    def record_reconciliation(self, result: ReconciliationResult) -> None: ...
    def record_quarantine(self, batch: QuarantineBatch) -> None: ...
    def record_attempt_lineage(self, lineage: DatasetAttemptLineage) -> None: ...
    def record_reprocess_request(self, request: ReprocessRequest) -> None: ...


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
        self.capture_receipts: list[CaptureReceipt] = []
        self.step_runs: list[StepRunAudit] = []
        self.reconciliation_results: list[ReconciliationResult] = []
        self.quarantine_batches: list[QuarantineBatch] = []
        self.attempt_lineage: list[DatasetAttemptLineage] = []
        self.reprocess_requests: list[ReprocessRequest] = []

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
            for index, existing in enumerate(self.dataset_runs):
                if existing.dataset_run_id == audit.dataset_run_id:
                    if (
                        existing.pipeline_run_id != audit.pipeline_run_id
                        or existing.dataset_id != audit.dataset_id
                        or existing.attempt != audit.attempt
                        or existing.run_mode is not audit.run_mode
                        or existing.effective_config_hash != audit.effective_config_hash
                    ):
                        raise ValueError("dataset run semantic identity cannot change")
                    self.dataset_runs[index] = audit
                    return
            self.dataset_runs.append(audit)

    def get_dataset_outcome(self, dataset_run_id: UUID) -> DatasetDispatchOutcome | None:
        with self._lock:
            for audit in reversed(self.dataset_runs):
                if audit.dataset_run_id == dataset_run_id:
                    return DatasetDispatchOutcome(
                        dataset_run_id=dataset_run_id,
                        status=audit.status,
                        retryable=audit.retryable,
                        error_code=audit.error_code,
                        error_message=audit.error_message,
                    )
        return None

    def record_capture_receipt(self, receipt: CaptureReceipt) -> None:
        with self._lock:
            self.capture_receipts.append(deepcopy(receipt))

    def record_step_run(self, audit: StepRunAudit) -> None:
        with self._lock:
            for index, existing in enumerate(self.step_runs):
                if existing.step_run_id == audit.step_run_id:
                    if (
                        existing.dataset_run_id != audit.dataset_run_id
                        or existing.step_name != audit.step_name
                    ):
                        raise ValueError("step run semantic identity cannot change")
                    self.step_runs[index] = audit
                    return
            self.step_runs.append(audit)

    def record_reconciliation(self, result: ReconciliationResult) -> None:
        with self._lock:
            if any(
                existing.reconciliation_id == result.reconciliation_id
                for existing in self.reconciliation_results
            ):
                raise ValueError(
                    f"reconciliation {result.reconciliation_id} is already recorded"
                )
            self.reconciliation_results.append(result)

    def record_quarantine(self, batch: QuarantineBatch) -> None:
        with self._lock:
            if any(
                existing.quarantine_id == batch.quarantine_id
                for existing in self.quarantine_batches
            ):
                raise ValueError(f"quarantine batch {batch.quarantine_id} is already recorded")
            self.quarantine_batches.append(batch)

    def record_attempt_lineage(self, lineage: DatasetAttemptLineage) -> None:
        with self._lock:
            if any(
                existing.dataset_run_id == lineage.dataset_run_id
                for existing in self.attempt_lineage
            ):
                raise ValueError(
                    f"attempt lineage already recorded for {lineage.dataset_run_id}"
                )
            self.attempt_lineage.append(deepcopy(lineage))

    def record_reprocess_request(self, request: ReprocessRequest) -> None:
        with self._lock:
            for index, existing in enumerate(self.reprocess_requests):
                if existing.reprocess_request_id == request.reprocess_request_id:
                    if (
                        existing.dataset_id != request.dataset_id
                        or existing.run_mode is not request.run_mode
                        or existing.reason != request.reason
                        or existing.requested_by != request.requested_by
                        or existing.original_pipeline_run_id
                        != request.original_pipeline_run_id
                        or existing.original_dataset_run_id
                        != request.original_dataset_run_id
                        or existing.range_json != request.range_json
                    ):
                        raise ValueError("reprocess request semantic identity cannot change")
                    self.reprocess_requests[index] = deepcopy(request)
                    return
            self.reprocess_requests.append(deepcopy(request))

    def quarantines_for_run(self, dataset_run_id: UUID) -> tuple[QuarantineBatch, ...]:
        with self._lock:
            return tuple(
                item for item in self.quarantine_batches if item.dataset_run_id == dataset_run_id
            )

    def capture_receipts_for_run(self, dataset_run_id: UUID) -> tuple[CaptureReceipt, ...]:
        with self._lock:
            return tuple(
                deepcopy(item)
                for item in self.capture_receipts
                if item.dataset_run_id == dataset_run_id
            )

    def lineage_for_root(self, root_dataset_run_id: UUID) -> tuple[DatasetAttemptLineage, ...]:
        with self._lock:
            items = [
                deepcopy(item)
                for item in self.attempt_lineage
                if item.root_dataset_run_id == root_dataset_run_id
            ]
            return tuple(sorted(items, key=lambda item: item.attempt))

    def get_reprocess_request(self, request_id: UUID) -> ReprocessRequest:
        with self._lock:
            for item in self.reprocess_requests:
                if item.reprocess_request_id == request_id:
                    return deepcopy(item)
        raise KeyError(f"reprocess request not found: {request_id}")
