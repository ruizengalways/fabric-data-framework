"""Deterministic current-state SCD1 apply semantics.

The implementation is provider-neutral and intentionally fail-closed when an
incremental current-state update cannot be ordered safely. Native Fabric movement
may land the candidate rows; this module remains the canonical framework fallback
for SCD1 apply semantics.
"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Mapping, Sequence

from pydantic import Field

from ..config import FrozenModel
from ..operations import MutationCounts


class SCD1ConflictError(ValueError):
    """Raised when equal source positions contain conflicting payloads."""


class SCD1OrderingError(ValueError):
    """Raised when a safe current-state ordering decision cannot be made."""


class StaleRecordAction(str, Enum):
    IGNORE = "IGNORE"
    ERROR = "ERROR"


class SCD1ApplyPolicy(FrozenModel):
    """Safety policy for current-state overwrite semantics."""

    allow_unordered_updates: bool = False
    stale_record_action: StaleRecordAction = StaleRecordAction.IGNORE


class SCD1ApplyResult(FrozenModel):
    rows: tuple[dict[str, Any], ...]
    mutations: MutationCounts
    stale_ignored: int = Field(default=0, ge=0)
    incoming_superseded: int = Field(default=0, ge=0)
    duplicate_ignored: int = Field(default=0, ge=0)


def _key(row: Mapping[str, Any], columns: tuple[str, ...]) -> tuple[Any, ...]:
    values = tuple(row.get(column) for column in columns)
    if any(value is None for value in values):
        raise ValueError(f"SCD1 merge key columns cannot be null: {columns}")
    return values


def _position(
    row: Mapping[str, Any],
    columns: tuple[str, ...],
) -> tuple[Any, ...] | None:
    if not columns:
        return None
    values = tuple(row.get(column) for column in columns)
    if any(value is None for value in values):
        raise SCD1OrderingError(
            f"SCD1 ordering columns cannot be null: {columns}"
        )
    return values


def _canonical_payload(row: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(dict(row).items(), key=lambda item: item[0]))


def _compare_positions(left: tuple[Any, ...], right: tuple[Any, ...]) -> int:
    try:
        if left < right:
            return -1
        if left > right:
            return 1
        return 0
    except TypeError as exc:
        raise SCD1OrderingError(
            "SCD1 ordering values are not mutually comparable"
        ) from exc


def _select_latest_incoming(
    incoming_rows: Sequence[Mapping[str, Any]],
    *,
    merge_key: tuple[str, ...],
    ordering_columns: tuple[str, ...],
) -> tuple[dict[tuple[Any, ...], dict[str, Any]], int, int]:
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    incoming_superseded = 0
    duplicate_ignored = 0

    for raw in incoming_rows:
        candidate = deepcopy(dict(raw))
        key = _key(candidate, merge_key)
        current = selected.get(key)
        if current is None:
            _position(candidate, ordering_columns)
            selected[key] = candidate
            continue

        candidate_payload = _canonical_payload(candidate)
        current_payload = _canonical_payload(current)

        if not ordering_columns:
            if candidate_payload != current_payload:
                raise SCD1OrderingError(
                    f"multiple unordered incoming rows for key {key} have different payloads"
                )
            duplicate_ignored += 1
            continue

        candidate_position = _position(candidate, ordering_columns)
        current_position = _position(current, ordering_columns)
        assert candidate_position is not None
        assert current_position is not None
        comparison = _compare_positions(candidate_position, current_position)

        if comparison > 0:
            selected[key] = candidate
            incoming_superseded += 1
        elif comparison < 0:
            incoming_superseded += 1
        elif candidate_payload == current_payload:
            duplicate_ignored += 1
        else:
            raise SCD1ConflictError(
                f"conflicting incoming rows for key {key} at equal position "
                f"{candidate_position}"
            )

    return selected, incoming_superseded, duplicate_ignored


def apply_scd1(
    existing_rows: Sequence[Mapping[str, Any]],
    incoming_rows: Sequence[Mapping[str, Any]],
    *,
    merge_key: tuple[str, ...],
    ordering_columns: tuple[str, ...] = (),
    policy: SCD1ApplyPolicy | None = None,
) -> SCD1ApplyResult:
    """Apply deterministic SCD1/current-state semantics.

    Ordering columns normally represent source event time, source version and/or
    sequence/LSN metadata. For incremental updates, callers should provide an
    ordering tuple. Without ordering, changed updates to existing keys fail closed
    unless ``allow_unordered_updates`` is explicitly enabled for an authoritative
    source/capture contract.

    Exact reruns are idempotent. Older source positions are ignored or rejected by
    policy. Conflicting payloads at the same source position always fail closed.
    """

    if not merge_key:
        raise ValueError("merge_key is required for SCD1")
    if len(set(merge_key)) != len(merge_key):
        raise ValueError("SCD1 merge_key columns must be unique")
    if len(set(ordering_columns)) != len(ordering_columns):
        raise ValueError("SCD1 ordering columns must be unique")

    effective_policy = policy or SCD1ApplyPolicy()
    rows_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}

    for raw in existing_rows:
        row = deepcopy(dict(raw))
        key = _key(row, merge_key)
        if key in rows_by_key:
            raise ValueError(f"existing SCD1 target contains duplicate key {key}")
        if ordering_columns:
            _position(row, ordering_columns)
        rows_by_key[key] = row

    selected, incoming_superseded, duplicate_ignored = _select_latest_incoming(
        incoming_rows,
        merge_key=merge_key,
        ordering_columns=ordering_columns,
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
                raise SCD1OrderingError(
                    f"changed SCD1 update for key {key} has no ordering columns"
                )
            merged = deepcopy(current)
            merged.update(candidate)
            rows_by_key[key] = merged
            updated += 1
            continue

        candidate_position = _position(candidate, ordering_columns)
        current_position = _position(current, ordering_columns)
        assert candidate_position is not None
        assert current_position is not None
        comparison = _compare_positions(candidate_position, current_position)

        if comparison < 0:
            if effective_policy.stale_record_action is StaleRecordAction.ERROR:
                raise SCD1OrderingError(
                    f"stale SCD1 row for key {key}: candidate={candidate_position}, "
                    f"current={current_position}"
                )
            stale_ignored += 1
            continue

        if comparison == 0:
            raise SCD1ConflictError(
                f"conflicting SCD1 row for key {key} at equal position "
                f"{candidate_position}"
            )

        merged = deepcopy(current)
        merged.update(candidate)
        rows_by_key[key] = merged
        updated += 1

    ordered_rows = tuple(
        deepcopy(rows_by_key[key]) for key in sorted(rows_by_key, key=repr)
    )
    return SCD1ApplyResult(
        rows=ordered_rows,
        mutations=MutationCounts(inserted=inserted, updated=updated, deleted=0),
        stale_ignored=stale_ignored,
        incoming_superseded=incoming_superseded,
        duplicate_ignored=duplicate_ignored,
    )


class InMemorySCD1Target:
    """Small deterministic target adapter for reference/certification tests."""

    def __init__(self, rows: Sequence[Mapping[str, Any]] = ()) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)

    def read(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(dict(row)) for row in self._rows)

    def replace(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)
