"""CDC-to-SCD2 history apply with source-order and valid-time separation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping, Sequence
from uuid import UUID

from pydantic import Field

from ..capture.cdc import CDCNormalizedBatch, CDCOperation, CDCOrderingError
from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.audit import MutationCounts
from ..quality.temporal import (
    EventTimeRelation,
    SourceOrderRelation,
    TemporalOrderingError,
    compare_event_time,
    compare_source_order,
)
from fabric_data_framework.apply.scd2 import (
    IS_CURRENT,
    RECORD_HASH,
    SOURCE_DATASET_RUN_ID,
    VALID_FROM,
    VALID_TO,
    assert_one_current_row,
)
from .cdc import (
    CDC_PARTITION,
    CDC_POSITION,
    _assert_event_newer_than_target,
    _event_key,
)
from .record_hash import hash_tracked_attributes


CDC_CLOSED_PARTITION = "_framework_cdc_closed_partition"
CDC_CLOSED_POSITION = "_framework_cdc_closed_position"


class CDCSCD2Error(ValueError):
    pass


class CDCSCD2LateArrivingError(CDCSCD2Error):
    """A newer source event has valid-time earlier than the current/history boundary."""


class CDCSCD2ConflictError(CDCSCD2Error):
    pass


class CDCSCD2ApplyResult(FrozenModel):
    rows: tuple[dict[str, Any], ...]
    mutations: MutationCounts
    events_applied: int = Field(default=0, ge=0)
    stale_events_ignored: int = Field(default=0, ge=0)
    no_change_events: int = Field(default=0, ge=0)
    missing_delete_events_ignored: int = Field(default=0, ge=0)


def _hash_attributes(row: Mapping[str, Any], tracked_columns: tuple[str, ...]) -> str:
    return hash_tracked_attributes(row, tracked_columns)


def _business_key(row: Mapping[str, Any], columns: tuple[str, ...]) -> tuple[Any, ...]:
    values = tuple(row.get(column) for column in columns)
    if any(value is None for value in values):
        raise CDCSCD2Error(f"SCD2 business key columns cannot be null: {columns}")
    return values


def _event_time(event_id: str, value: datetime | None) -> datetime:
    if value is None:
        raise CDCSCD2Error(f"CDC event {event_id} requires event_time for SCD2 apply")
    return value


def _current_index(
    rows: Sequence[Mapping[str, Any]],
    *,
    key: tuple[Any, ...],
    business_key: tuple[str, ...],
) -> int | None:
    return next(
        (
            index
            for index, row in enumerate(rows)
            if row.get(IS_CURRENT) is True and _business_key(row, business_key) == key
        ),
        None,
    )


def _close_current(
    current: dict[str, Any],
    *,
    effective_at: datetime,
    event_partition: str,
    event_position: tuple[int, ...],
) -> None:
    current_from = current.get(VALID_FROM)
    if not isinstance(current_from, datetime):
        raise CDCSCD2Error("existing SCD2 current row missing datetime valid_from")
    try:
        relation = compare_event_time(effective_at, current_from)
    except TemporalOrderingError as exc:
        raise CDCSCD2Error("SCD2 valid-time values cannot be compared safely") from exc
    if relation is EventTimeRelation.EARLIER:
        raise CDCSCD2LateArrivingError(
            "CDC source order is newer but event valid-time predates the current SCD2 version; "
            "retroactive history correction is not yet certified"
        )
    current[VALID_TO] = effective_at
    current[IS_CURRENT] = False
    current[CDC_CLOSED_PARTITION] = event_partition
    current[CDC_CLOSED_POSITION] = event_position


def _history_for_key(
    rows: Sequence[Mapping[str, Any]],
    *,
    key: tuple[Any, ...],
    business_key: tuple[str, ...],
) -> list[Mapping[str, Any]]:
    return [row for row in rows if _business_key(row, business_key) == key]


def _latest_closed_row(
    history: Sequence[Mapping[str, Any]],
    *,
    key: tuple[Any, ...],
) -> Mapping[str, Any] | None:
    latest: Mapping[str, Any] | None = None
    latest_partition: str | None = None
    latest_position: tuple[int, ...] | None = None

    for row in history:
        partition = row.get(CDC_CLOSED_PARTITION)
        position = row.get(CDC_CLOSED_POSITION)
        if partition is None and position is None:
            continue
        if not isinstance(partition, str) or not partition:
            raise CDCOrderingError(
                f"CDC SCD2 history for {key} has incomplete closed-partition evidence"
            )
        if not isinstance(position, (tuple, list)) or not position or not all(
            type(value) is int for value in position
        ):
            raise CDCOrderingError(
                f"CDC SCD2 history for {key} has invalid closed-position evidence"
            )
        candidate_position = tuple(position)
        if latest is None:
            latest = row
            latest_partition = partition
            latest_position = candidate_position
            continue
        if partition != latest_partition:
            raise CDCOrderingError(
                f"CDC SCD2 history for {key} spans multiple source partitions; "
                "deterministic resurrection order cannot be proven"
            )
        assert latest_position is not None
        try:
            relation = compare_source_order(candidate_position, latest_position)
        except TemporalOrderingError as exc:
            raise CDCOrderingError(
                f"CDC SCD2 history for {key} contains non-comparable closed positions"
            ) from exc
        if relation is SourceOrderRelation.NEWER:
            latest = row
            latest_position = candidate_position
    return latest


def _ordering_when_current_absent(
    *,
    rows: Sequence[Mapping[str, Any]],
    key: tuple[Any, ...],
    business_key: tuple[str, ...],
    event_partition: str,
    event_position: tuple[int, ...],
    batch: CDCNormalizedBatch,
) -> tuple[int | None, Mapping[str, Any] | None]:
    history = _history_for_key(rows, key=key, business_key=business_key)
    if not history:
        return None, None
    closed = _latest_closed_row(history, key=key)
    if closed is None:
        synthetic: Mapping[str, Any] = {}
    else:
        synthetic = {
            CDC_PARTITION: closed[CDC_CLOSED_PARTITION],
            CDC_POSITION: closed[CDC_CLOSED_POSITION],
        }
    ordering = _assert_event_newer_than_target(
        current=synthetic,
        event_partition=event_partition,
        event_position=event_position,
        batch=batch,
        key=key,
    )
    return ordering, closed


def _assert_reinsert_valid_time(
    *,
    key: tuple[Any, ...],
    effective_at: datetime,
    closed: Mapping[str, Any] | None,
) -> None:
    if closed is None:
        return
    closed_at = closed.get(VALID_TO)
    if not isinstance(closed_at, datetime):
        raise CDCOrderingError(
            f"CDC SCD2 closed history for {key} lacks a datetime valid_to boundary"
        )
    try:
        relation = compare_event_time(effective_at, closed_at)
    except TemporalOrderingError as exc:
        raise CDCOrderingError(
            f"CDC SCD2 reinsert valid-time for {key} cannot be compared safely"
        ) from exc
    if relation is EventTimeRelation.EARLIER:
        raise CDCSCD2LateArrivingError(
            "CDC source position is newer but reinsert valid-time predates the delete/history "
            "boundary; retroactive history correction is not yet certified"
        )


def apply_cdc_scd2(
    existing_rows: Sequence[Mapping[str, Any]],
    batch: CDCNormalizedBatch,
    *,
    business_key: tuple[str, ...],
    tracked_columns: tuple[str, ...],
    dataset_run_id: UUID,
) -> CDCSCD2ApplyResult:
    """Apply normalized CDC to SCD2 history without conflating two clocks.

    Canonical CDC source position determines event order. ``event_time`` determines
    validity intervals. Closed rows retain delete/tombstone source-position evidence so
    stale or equal events cannot resurrect a deleted business key.
    """

    if not business_key or len(set(business_key)) != len(business_key):
        raise ValueError("CDC SCD2 apply requires unique business_key columns")
    if not tracked_columns or len(set(tracked_columns)) != len(tracked_columns):
        raise ValueError("CDC SCD2 apply requires unique tracked_columns")

    rows = [deepcopy(dict(row)) for row in existing_rows]
    assert_one_current_row(rows, business_key)

    inserted = 0
    updated = 0
    deleted = 0
    events_applied = 0
    stale_events_ignored = 0
    no_change_events = 0
    missing_delete_events_ignored = 0

    for event in batch.events:
        key = _event_key(event.key, business_key, strategy_name="SCD2")
        effective_at = _event_time(event.event_id, event.event_time)
        index = _current_index(rows, key=key, business_key=business_key)
        current = rows[index] if index is not None else None
        ordering: int | None = None
        closed_history: Mapping[str, Any] | None = None
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
        else:
            ordering, closed_history = _ordering_when_current_absent(
                rows=rows,
                key=key,
                business_key=business_key,
                event_partition=event.position.partition,
                event_position=event.position.values,
                batch=batch,
            )
            if ordering is not None and ordering <= 0:
                stale_events_ignored += 1
                continue

        if event.operation is CDCOperation.DELETE:
            if current is None:
                missing_delete_events_ignored += 1
                continue
            if ordering == 0:
                raise CDCSCD2ConflictError(
                    f"CDC DELETE conflicts with current SCD2 version {key} at equal source position"
                )
            _close_current(
                current,
                effective_at=effective_at,
                event_partition=event.position.partition,
                event_position=event.position.values,
            )
            deleted += 1
            events_applied += 1
            continue

        assert event.after is not None
        incoming = deepcopy(event.after)
        for column, value in zip(business_key, key, strict=True):
            incoming[column] = value
        new_hash = _hash_attributes(incoming, tracked_columns)

        if current is None:
            _assert_reinsert_valid_time(
                key=key,
                effective_at=effective_at,
                closed=closed_history,
            )
            new_row = incoming
            new_row.update(
                {
                    VALID_FROM: effective_at,
                    VALID_TO: None,
                    IS_CURRENT: True,
                    RECORD_HASH: new_hash,
                    SOURCE_DATASET_RUN_ID: str(dataset_run_id),
                    CDC_PARTITION: event.position.partition,
                    CDC_POSITION: event.position.values,
                }
            )
            rows.append(new_row)
            inserted += 1
            events_applied += 1
            continue

        current_hash = current.get(RECORD_HASH)
        if current_hash is None:
            current_hash = _hash_attributes(current, tracked_columns)

        if ordering == 0:
            if current_hash == new_hash:
                no_change_events += 1
                continue
            raise CDCSCD2ConflictError(
                f"CDC {event.operation.value} conflicts with current SCD2 version {key} "
                "at equal source position"
            )

        if current_hash == new_hash:
            current[CDC_PARTITION] = event.position.partition
            current[CDC_POSITION] = event.position.values
            no_change_events += 1
            continue

        _close_current(
            current,
            effective_at=effective_at,
            event_partition=event.position.partition,
            event_position=event.position.values,
        )
        new_row = incoming
        new_row.update(
            {
                VALID_FROM: effective_at,
                VALID_TO: None,
                IS_CURRENT: True,
                RECORD_HASH: new_hash,
                SOURCE_DATASET_RUN_ID: str(dataset_run_id),
                CDC_PARTITION: event.position.partition,
                CDC_POSITION: event.position.values,
            }
        )
        rows.append(new_row)
        updated += 1
        events_applied += 1

    assert_one_current_row(rows, business_key)
    rows.sort(
        key=lambda row: (
            repr(_business_key(row, business_key)),
            row.get(VALID_FROM) or datetime.min,
            repr(row.get(CDC_POSITION)),
        )
    )
    return CDCSCD2ApplyResult(
        rows=tuple(rows),
        mutations=MutationCounts(inserted=inserted, updated=updated, deleted=deleted),
        events_applied=events_applied,
        stale_events_ignored=stale_events_ignored,
        no_change_events=no_change_events,
        missing_delete_events_ignored=missing_delete_events_ignored,
    )


__all__ = [
    "CDC_CLOSED_PARTITION",
    "CDC_CLOSED_POSITION",
    "CDCSCD2ApplyResult",
    "CDCSCD2ConflictError",
    "CDCSCD2Error",
    "CDCSCD2LateArrivingError",
    "apply_cdc_scd2",
]
