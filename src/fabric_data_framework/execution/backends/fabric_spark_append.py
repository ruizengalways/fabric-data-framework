"""Fabric Spark child executor for distributed APPEND batches."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import Engine

from fabric_data_framework.adapters.fabric.append import (
    FabricSparkDeltaAppendRuntime,
    SparkDeltaAppendRequest,
)
from fabric_data_framework.adapters.fabric.spark_protocols import SparkSessionLike
from fabric_data_framework.contracts.audit import DatasetRunAudit, MutationCounts, RowAccounting
from fabric_data_framework.contracts.audit_safety import sanitize_audit_text
from fabric_data_framework.contracts.dispatch import DatasetDispatchOutcome, DatasetDispatchRequest
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationObservation,
    ReconciliationStatus,
)
from fabric_data_framework.contracts.temporal import utc_now
from fabric_data_framework.control_plane.repository import ControlPlaneRepository
from fabric_data_framework.metadata.config import ApplyStrategy, DatasetStatus
from fabric_data_framework.quality.reconciliation.append import reconcile_append


@dataclass(frozen=True)
class SparkAppendBatch:
    """Distributed accepted/staged relation plus framework accounting for one run."""

    incoming_relation: str
    accounting: RowAccounting
    observations: tuple[ReconciliationObservation, ...] = ()


@dataclass(frozen=True)
class _AppendRunOutcome:
    status: DatasetStatus
    mutations: MutationCounts = field(default_factory=MutationCounts)
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool | None = None


AppendBatchResolver = Callable[[DatasetDispatchRequest], SparkAppendBatch]


class FabricSparkAppendExecutor:
    """Bind a distributed staged relation to the Spark/Delta APPEND runtime."""

    def __init__(
        self,
        *,
        spark: SparkSessionLike,
        control_plane_engine: Engine,
        repository: ControlPlaneRepository,
        batch_resolver: AppendBatchResolver,
    ) -> None:
        self._runtime = FabricSparkDeltaAppendRuntime(spark)
        self._control_plane_engine = control_plane_engine
        self._repository = repository
        self._batch_resolver = batch_resolver

    def _record(
        self,
        request: DatasetDispatchRequest,
        outcome: _AppendRunOutcome,
    ) -> DatasetDispatchOutcome:
        completed = utc_now()
        safe_message = (
            sanitize_audit_text(outcome.error_message)
            if outcome.error_message is not None
            else None
        )
        self._repository.record_dataset_run(
            DatasetRunAudit(
                dataset_run_id=request.dataset_run_id,
                pipeline_run_id=request.pipeline_run_id,
                dataset_id=request.dataset_id,
                attempt=request.attempt,
                run_mode=request.run_mode,
                status=outcome.status,
                effective_config_hash=request.effective_config.effective_config_hash,
                mutations=outcome.mutations,
                error_code=outcome.error_code,
                error_message=safe_message,
                retryable=outcome.retryable,
                started_at=completed,
                completed_at=completed,
            )
        )
        return DatasetDispatchOutcome(
            dataset_run_id=request.dataset_run_id,
            status=outcome.status,
            retryable=outcome.retryable,
            error_code=outcome.error_code,
            error_message=safe_message,
        )

    def __call__(self, request: DatasetDispatchRequest) -> DatasetDispatchOutcome:
        config = request.effective_config.config
        if config.load.apply_strategy is not ApplyStrategy.APPEND:
            return self._record(
                request,
                _AppendRunOutcome(
                    status=DatasetStatus.FAILED,
                    error_code="SPARK_APPEND_CONFIG_MISMATCH",
                    error_message="Fabric Spark APPEND executor received a non-APPEND dataset",
                    retryable=False,
                ),
            )
        if config.schema_contract is None:
            return self._record(
                request,
                _AppendRunOutcome(
                    status=DatasetStatus.FAILED,
                    error_code="SPARK_APPEND_SCHEMA_REQUIRED",
                    error_message="distributed APPEND requires an explicit schema_contract",
                    retryable=False,
                ),
            )

        mutations = MutationCounts()
        try:
            batch = self._batch_resolver(request)
            business_columns = tuple(field.name for field in config.schema_contract.fields)
            evidence = self._runtime.execute(
                control_plane_engine=self._control_plane_engine,
                request=SparkDeltaAppendRequest(
                    dataset_id=config.dataset_id,
                    dataset_run_id=request.dataset_run_id,
                    incoming_relation=batch.incoming_relation,
                    target_table=f"{config.target.layer}.{config.target.object}",
                    append_identity=config.load.append_identity,
                    business_columns=business_columns,
                    expected_incoming_rows=batch.accounting.rows_accepted,
                ),
            )
            mutations = evidence.mutations
            reconciliation = reconcile_append(
                dataset_run_id=request.dataset_run_id,
                dataset_id=config.dataset_id,
                policy=config.reconciliation,
                accounting=batch.accounting,
                inserted=evidence.inserted,
                replayed=evidence.replayed,
                duplicate_incoming=evidence.duplicate_incoming,
                observations=batch.observations,
            )
            self._repository.record_reconciliation(reconciliation)
            blocked = (
                reconciliation.blocks_state_advance
                and reconciliation.status is ReconciliationStatus.FAIL
            )
            if blocked:
                return self._record(
                    request,
                    _AppendRunOutcome(
                        status=DatasetStatus.FAILED,
                        mutations=mutations,
                        error_code="RECONCILIATION_FAILED",
                        error_message=(
                            "required APPEND reconciliation failed after idempotent target mutation; "
                            "source/framework state must not advance"
                        ),
                    ),
                )
            return self._record(
                request,
                _AppendRunOutcome(
                    status=DatasetStatus.SUCCEEDED,
                    mutations=mutations,
                ),
            )
        except Exception as exc:
            return self._record(
                request,
                _AppendRunOutcome(
                    status=DatasetStatus.FAILED,
                    mutations=mutations,
                    error_code="FABRIC_SPARK_APPEND_FAILED",
                    error_message=f"{type(exc).__name__}: {exc}",
                ),
            )


__all__ = ["AppendBatchResolver", "FabricSparkAppendExecutor", "SparkAppendBatch"]
