"""CDC-to-SCD2 history apply with source-order and valid-time separation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping, Sequence
from uuid import UUID

from pydantic import Field

from ..capture.cdc import CDCNormalizedBatch, CDCOperation, CDCOrderingError
from ..config import FrozenModel
from ..operations import MutationCounts
from ..scd2 import (
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


CDC_CLOSED_PARTITION = "_framework_cdc_closed_partition"
CDC_CLOSED_POSITION = "_framework_cdc_closed_position"


class CDCSCD2Error(ValueError):
    pass


class CDCSCD2LateArrivingError(CDCSCD2Error):
    """A newer source event has valid-time earlier than the current version."""


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
    payload = {column: row.get(column) for column in tracked_columns}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


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
    if effective_at < current_from:
        raise CDCSCD2LateArrivingError(
            "CDC source order is newer but event valid-time predates the current SCD2 version; "
            "retroactive history correction is not yet certified"
        )
    current[VALID_TO] = effective_at
    current[IS_CURRENT] = False
    current[CDC_CLOSED_PARTITION] = event_partition
    current[CDC_CLOSED_POSITION] = event_position


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
    validity intervals. Equal event_time values are therefore legal when source
    positions are distinct; the earlier version becomes a zero-duration history row.
    Truly retroactive valid-time correction remains fail-closed until an explicit
    history-rewrite policy is implemented.
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
