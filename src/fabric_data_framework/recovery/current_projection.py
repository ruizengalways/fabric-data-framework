"""Governed current-projection physical mode transitions and checkpoint reset."""

from __future__ import annotations

from builtins import ExceptionGroup
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import Engine

from fabric_data_framework.adapters.fabric.current_projection import (
    FabricSparkDeltaCurrentProjectionRuntime,
    SparkProjectionReconciliation,
    SparkSessionLike,
)
from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.current_projection import (
    CurrentProjectionMode,
    MaterializedCurrentImplementation,
)
from fabric_data_framework.control_plane.current_projection_transition import (
    CurrentProjectionTransitionEvent,
    ProjectionTransitionStatus,
    complete_projection_transition,
    record_projection_transition_event,
)
from fabric_data_framework.control_plane.io import read_cdc_checkpoint
from fabric_data_framework.deployment.current_projection import (
    compile_current_projection_deployment,
    quote_spark_relation,
)
from fabric_data_framework.metadata.config import DatasetConfig


class CurrentProjectionModeTransitionError(RuntimeError):
    pass


class CurrentProjectionModeTransitionResult(FrozenModel):
    transition_id: UUID
    dataset_id: str = Field(min_length=1)
    from_mode: CurrentProjectionMode
    to_mode: CurrentProjectionMode
    checkpoint_reset: bool
    completed_event_id: UUID


