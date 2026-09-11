"""Operational health for derived current projections using existing OPS state."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Engine, desc, select

from fabric_data_framework.contracts.current_projection import (
    CurrentProjectionHealth,
    CurrentProjectionMode,
    evaluate_current_projection_health,
)
from fabric_data_framework.metadata.config import DatasetConfig, DatasetStatus
from .io import read_cdc_checkpoint
from .schema import dataset_run


def read_current_projection_health(
    engine: Engine,
    *,
    config: DatasetConfig,
    history_latest_delta_version: int,
) -> CurrentProjectionHealth:
    """Report Mode-3 lag from the existing CDC checkpoint and dataset-run audit tables."""

    projection = config.current_projection
    if projection is None or projection.mode is not CurrentProjectionMode.DELTA_PROJECTION:
        raise ValueError("current projection health is only defined for DELTA_PROJECTION datasets")

    state = read_cdc_checkpoint(engine, config.dataset_id)
    processed_version: int | None = None
    if state is not None:
        partition = f"delta-cdf:{config.source.object}"
        position = state.checkpoint.position_for(partition)
        if position is None or not position:
            raise RuntimeError(
                "persisted projection checkpoint does not match the configured history source"
            )
        processed_version = position[0]

    with engine.connect() as connection:
        last_run = connection.execute(
            select(dataset_run.c.dataset_run_id)
            .where(
                dataset_run.c.dataset_id == config.dataset_id,
                dataset_run.c.status == DatasetStatus.SUCCEEDED.value,
            )
            .order_by(desc(dataset_run.c.completed_at), desc(dataset_run.c.started_at))
            .limit(1)
        ).scalar_one_or_none()

    return evaluate_current_projection_health(
        dataset_id=config.dataset_id,
        history_latest_delta_version=history_latest_delta_version,
        processed_version=processed_version,
        lag_warning_versions=projection.lag_warning_versions,
        lag_error_versions=projection.lag_error_versions,
        last_successful_projection_run_id=UUID(str(last_run)) if last_run is not None else None,
    )


__all__ = ["read_current_projection_health"]
