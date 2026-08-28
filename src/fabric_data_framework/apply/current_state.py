"""Shared deterministic primitive for ordered current-state apply strategies.

SCD1 and generic UPSERT both need the same hard correctness decisions around
merge keys, source ordering, duplicate reruns, stale updates and equal-position
conflicts.  Keeping those decisions here prevents the strategies from drifting.
"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Mapping, Sequence

from pydantic import Field

from ..config import FrozenModel
from ..operations import MutationCounts


class CurrentStateConflictError(ValueError):
    """Raised when equal source positions contain conflicting payloads."""


class CurrentStateOrderingError(ValueError):
    """Raised when a safe current-state ordering decision cannot be made."""


class StaleRecordAction(str, Enum):
    IGNORE = "IGNORE"
    ERROR = "ERROR"


class CurrentStateApplyPolicy(FrozenModel):
    """Safety policy shared by current-state apply strategies."""

    allow_unordered_updates: bool = False
    stale_record_action: StaleRecordAction = StaleRecordAction.IGNORE


class CurrentStateApplyResult(FrozenModel):
    rows: tuple[dict[str, Any], ...]
    mutations: MutationCounts
    stale_ignored: int = Field(default=0, ge=0)
    duplicate_ignored: int = Field(default=0, ge=0)
    incoming_superseded: int = Field(default=0, ge=0)


def _key(row: Mapping[str, Any], columns: tuple[str, ...], *, strategy_name: str) -> tuple[Any, ...]:
    values = tuple(row.get(column) for column in columns)
    if any(value is None for value in values):
        raise ValueError(f"{strategy_name} merge key columns cannot be null: {columns}")
    return values


def _position(
    row: Mapping[str, Any],
    columns: tuple[str, ...],
    *,
    strategy_name: str,
) -> tuple[Any, ...] | None:
    if not columns:
        return None
    values = tuple(row.get(column) for column in columns)
    if any(value is None for value in values):
        raise CurrentStateOrderingError(
            f"{strategy_name} ordering columns cannot be null: {columns}"
        )
    return values


def _canonical_payload(row: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(dict(row).items(), key=lambda item: item[0]))


def _compare_positions(
    left: tuple[Any, ...],
    right: tuple[Any, ...],
    *,
    strategy_name: str,
) -> int:
    try:
        if left < right:
            return -1
        if left > right:
            return 1
        return 0
    except TypeError as exc:
        raise CurrentStateOrderingError(
            f"{strategy_name} ordering values are not mutually comparable"
        ) from exc


def _select_latest_incoming(
    incoming_rows: Sequence[Mapping[str, Any]],
    *,
    merge_key: tuple[str, ...],
    ordering_columns: tuple[str, ...],
    strategy_name: str,
) -> tuple[dict[tuple[Any, ...], dict[str, Any]], int, int]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    duplicate_ignored = 0
    incoming_superseded = 0

    for raw in incoming_rows:
        candidate = deepcopy(dict(raw))
        key = _key(candidate, merge_key, strategy_name=strategy_name)
        current = selected.get(key)
        if current is None:
            _position(candidate, ordering_columns, strategy_name=strategy_name)
            selected[key] = candidate
            continue

        candidate_payload = _canonical_payload(candidate)
        current_payload = _canonical_payload(current)

        if not ordering_columns:
            if candidate_payload != current_payload:
                raise CurrentStateOrderingError(
                    f"multiple unordered {strategy_name} incoming rows for key {key} "
                    "have different payloads"
                )
            duplicate_ignored += 1
            continue

        candidate_position = _position(
            candidate, ordering_columns, strategy_name=strategy_name
        )
        current_position = _position(
            current, ordering_columns, strategy_name=strategy_name
        )
        assert candidate_position is not None
        assert current_position is not None
        comparison = _compare_positions(
            candidate_position,
            current_position,
            strategy_name=strategy_name,
        )

        if comparison > 0:
            selected[key] = candidate
            incoming_superseded += 1
        elif comparison < 0:
            incoming_superseded += 1
        elif candidate_payload == current_payload:
            duplicate_ignored += 1
        else:
            raise CurrentStateConflictError(
                f"conflicting {strategy_name} incoming rows for key {key} at equal "
                f"position {candidate_position}"
            )

    return selected, duplicate_ignored, incoming_superseded


def apply_ordered_current_state(
    existing_rows: Sequence[Mapping[str, Any]],
    incoming_rows: Sequence[Mapping[str, Any]],
    *,
    merge_key: tuple[str, ...],
    ordering_columns: tuple[str, ...] = (),
    policy: CurrentStateApplyPolicy | None = None,
    strategy_name: str,
) -> CurrentStateApplyResult:
    """Apply generic insert-or-update current-state semantics safely.

    Incoming fields are merged over the current target row for an existing key.
    Target-only fields are retained.  The source ordering tuple normally contains
    event time, source version and/or sequence/LSN values.
    """

    if not merge_key:
        raise ValueError(f"merge_key is required for {strategy_name}")
    if len(set(merge_key)) != len(merge_key):
        raise ValueError(f"{strategy_name} merge_key columns must be unique")
    if len(set(ordering_columns)) != len(ordering_columns):
        raise ValueError(f"{strategy_name} ordering columns must be unique")

    effective_policy = policy or CurrentStateApplyPolicy()
    rows_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}

    for raw in existing_rows:
        row = deepcopy(dict(raw))
        key = _key(row, merge_key, strategy_name=strategy_name)
        if key in rows_by_key:
            raise ValueError(
                f"existing {strategy_name} target contains duplicate key {key}"
            )
        if ordering_columns:
            _position(row, ordering_columns, strategy_name=strategy_name)
        rows_by_key[key] = row

    selected, duplicate_ignored, incoming_superseded = _select_latest_incoming(
        incoming_rows,
        merge_key=merge_key,
        ordering_columns=ordering_columns,
        strategy_name=strategy_name,
    )

    inserted = 0
    updated = 0
    stale_ignored = 0

    for key in sorted(selected, key=repr):
        candidate = selected[key]
        current = rows_by_key.get(key)
        if current is None:
            rows_by_key[key] = candidate
            inserted += 1
            continue

        candidate_payload = _canonical_payload(candidate)
        current_payload = _canonical_payload(current)
        if candidate_payload == current_payload:
            duplicate_ignored += 1
            continue

        if not ordering_columns:
            if not effective_policy.allow_unordered_updates:
                raise CurrentStateOrderingError(
                    f"changed {strategy_name} update for key {key} has no ordering columns"
                )
            merged = deepcopy(current)
            merged.update(candidate)
            rows_by_key[key] = merged
            updated += 1
            continue

        candidate_position = _position(
            candidate, ordering_columns, strategy_name=strategy_name
        )
        current_position = _position(
            current, ordering_columns, strategy_name=strategy_name
        )
        assert candidate_position is not None
        assert current_position is not None
        comparison = _compare_positions(
            candidate_position,
            current_position,
            strategy_name=strategy_name,
        )

        if comparison < 0:
            if effective_policy.stale_record_action is StaleRecordAction.ERROR:
                raise CurrentStateOrderingError(
                    f"stale {strategy_name} row for key {key}: "
                    f"candidate={candidate_position}, current={current_position}"
                )
            stale_ignored += 1
            continue

        if comparison == 0:
            raise CurrentStateConflictError(
                f"conflicting {strategy_name} row for key {key} at equal position "
                f"{candidate_position}"
            )

        merged = deepcopy(current)
        merged.update(candidate)
        rows_by_key[key] = merged
        updated += 1

    ordered_rows = tuple(
        deepcopy(rows_by_key[key]) for key in sorted(rows_by_key, key=repr)
    )
    return CurrentStateApplyResult(
        rows=ordered_rows,
        mutations=MutationCounts(inserted=inserted, updated=updated, deleted=0),
        stale_ignored=stale_ignored,
        duplicate_ignored=duplicate_ignored,
        incoming_superseded=incoming_superseded,
    )
