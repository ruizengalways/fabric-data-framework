"""Incremental history -> current projection execution with independent CDC progress.

The projection checkpoint is downstream progress over the authoritative history Delta
table. Target mutation is committed before checkpoint advance. If checkpoint commit
fails after target mutation, a retry replays the same history range and is idempotent.
No distributed transaction across the two Delta tables is assumed.
"""

from __future__ import annotations

from builtins import BaseExceptionGroup
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator, Mapping, Protocol, Sequence, runtime_checkable
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import Engine

from fabric_data_framework.adapters.cdc.delta_cdf import (
    DeltaCDFRecord,
    plan_delta_cdf_resume,
)
from fabric_data_framework.apply.current_projection import (
    CurrentProjectionApplyResult,
    CurrentProjectionError,
    apply_current_projection,
)
from fabric_data_framework.contracts.audit import MutationCounts
from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.current_projection import (
    current_projection_checkpoint_partition,
)
from fabric_data_framework.contracts.runtime import StateCommitGate
from fabric_data_framework.capture.cdc import build_cdc_checkpoint
from fabric_data_framework.control_plane.io import (
    CDCCheckpointState,
    commit_cdc_checkpoint,
    read_cdc_checkpoint,
)
from fabric_data_framework.control_plane.dataset_lease import (
    DatasetLeaseConflict,
    DatasetLeaseState,
    acquire_dataset_lease,
    release_dataset_lease,
)


class CurrentProjectionExecutionError(RuntimeError):
    pass


@runtime_checkable
class CurrentProjectionTarget(Protocol):
    """Physical current-target boundary used by the incremental projection executor."""

    def read_projection_rows(
        self,
        *,
        business_key: tuple[str, ...],
        affected_keys: tuple[tuple[object, ...], ...] | None,
    ) -> tuple[dict[str, object], ...]: ...

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

    def read_projection_rows(
        self,
        *,
        business_key: tuple[str, ...],
        affected_keys: tuple[tuple[object, ...], ...] | None,
    ) -> tuple[dict[str, object], ...]:
        if affected_keys is None:
            return self.read()
        selected = set(affected_keys)
        return tuple(
            deepcopy(dict(row))
            for row in self._rows
            if tuple(row.get(column) for column in business_key) in selected
        )

    def apply_projection(
        self,
        result: CurrentProjectionApplyResult,
        *,
        business_key: tuple[str, ...],
    ) -> MutationCounts:
        by_key: dict[tuple[object, ...], dict[str, object]] = {}
        for raw in self._rows:
            row = deepcopy(dict(raw))
            key = tuple(row.get(column) for column in business_key)
            if any(value is None for value in key) or key in by_key:
                raise CurrentProjectionExecutionError(
                    "current projection target contains an invalid/duplicate business key"
                )
            by_key[key] = row
        for raw_key in result.delete_keys:
            key = tuple(raw_key.get(column) for column in business_key)
            by_key.pop(key, None)
        for raw in result.upserts:
            row = deepcopy(dict(raw))
            key = tuple(row.get(column) for column in business_key)
            by_key[key] = row
        self._rows = tuple(deepcopy(by_key[key]) for key in sorted(by_key, key=repr))
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


@contextmanager
def _exclusive_projection_mutation(
    *,
    engine: Engine,
    dataset_id: str,
    dataset_run_id: UUID,
) -> Iterator[DatasetLeaseState]:
    owner = f"current-projection:{uuid4()}"
    try:
        lease = acquire_dataset_lease(
            engine,
            dataset_id=dataset_id,
            lease_owner=owner,
            dataset_run_id=dataset_run_id,
            review_deadline=datetime.now(timezone.utc) + timedelta(days=1),
        )
    except DatasetLeaseConflict as exc:
        raise CurrentProjectionExecutionError(
            "current projection mutation is already in progress for this dataset"
        ) from exc

    try:
        yield lease
    except BaseException as execution_error:
        try:
            release_dataset_lease(engine, lease)
        except BaseException as release_error:
            raise BaseExceptionGroup(
                "current projection execution and dataset-lease release both failed",
                (execution_error, release_error),
            ) from execution_error
        raise
    else:
        try:
            release_dataset_lease(engine, lease)
        except Exception as exc:
            raise CurrentProjectionExecutionError(
                "current projection succeeded but its dataset lease could not be released"
            ) from exc


