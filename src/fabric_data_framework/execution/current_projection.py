"""Incremental history -> current projection execution with independent CDC progress.

The projection checkpoint is downstream progress over the authoritative history Delta
table. Target mutation is committed before checkpoint advance. If checkpoint commit
fails after target mutation, a retry replays the same history range and is idempotent.
No distributed transaction across the two Delta tables is assumed.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Callable, Protocol, Sequence, runtime_checkable
from uuid import UUID

from pydantic import Field
from sqlalchemy import Engine

from fabric_data_framework.adapters.cdc.delta_cdf import (
    DeltaCDFRecord,
    delta_cdf_checkpoint,
    plan_delta_cdf_resume,
)
from fabric_data_framework.apply.current_projection import (
    CurrentProjectionApplyResult,
    CurrentProjectionError,
    apply_current_projection,
)
from fabric_data_framework.contracts.audit import MutationCounts
from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.runtime import StateCommitGate
from fabric_data_framework.control_plane.io import (
    CDCCheckpointState,
    commit_cdc_checkpoint,
    read_cdc_checkpoint,
)


class CurrentProjectionExecutionError(RuntimeError):
    pass


@runtime_checkable
class CurrentProjectionTarget(Protocol):
    """Physical current-target boundary used by the incremental projection executor."""

    def read(self) -> tuple[dict[str, object], ...]: ...

    def apply_projection(
        self,
        result: CurrentProjectionApplyResult,
        *,
        business_key: tuple[str, ...],
    ) -> MutationCounts: ...


class InMemoryCurrentProjectionTarget:
    """Deterministic reference target for tests and certification."""

    def __init__(self, rows: Sequence[dict[str, object]] = ()) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)

    def read(self) -> tuple[dict[str, object], ...]:
        return tuple(deepcopy(dict(row)) for row in self._rows)

    def apply_projection(
        self,
        result: CurrentProjectionApplyResult,
        *,
        business_key: tuple[str, ...],
    ) -> MutationCounts:
        del business_key
        self._rows = tuple(deepcopy(dict(row)) for row in result.rows)
        return result.mutations


class CurrentProjectionExecutionResult(FrozenModel):
    dataset_id: str = Field(min_length=1)
    lower_processed_version: int | None = Field(default=None, ge=0)
    upper_processed_version: int = Field(ge=0)
    affected_keys: int = Field(ge=0)
    mutations: MutationCounts
    checkpoint_version: int = Field(ge=0)
    no_work: bool = False


ProjectionReconciliation = Callable[[CurrentProjectionApplyResult], bool]


def _processed_version(
    state: CDCCheckpointState | None,
    *,
    table_reference: str,
) -> int | None:
    if state is None:
        return None
    partition = f"delta-cdf:{table_reference}"
    if len(state.checkpoint.positions) != 1:
        raise CurrentProjectionExecutionError(
            "current projection CDC checkpoint must contain exactly one history partition"
        )
    position = state.checkpoint.position_for(partition)
    if position is None or len(position) < 1:
        raise CurrentProjectionExecutionError(
            "current projection CDC checkpoint does not match authoritative history table"
        )
    return position[0]


def _affected_keys(
    records: Sequence[DeltaCDFRecord],
    *,
    business_key: tuple[str, ...],
    start_version: int,
    upper_version: int,
) -> tuple[tuple[object, ...], ...]:
    keys: set[tuple[object, ...]] = set()
    for record in records:
        if record.commit_version < start_version or record.commit_version > upper_version:
            continue
        key = tuple(record.data.get(column) for column in business_key)
        if any(value is None for value in key):
            raise CurrentProjectionExecutionError(
                f"history CDF row is missing business key columns: {business_key}"
            )
        keys.add(key)
    return tuple(sorted(keys, key=repr))


def execute_delta_current_projection(
    *,
    control_plane_engine: Engine,
    dataset_id: str,
    dataset_run_id: UUID,
    table_reference: str,
    business_key: tuple[str, ...],
    projected_columns: tuple[str, ...],
    history_cdf_records: Sequence[DeltaCDFRecord],
    history_rows_at_upper: Sequence[dict[str, object]],
    history_snapshot_version: int,
    earliest_available_version: int,
    latest_available_version: int,
    target: CurrentProjectionTarget,
    current_flag_column: str = "_framework_is_current",
    requested_upper_version: int | None = None,
    reconciliation_required: bool = True,
    reconcile: ProjectionReconciliation | None = None,
) -> CurrentProjectionExecutionResult:
    """Apply one bounded history-CDF range and atomically advance downstream progress.

    The caller must supply a time-travel/current-history snapshot exactly at the frozen
    upper Delta version. Reading history at a later version would expose state that is
    newer than the checkpoint being committed and is therefore rejected.
    """

    if not dataset_id or not table_reference:
        raise ValueError("dataset_id and table_reference are required")
    if not business_key:
        raise ValueError("current projection requires business_key")
    if reconciliation_required and reconcile is None:
        raise CurrentProjectionExecutionError(
            "required current projection reconciliation callback is missing"
        )

    checkpoint_state = read_cdc_checkpoint(control_plane_engine, dataset_id)
    lower_version = _processed_version(checkpoint_state, table_reference=table_reference)
    resume = plan_delta_cdf_resume(
        table_reference=table_reference,
        lower_committed_version=lower_version,
        earliest_available_version=earliest_available_version,
        latest_available_version=latest_available_version,
        requested_upper_version=requested_upper_version,
    )

    if not resume.has_work:
        return CurrentProjectionExecutionResult(
            dataset_id=dataset_id,
            lower_processed_version=lower_version,
            upper_processed_version=resume.upper_version,
            affected_keys=0,
            mutations=MutationCounts(),
            checkpoint_version=checkpoint_state.version if checkpoint_state is not None else 0,
            no_work=True,
        )

    if history_snapshot_version != resume.upper_version:
        raise CurrentProjectionExecutionError(
            "current projection must read authoritative history at the exact frozen upper "
            f"Delta version: snapshot={history_snapshot_version}, upper={resume.upper_version}"
        )

    affected = _affected_keys(
        history_cdf_records,
        business_key=business_key,
        start_version=resume.start_version,
        upper_version=resume.upper_version,
    )
    try:
        projection = apply_current_projection(
            target.read(),
            history_rows_at_upper,
            business_key=business_key,
            projected_columns=projected_columns,
            affected_keys=affected,
            current_flag_column=current_flag_column,
        )
    except CurrentProjectionError as exc:
        raise CurrentProjectionExecutionError(str(exc)) from exc

    observed_mutations = target.apply_projection(projection, business_key=business_key)
    if observed_mutations != projection.mutations:
        raise CurrentProjectionExecutionError(
            "current projection target mutation evidence does not match the planned mutation set"
        )

    reconciliation_passed = True
    if reconcile is not None:
        reconciliation_passed = bool(reconcile(projection))
    gate = StateCommitGate(
        target_committed=True,
        reconciliation_required=reconciliation_required,
        reconciliation_passed=reconciliation_passed,
    )
    if not gate.can_advance_state:
        raise CurrentProjectionExecutionError(
            "current projection reconciliation failed; checkpoint was not advanced"
        )

    next_state = commit_cdc_checkpoint(
        control_plane_engine,
        dataset_id=dataset_id,
        checkpoint=delta_cdf_checkpoint(table_reference, resume.upper_version),
        dataset_run_id=dataset_run_id,
        expected_version=checkpoint_state.version if checkpoint_state is not None else 0,
        gate=gate,
    )
    return CurrentProjectionExecutionResult(
        dataset_id=dataset_id,
        lower_processed_version=lower_version,
        upper_processed_version=resume.upper_version,
        affected_keys=len(affected),
        mutations=projection.mutations,
        checkpoint_version=next_state.version,
    )


__all__ = [
    "CurrentProjectionExecutionError",
    "CurrentProjectionExecutionResult",
    "CurrentProjectionTarget",
    "InMemoryCurrentProjectionTarget",
    "ProjectionReconciliation",
    "execute_delta_current_projection",
]
