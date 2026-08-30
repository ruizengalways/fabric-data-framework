"""CDC-to-current-state apply semantics for UPSERT and SCD1 targets."""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Mapping, Sequence

from pydantic import Field

from ..capture.cdc import CDCNormalizedBatch, CDCOperation, CDCOrderingError
from fabric_data_framework.config import ApplyStrategy
from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.audit import MutationCounts
from ..quality.temporal import (
    SourceOrderRelation,
    TemporalOrderingError,
    compare_source_order,
)


CDC_PARTITION = "_framework_cdc_partition"
CDC_POSITION = "_framework_cdc_position"


class CDCApplyError(ValueError):
    """Base error for CDC semantic apply."""


class CDCDeleteAction(str, Enum):
    APPLY = "APPLY"
    IGNORE = "IGNORE"
    ERROR = "ERROR"


class CDCDeleteRejectedError(CDCApplyError):
    pass


class CDCCurrentStateApplyResult(FrozenModel):
    rows: tuple[dict[str, Any], ...]
    mutations: MutationCounts
    events_applied: int = Field(default=0, ge=0)
    stale_events_ignored: int = Field(default=0, ge=0)
    no_change_events: int = Field(default=0, ge=0)
    missing_delete_events_ignored: int = Field(default=0, ge=0)
    delete_policy_events_ignored: int = Field(default=0, ge=0)


def _row_key(
    row: Mapping[str, Any],
    merge_key: tuple[str, ...],
    *,
    strategy_name: str,
) -> tuple[Any, ...]:
    values = tuple(row.get(column) for column in merge_key)
    if any(value is None for value in values):
        raise CDCApplyError(
            f"{strategy_name} CDC target merge key columns cannot be null: {merge_key}"
        )
    return values


def _event_key(
    event_key: Mapping[str, Any],
    merge_key: tuple[str, ...],
    *,
    strategy_name: str,
) -> tuple[Any, ...]:
    missing = [column for column in merge_key if column not in event_key]
    if missing:
        raise CDCApplyError(
            f"{strategy_name} CDC event key is missing merge key columns: {missing}"
        )
    values = tuple(event_key[column] for column in merge_key)
    if any(value is None for value in values):
        raise CDCApplyError(f"{strategy_name} CDC event merge key cannot contain null values")
    return values


def _payload_without_cdc_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in row.items()
        if key not in {CDC_PARTITION, CDC_POSITION}
    }


def _assert_event_newer_than_target(
    *,
    current: Mapping[str, Any],
    event_partition: str,
    event_position: tuple[int, ...],
    batch: CDCNormalizedBatch,
    key: tuple[Any, ...],
) -> int:
    """Return -1 stale, 0 equal or 1 newer relative to current target state."""

    current_partition = current.get(CDC_PARTITION)
    current_position = current.get(CDC_POSITION)
    if current_partition is None and current_position is None:
        lower = batch.lower_checkpoint
        lower_position = lower.position_for(event_partition) if lower is not None else None
        if lower_position is None:
            raise CDCOrderingError(
                f"CDC target row {key} has no source-position metadata and the batch has "
                "no committed lower checkpoint proving the event is newer"
            )
        try:
            relation = compare_source_order(event_position, lower_position)
        except TemporalOrderingError as exc:
            raise CDCOrderingError(
                f"CDC event for target row {key} cannot be compared with committed lower checkpoint"
            ) from exc
        if relation is not SourceOrderRelation.NEWER:
            raise CDCOrderingError(
                f"CDC event for target row {key} is not above the committed lower checkpoint"
            )
        return 1
    if current_partition is None or current_position is None:
        raise CDCOrderingError(
            f"CDC target row {key} has incomplete framework source-position metadata"
        )
    if current_partition != event_partition:
        raise CDCOrderingError(
            f"CDC target row {key} moved across source partitions; deterministic order "
            "cannot be proven"
        )
    if not isinstance(current_position, (tuple, list)) or not all(
        isinstance(value, int) for value in current_position
    ):
        raise CDCOrderingError(f"CDC target row {key} has invalid source-position metadata")
    target_position = tuple(current_position)
    try:
        relation = compare_source_order(event_position, target_position)
    except TemporalOrderingError as exc:
        raise CDCOrderingError(
            f"CDC target row {key} has non-comparable source-position metadata"
        ) from exc
    if relation is SourceOrderRelation.STALE:
        return -1
    if relation is SourceOrderRelation.NEWER:
        return 1
    return 0