def _processed_version(
    state: CDCCheckpointState | None,
    *,
    table_reference: str,
    business_key: tuple[str, ...],
    projected_columns: tuple[str, ...],
    current_flag_column: str,
) -> int | None:
    if state is None:
        return None
    partition = current_projection_checkpoint_partition(
        table_reference=table_reference,
        business_key=business_key,
        projected_columns=projected_columns,
        current_flag_column=current_flag_column,
    )
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
        if record.commit_version > upper_version:
            raise CurrentProjectionExecutionError(
                "history CDF contains a record newer than the frozen upper version"
            )
        if record.commit_version < start_version:
            continue
        key = tuple(record.data.get(column) for column in business_key)
        if any(value is None for value in key):
            raise CurrentProjectionExecutionError(
                f"history CDF row is missing business key columns: {business_key}"
            )
        keys.add(key)
    return tuple(sorted(keys, key=repr))


def _assert_history_scope(
    history_rows: Sequence[Mapping[str, object]],
    *,
    business_key: tuple[str, ...],
    affected_keys: tuple[tuple[object, ...], ...],
) -> None:
    selected = set(affected_keys)
    for row in history_rows:
        key = tuple(row.get(column) for column in business_key)
        if any(value is None for value in key):
            raise CurrentProjectionExecutionError(
                f"authoritative history row is missing business key columns: {business_key}"
            )
        if key not in selected:
            raise CurrentProjectionExecutionError(
                "incremental authoritative history rows must be scoped to affected keys"
            )


