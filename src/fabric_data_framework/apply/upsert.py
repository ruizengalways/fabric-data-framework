"""Deterministic generic UPSERT/current-state apply semantics.

UPSERT is the generic current-state insert-or-update strategy.  It shares the hard
ordering/idempotency primitive with SCD1 while retaining a distinct semantic name in
metadata, planning and audit.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .current_state import (
    CurrentStateApplyPolicy,
    CurrentStateApplyResult,
    CurrentStateConflictError,
    CurrentStateOrderingError,
    StaleRecordAction,
    apply_ordered_current_state,
)


UpsertConflictError = CurrentStateConflictError
UpsertOrderingError = CurrentStateOrderingError
UpsertApplyPolicy = CurrentStateApplyPolicy
UpsertApplyResult = CurrentStateApplyResult


def apply_upsert(
    existing_rows: Sequence[Mapping[str, Any]],
    incoming_rows: Sequence[Mapping[str, Any]],
    *,
    merge_key: tuple[str, ...],
    ordering_columns: tuple[str, ...] = (),
    policy: UpsertApplyPolicy | None = None,
) -> UpsertApplyResult:
    """Insert new keys and update existing keys using deterministic source ordering.

    For an existing key, incoming fields are merged over the current row, retaining
    target-only fields. Exact reruns are no-ops. Older source positions are ignored
    or rejected by policy, and conflicting payloads at one source position fail
    closed.
    """

    return apply_ordered_current_state(
        existing_rows,
        incoming_rows,
        merge_key=merge_key,
        ordering_columns=ordering_columns,
        policy=policy,
        strategy_name="UPSERT",
    )


class InMemoryUpsertTarget:
    """Small deterministic target adapter for reference/certification tests."""

    def __init__(self, rows: Sequence[Mapping[str, Any]] = ()) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)

    def read(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(dict(row)) for row in self._rows)

    def replace(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)


__all__ = [
    "InMemoryUpsertTarget",
    "StaleRecordAction",
    "UpsertApplyPolicy",
    "UpsertApplyResult",
    "UpsertConflictError",
    "UpsertOrderingError",
    "apply_upsert",
]