def apply_cdc_current_state(
    existing_rows: Sequence[Mapping[str, Any]],
    batch: CDCNormalizedBatch,
    *,
    merge_key: tuple[str, ...],
    strategy: ApplyStrategy,
    delete_action: CDCDeleteAction = CDCDeleteAction.APPLY,
) -> CDCCurrentStateApplyResult:
    """Apply normalized CDC sequentially to a current-state target.

    UPSERT and SCD1 intentionally share this CDC correctness path. The committed
    lower checkpoint is sufficient to safely move a bootstrap/current row that does
    not yet carry row-level CDC position metadata. Once touched by CDC, rows retain
    canonical source position metadata for stale/conflict detection.
    """

    if strategy not in {ApplyStrategy.UPSERT, ApplyStrategy.SCD1}:
        raise ValueError("CDC current-state apply supports only UPSERT or SCD1")
    if not merge_key or len(set(merge_key)) != len(merge_key):
        raise ValueError("CDC current-state apply requires unique merge_key columns")

    strategy_name = strategy.value
    rows_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for raw in existing_rows:
        row = deepcopy(dict(raw))
        key = _row_key(row, merge_key, strategy_name=strategy_name)
        if key in rows_by_key:
            raise CDCApplyError(f"existing {strategy_name} target contains duplicate key {key}")
        rows_by_key[key] = row

    inserted = 0
    updated = 0
    deleted = 0
    events_applied = 0
    stale_events_ignored = 0
    no_change_events = 0
    missing_delete_events_ignored = 0
    delete_policy_events_ignored = 0

    for event in batch.events:
        key = _event_key(event.key, merge_key, strategy_name=strategy_name)
        current = rows_by_key.get(key)
        ordering = None
        if current is not None:
            ordering = _assert_event_newer_than_target(
                current=current,
                event_partition=event.position.partition,
                event_position=event.position.values,
                batch=batch,
                key=key,
            )
            if ordering < 0:
                stale_events_ignored += 1
                continue

        if event.operation is CDCOperation.DELETE:
            if delete_action is CDCDeleteAction.IGNORE:
                delete_policy_events_ignored += 1
                continue
            if delete_action is CDCDeleteAction.ERROR:
                raise CDCDeleteRejectedError(
                    f"CDC DELETE rejected by policy for {strategy_name} key {key}"
                )
            if current is None:
                missing_delete_events_ignored += 1
                continue
            if ordering == 0:
                raise CDCOrderingError(
                    f"CDC DELETE conflicts with existing {strategy_name} row {key} at "
                    f"equal source position {event.position.values}"
                )
            del rows_by_key[key]
            deleted += 1
            events_applied += 1
            continue

        assert event.after is not None
        candidate = deepcopy(current) if current is not None else {}
        candidate.update(deepcopy(event.after))
        for column, value in zip(merge_key, key, strict=True):
            candidate[column] = value
        candidate[CDC_PARTITION] = event.position.partition
        candidate[CDC_POSITION] = event.position.values

        if current is None:
            rows_by_key[key] = candidate
            inserted += 1
            events_applied += 1
            continue

        if ordering == 0:
            if candidate == current:
                no_change_events += 1
                continue
            raise CDCOrderingError(
                f"CDC {event.operation.value} conflicts with existing {strategy_name} row "
                f"{key} at equal source position {event.position.values}"
            )

        if _payload_without_cdc_metadata(candidate) == _payload_without_cdc_metadata(current):
            rows_by_key[key] = candidate
            no_change_events += 1
            continue

        rows_by_key[key] = candidate
        updated += 1
        events_applied += 1

    ordered_rows = tuple(
        deepcopy(rows_by_key[key]) for key in sorted(rows_by_key, key=repr)
    )
    return CDCCurrentStateApplyResult(
        rows=ordered_rows,
        mutations=MutationCounts(inserted=inserted, updated=updated, deleted=deleted),
        events_applied=events_applied,
        stale_events_ignored=stale_events_ignored,
        no_change_events=no_change_events,
        missing_delete_events_ignored=missing_delete_events_ignored,
        delete_policy_events_ignored=delete_policy_events_ignored,
    )


__all__ = [
    "CDCApplyError",
    "CDCCurrentStateApplyResult",
    "CDCDeleteAction",
    "CDCDeleteRejectedError",
    "CDC_PARTITION",
    "CDC_POSITION",
    "apply_cdc_current_state",
]