def _apply_and_commit(
    *,
    control_plane_engine: Engine,
    dataset_id: str,
    dataset_run_id: UUID,
    table_reference: str,
    business_key: tuple[str, ...],
    projected_columns: tuple[str, ...],
    history_rows: Sequence[dict[str, object]],
    affected_keys: tuple[tuple[object, ...], ...] | None,
    upper_version: int,
    checkpoint_state: CDCCheckpointState | None,
    target: CurrentProjectionTarget,
    current_flag_column: str,
    reconciliation_required: bool,
    reconcile: ProjectionReconciliation | None,
) -> tuple[CurrentProjectionApplyResult, CDCCheckpointState]:
    try:
        projection = apply_current_projection(
            target.read_projection_rows(
                business_key=business_key,
                affected_keys=affected_keys,
            ),
            history_rows,
            business_key=business_key,
            projected_columns=projected_columns,
            affected_keys=affected_keys,
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
        checkpoint=build_cdc_checkpoint(
            {
                current_projection_checkpoint_partition(
                    table_reference=table_reference,
                    business_key=business_key,
                    projected_columns=projected_columns,
                    current_flag_column=current_flag_column,
                ): (upper_version,)
            }
        ),
        dataset_run_id=dataset_run_id,
        expected_version=checkpoint_state.version if checkpoint_state is not None else 0,
        gate=gate,
    )
    return projection, next_state


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
    history_cdf_complete_through_upper: bool,
    history_snapshot_complete_for_affected_keys: bool,
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

    with _exclusive_projection_mutation(
        engine=control_plane_engine,
        dataset_id=dataset_id,
        dataset_run_id=dataset_run_id,
    ):
        checkpoint_state = read_cdc_checkpoint(control_plane_engine, dataset_id)
        if checkpoint_state is None:
            raise CurrentProjectionExecutionError(
                "current projection is uninitialized; run an explicit full projection rebuild "
                "before incremental CDF execution"
            )
        lower_version = _processed_version(
            checkpoint_state,
            table_reference=table_reference,
            business_key=business_key,
            projected_columns=projected_columns,
            current_flag_column=current_flag_column,
        )
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
                checkpoint_version=checkpoint_state.version,
                no_work=True,
            )

        if history_cdf_complete_through_upper is not True:
            raise CurrentProjectionExecutionError(
                "current projection CDF evidence is not complete through the frozen upper version"
            )
        if history_snapshot_complete_for_affected_keys is not True:
            raise CurrentProjectionExecutionError(
                "authoritative history snapshot is not complete for every affected key"
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
        _assert_history_scope(
            history_rows_at_upper,
            business_key=business_key,
            affected_keys=affected,
        )
        projection, next_state = _apply_and_commit(
            control_plane_engine=control_plane_engine,
            dataset_id=dataset_id,
            dataset_run_id=dataset_run_id,
            table_reference=table_reference,
            business_key=business_key,
            projected_columns=projected_columns,
            history_rows=history_rows_at_upper,
            affected_keys=affected,
            upper_version=resume.upper_version,
            checkpoint_state=checkpoint_state,
            target=target,
            current_flag_column=current_flag_column,
            reconciliation_required=reconciliation_required,
            reconcile=reconcile,
        )
        return CurrentProjectionExecutionResult(
            dataset_id=dataset_id,
            lower_processed_version=lower_version,
            upper_processed_version=resume.upper_version,
            affected_keys=len(affected),
            mutations=projection.mutations,
            checkpoint_version=next_state.version,
        )


def rebuild_delta_current_projection(
    *,
    control_plane_engine: Engine,
    dataset_id: str,
    dataset_run_id: UUID,
    table_reference: str,
    business_key: tuple[str, ...],
    projected_columns: tuple[str, ...],
    history_rows_at_upper: Sequence[dict[str, object]],
    history_snapshot_version: int,
    history_snapshot_complete: bool,
    target: CurrentProjectionTarget,
    current_flag_column: str = "_framework_is_current",
    reconciliation_required: bool = True,
    reconcile: ProjectionReconciliation | None = None,
) -> CurrentProjectionExecutionResult:
    """Explicitly rebuild all current state and establish the Mode-3 checkpoint.

    This is the required bootstrap and retention-gap recovery path.  The caller must
    supply the complete authoritative history snapshot at the frozen version.  Existing
    checkpoint progress may advance, but it is never silently rewound or rebound to a
    different history table.
    """

    if not dataset_id or not table_reference:
        raise ValueError("dataset_id and table_reference are required")
    if not business_key:
        raise ValueError("current projection requires business_key")
    if history_snapshot_version < 0:
        raise ValueError("history_snapshot_version must be non-negative")
    if history_snapshot_complete is not True:
        raise CurrentProjectionExecutionError(
            "full current projection rebuild requires a complete authoritative history snapshot"
        )
    if reconciliation_required and reconcile is None:
        raise CurrentProjectionExecutionError(
            "required current projection reconciliation callback is missing"
        )

    with _exclusive_projection_mutation(
        engine=control_plane_engine,
        dataset_id=dataset_id,
        dataset_run_id=dataset_run_id,
    ):
        checkpoint_state = read_cdc_checkpoint(control_plane_engine, dataset_id)
        lower_version = _processed_version(
            checkpoint_state,
            table_reference=table_reference,
            business_key=business_key,
            projected_columns=projected_columns,
            current_flag_column=current_flag_column,
        )
        if lower_version is not None and history_snapshot_version < lower_version:
            raise CurrentProjectionExecutionError(
                "full current projection rebuild cannot rewind the committed history version"
            )
        projection, next_state = _apply_and_commit(
            control_plane_engine=control_plane_engine,
            dataset_id=dataset_id,
            dataset_run_id=dataset_run_id,
            table_reference=table_reference,
            business_key=business_key,
            projected_columns=projected_columns,
            history_rows=history_rows_at_upper,
            affected_keys=None,
            upper_version=history_snapshot_version,
            checkpoint_state=checkpoint_state,
            target=target,
            current_flag_column=current_flag_column,
            reconciliation_required=reconciliation_required,
            reconcile=reconcile,
        )
        return CurrentProjectionExecutionResult(
            dataset_id=dataset_id,
            lower_processed_version=lower_version,
            upper_processed_version=history_snapshot_version,
            affected_keys=projection.affected_keys,
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
    "rebuild_delta_current_projection",
]
