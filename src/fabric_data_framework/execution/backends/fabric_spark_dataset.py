"""Resolver that binds supported Fabric Spark apply strategies to physical executors."""

from __future__ import annotations

from sqlalchemy import Engine

from fabric_data_framework.adapters.fabric.spark_protocols import SparkSessionLike
from fabric_data_framework.contracts.dispatch import ExecutorResolver
from fabric_data_framework.control_plane.repository import ControlPlaneRepository
from fabric_data_framework.execution.backends.fabric_spark import (
    FabricSparkCurrentProjectionExecutor,
    ProjectionReconciliationResolver,
)
from fabric_data_framework.execution.backends.fabric_spark_append import (
    AppendBatchResolver,
    FabricSparkAppendExecutor,
)
from fabric_data_framework.metadata.config import ApplyStrategy, EffectiveDatasetConfig


def build_fabric_spark_executor_resolver(
    *,
    spark: SparkSessionLike,
    control_plane_engine: Engine,
    repository: ControlPlaneRepository,
    append_batch_resolver: AppendBatchResolver,
    projection_reconciliation_resolver: ProjectionReconciliationResolver | None = None,
) -> ExecutorResolver:
    """Return the explicit Fabric Spark resolver for physically implemented strategies."""

    append = FabricSparkAppendExecutor(
        spark=spark,
        control_plane_engine=control_plane_engine,
        repository=repository,
        batch_resolver=append_batch_resolver,
    )
    projection = FabricSparkCurrentProjectionExecutor(
        spark=spark,
        control_plane_engine=control_plane_engine,
        repository=repository,
        reconciliation_resolver=projection_reconciliation_resolver,
    )

    def resolve(effective: EffectiveDatasetConfig):
        strategy = effective.config.load.apply_strategy
        if strategy is ApplyStrategy.APPEND:
            return append
        if strategy is ApplyStrategy.CURRENT_PROJECTION:
            return projection
        raise ValueError(
            "Fabric Spark packaged executor currently supports APPEND and CURRENT_PROJECTION; "
            f"received {strategy.value}"
        )

    return resolve


__all__ = ["build_fabric_spark_executor_resolver"]