class FabricSparkProjectionTransitionCoordinator:
    """Change physical current representation without creating a second truth.

    The source-controlled desired config is supplied explicitly.  Leaving Mode 3 resets
    only the exact checkpoint observed before physical replacement; entering Mode 3
    performs a full authoritative-history rebuild that establishes the new checkpoint.
    Every attempt emits append-only STARTED/FAILED/COMPLETED evidence.
    """

    def __init__(self, *, spark: SparkSessionLike, control_plane_engine: Engine) -> None:
        self.spark = spark
        self.control_plane_engine = control_plane_engine
        self.delta = FabricSparkDeltaCurrentProjectionRuntime(spark)

    @staticmethod
    def _target(config: DatasetConfig) -> str:
        return f"{config.target.layer}.{config.target.object}"

    def _drop_previous(self, config: DatasetConfig) -> None:
        projection = config.current_projection
        if projection is None:
            raise CurrentProjectionModeTransitionError("previous config is not a projection")
        target = quote_spark_relation(self._target(config))
        if projection.mode is CurrentProjectionMode.VIEW:
            self.spark.sql(f"DROP VIEW IF EXISTS {target}")
            return
        if projection.mode is CurrentProjectionMode.DELTA_PROJECTION:
            self.spark.sql(f"DROP TABLE IF EXISTS {target}")
            return
        implementation = projection.materialized_implementation
        if implementation is MaterializedCurrentImplementation.AUTO:
            implementation = MaterializedCurrentImplementation.FABRIC_MATERIALIZED_LAKE_VIEW
        if implementation is MaterializedCurrentImplementation.FABRIC_MATERIALIZED_LAKE_VIEW:
            self.spark.sql(f"DROP MATERIALIZED LAKE VIEW IF EXISTS {target}")
        else:
            self.spark.sql(f"DROP TABLE IF EXISTS {target}")

    def _deploy_non_delta(self, config: DatasetConfig) -> None:
        plan = compile_current_projection_deployment(config)
        if plan.mode is CurrentProjectionMode.DELTA_PROJECTION:
            raise CurrentProjectionModeTransitionError("non-delta deploy received DELTA_PROJECTION")
        if plan.enable_history_cdf_sql is not None:
            self.spark.sql(plan.enable_history_cdf_sql)
        if plan.create_or_replace_sql is None:
            raise CurrentProjectionModeTransitionError("projection deployment SQL is missing")
        self.spark.sql(plan.create_or_replace_sql)

    def transition(
        self,
        *,
        previous: DatasetConfig,
        desired: DatasetConfig,
        dataset_run_id: UUID,
        actor: str,
        reason: str,
        ticket_reference: str | None = None,
        transition_id: UUID | None = None,
        reconcile: SparkProjectionReconciliation | None = None,
    ) -> CurrentProjectionModeTransitionResult:
        if previous.dataset_id != desired.dataset_id:
            raise ValueError("projection transition configs must have the same dataset_id")
        if self._target(previous) != self._target(desired):
            raise ValueError("projection mode transition cannot change the stable consumer target")
        old = previous.current_projection
        new = desired.current_projection
        if old is None or new is None:
            raise ValueError("projection transition requires projection configs on both sides")
        transition_id = transition_id or uuid4()
        checkpoint = read_cdc_checkpoint(self.control_plane_engine, desired.dataset_id)
        checkpoint_version = checkpoint.version if checkpoint is not None else None
        leaving_delta = (
            old.mode is CurrentProjectionMode.DELTA_PROJECTION
            and new.mode is not CurrentProjectionMode.DELTA_PROJECTION
        )
        entering_delta = (
            old.mode is not CurrentProjectionMode.DELTA_PROJECTION
            and new.mode is CurrentProjectionMode.DELTA_PROJECTION
        )
        if leaving_delta and checkpoint is None:
            raise CurrentProjectionModeTransitionError(
                "leaving DELTA_PROJECTION requires an existing checkpoint for exact governed reset"
            )
        if entering_delta and checkpoint is not None:
            raise CurrentProjectionModeTransitionError(
                "entering DELTA_PROJECTION requires no pre-existing projection checkpoint"
            )
        if old.mode is not CurrentProjectionMode.DELTA_PROJECTION and checkpoint is not None:
            raise CurrentProjectionModeTransitionError(
                "non-delta projection unexpectedly owns CDC state; explicit recovery is required"
            )

        started = CurrentProjectionTransitionEvent(
            transition_id=transition_id,
            dataset_id=desired.dataset_id,
            from_mode=old.mode,
            to_mode=new.mode,
            status=ProjectionTransitionStatus.STARTED,
            actor=actor,
            reason=reason,
            ticket_reference=ticket_reference,
            checkpoint_version_before=checkpoint_version,
        )
        record_projection_transition_event(self.control_plane_engine, started)

        try:
            self._drop_previous(previous)
            if new.mode is CurrentProjectionMode.DELTA_PROJECTION:
                plan = compile_current_projection_deployment(desired)
                if plan.enable_history_cdf_sql is None:
                    raise CurrentProjectionModeTransitionError(
                        "DELTA_PROJECTION deployment must enable authoritative history CDF"
                    )
                self.spark.sql(plan.enable_history_cdf_sql)
                columns = tuple(field.name for field in desired.schema_contract.fields)  # type: ignore[union-attr]
                result = self.delta.rebuild(
                    control_plane_engine=self.control_plane_engine,
                    dataset_id=desired.dataset_id,
                    dataset_run_id=dataset_run_id,
                    history_table=desired.source.object,
                    target_table=self._target(desired),
                    business_key=desired.load.business_key,
                    projected_columns=columns,
                    current_flag_column=new.history_current_flag_column,
                    reconciliation_required=desired.reconciliation.required_for_state_commit,
                    reconcile=reconcile,
                )
                completed = complete_projection_transition(
                    self.control_plane_engine,
                    transition_id=transition_id,
                    dataset_id=desired.dataset_id,
                    from_mode=old.mode,
                    to_mode=new.mode,
                    actor=actor,
                    reason=reason,
                    ticket_reference=ticket_reference,
                    expected_checkpoint_version=result.checkpoint_version,
                    reset_checkpoint=False,
                    detail=f"rebuilt from authoritative history version {result.upper_processed_version}",
                )
            else:
                self._deploy_non_delta(desired)
                completed = complete_projection_transition(
                    self.control_plane_engine,
                    transition_id=transition_id,
                    dataset_id=desired.dataset_id,
                    from_mode=old.mode,
                    to_mode=new.mode,
                    actor=actor,
                    reason=reason,
                    ticket_reference=ticket_reference,
                    expected_checkpoint_version=checkpoint_version,
                    reset_checkpoint=leaving_delta,
                    detail="physical current representation replaced from authoritative history",
                )
        except Exception as exc:
            failed = CurrentProjectionTransitionEvent(
                transition_id=transition_id,
                dataset_id=desired.dataset_id,
                from_mode=old.mode,
                to_mode=new.mode,
                status=ProjectionTransitionStatus.FAILED,
                actor=actor,
                reason=reason,
                ticket_reference=ticket_reference,
                checkpoint_version_before=checkpoint_version,
                detail=f"{type(exc).__name__}: {exc}",
            )
            try:
                record_projection_transition_event(self.control_plane_engine, failed)
            except Exception as audit_exc:
                raise ExceptionGroup(
                    "projection transition and transition audit both failed",
                    (exc, audit_exc),
                ) from exc
            raise

        return CurrentProjectionModeTransitionResult(
            transition_id=transition_id,
            dataset_id=desired.dataset_id,
            from_mode=old.mode,
            to_mode=new.mode,
            checkpoint_reset=leaving_delta,
            completed_event_id=completed.event_id,
        )


__all__ = [
    "CurrentProjectionModeTransitionError",
    "CurrentProjectionModeTransitionResult",
    "FabricSparkProjectionTransitionCoordinator",
]
