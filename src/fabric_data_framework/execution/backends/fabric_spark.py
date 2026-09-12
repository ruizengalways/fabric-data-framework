"""Fabric Spark dataset executor for current projections.

This is the child-runtime dispatch boundary used inside a Fabric Spark execution.  VIEW
and MATERIALIZED projections execute their deployment/refresh SQL; DELTA_PROJECTION is
routed to the distributed history-CDF runtime and persists a terminal dataset audit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import Engine

from fabric_data_framework.adapters.fabric.current_projection import (
    FabricSparkDeltaCurrentProjectionRuntime,
    SparkCurrentProjectionEvidence,
    SparkProjectionReconciliation,
    SparkSessionLike,
)
from fabric_data_framework.contracts.audit import DatasetRunAudit, MutationCounts
from fabric_data_framework.contracts.current_projection import CurrentProjectionMode
from fabric_data_framework.contracts.dispatch import DatasetDispatchOutcome, DatasetDispatchRequest
from fabric_data_framework.control_plane.repository import ControlPlaneRepository
from fabric_data_framework.deployment.current_projection import (
    compile_current_projection_deployment,
)
from fabric_data_framework.evidence.safety import sanitize_audit_text
from fabric_data_framework.metadata.config import DatasetStatus, EffectiveDatasetConfig, RunMode


ProjectionReconciliationResolver = Callable[
    [EffectiveDatasetConfig], SparkProjectionReconciliation | None
]


class FabricSparkCurrentProjectionExecutor:
    """Execute one CURRENT_PROJECTION DatasetDispatchRequest in Fabric Spark."""

    def __init__(
        self,
        *,
        spark: SparkSessionLike,
        control_plane_engine: Engine,
        repository: ControlPlaneRepository,
        reconciliation_resolver: ProjectionReconciliationResolver | None = None,
    ) -> None:
        self._spark = spark
        self._control_plane_engine = control_plane_engine
        self._repository = repository
        self._reconciliation_resolver = reconciliation_resolver
        self._delta = FabricSparkDeltaCurrentProjectionRuntime(spark)

    def _reconcile_for(
        self,
        effective: EffectiveDatasetConfig,
    ) -> SparkProjectionReconciliation | None:
        config = effective.config
        if self._reconciliation_resolver is not None:
            resolved = self._reconciliation_resolver(effective)
            if resolved is not None:
                return resolved
        # Built-in exact target-vs-history verification is sufficient when no extra
        # declarative provider observations were requested.  Configured checks require
        # an implementation-owned observation/reconciliation resolver and fail closed.
        if config.reconciliation.checks:
            return None
        return lambda evidence: isinstance(evidence, SparkCurrentProjectionEvidence)

    def _record(
        self,
        request: DatasetDispatchRequest,
        *,
        status: DatasetStatus,
        mutations: MutationCounts = MutationCounts(),
        error_code: str | None = None,
        error_message: str | None = None,
        retryable: bool | None = None,
    ) -> DatasetDispatchOutcome:
        completed = datetime.now(timezone.utc)
        safe_message = sanitize_audit_text(error_message) if error_message is not None else None
        self._repository.record_dataset_run(
            DatasetRunAudit(
                dataset_run_id=request.dataset_run_id,
                pipeline_run_id=request.pipeline_run_id,
                dataset_id=request.dataset_id,
                attempt=request.attempt,
                run_mode=request.run_mode,
                status=status,
                effective_config_hash=request.effective_config.effective_config_hash,
                mutations=mutations,
                error_code=error_code,
                error_message=safe_message,
                retryable=retryable,
                started_at=completed,
                completed_at=completed,
            )
        )
        return DatasetDispatchOutcome(
            dataset_run_id=request.dataset_run_id,
            status=status,
            retryable=retryable,
            error_code=error_code,
            error_message=safe_message,
        )

    def __call__(self, request: DatasetDispatchRequest) -> DatasetDispatchOutcome:
        config = request.effective_config.config
        projection = config.current_projection
        if projection is None:
            return self._record(
                request,
                status=DatasetStatus.FAILED,
                error_code="SPARK_PROJECTION_CONFIG_MISSING",
                error_message="Fabric Spark current-projection executor received a non-projection dataset",
                retryable=False,
            )
        plan = compile_current_projection_deployment(config)
        try:
            if projection.mode is CurrentProjectionMode.VIEW:
                if plan.create_or_replace_sql is None:
                    raise RuntimeError("VIEW projection deployment SQL is missing")
                self._spark.sql(plan.create_or_replace_sql)
                return self._record(request, status=DatasetStatus.SUCCEEDED)

            if projection.mode is CurrentProjectionMode.MATERIALIZED:
                sql = (
                    plan.create_or_replace_sql
                    if request.run_mode is RunMode.FULL_REBUILD
                    else plan.refresh_sql or plan.create_or_replace_sql
                )
                if sql is None:
                    raise RuntimeError("MATERIALIZED projection SQL is missing")
                self._spark.sql(sql)
                return self._record(request, status=DatasetStatus.SUCCEEDED)

            if projection.mode is not CurrentProjectionMode.DELTA_PROJECTION:
                raise RuntimeError(f"unsupported current projection mode: {projection.mode}")

            columns = tuple(field.name for field in config.schema_contract.fields)  # type: ignore[union-attr]
            reconcile = self._reconcile_for(request.effective_config)
            if config.reconciliation.required_for_state_commit and reconcile is None:
                raise RuntimeError(
                    "projection reconciliation policy contains checks but no Fabric observation resolver was provided"
                )
            kwargs = dict(
                control_plane_engine=self._control_plane_engine,
                dataset_id=config.dataset_id,
                dataset_run_id=request.dataset_run_id,
                history_table=config.source.object,
                target_table=f"{config.target.layer}.{config.target.object}",
                business_key=config.load.business_key,
                projected_columns=columns,
                current_flag_column=projection.history_current_flag_column,
                reconciliation_required=config.reconciliation.required_for_state_commit,
                reconcile=reconcile,
            )
            if request.run_mode is RunMode.FULL_REBUILD:
                result = self._delta.rebuild(**kwargs)
            else:
                result = self._delta.execute_incremental(**kwargs)
            return self._record(
                request,
                status=DatasetStatus.SUCCEEDED,
                mutations=result.mutations,
            )
        except Exception as exc:
            return self._record(
                request,
                status=DatasetStatus.FAILED,
                error_code="FABRIC_SPARK_CURRENT_PROJECTION_FAILED",
                error_message=f"{type(exc).__name__}: {exc}",
                retryable=None,
            )


__all__ = [
    "FabricSparkCurrentProjectionExecutor",
    "ProjectionReconciliationResolver",
]
