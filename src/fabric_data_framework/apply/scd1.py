"""Deterministic current-state SCD1 apply semantics.

Native Fabric movement may land candidate rows; this module remains the canonical
framework fallback for SCD1 apply semantics. Hard ordering/idempotency behavior is
shared with generic UPSERT through ``apply.current_state``.
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


SCD1ConflictError = CurrentStateConflictError
SCD1OrderingError = CurrentStateOrderingError
SCD1ApplyPolicy = CurrentStateApplyPolicy
SCD1ApplyResult = CurrentStateApplyResult


def apply_scd1(
    existing_rows: Sequence[Mapping[str, Any]],
    incoming_rows: Sequence[Mapping[str, Any]],
    *,
    merge_key: tuple[str, ...],
    ordering_columns: tuple[str, ...] = (),
    policy: SCD1ApplyPolicy | None = None,
) -> SCD1ApplyResult:
    """Apply SCD1/current-state semantics with deterministic source ordering."""

    return apply_ordered_current_state(
        existing_rows,
        incoming_rows,
        merge_key=merge_key,
        ordering_columns=ordering_columns,
        policy=policy,
        strategy_name="SCD1",
    )


class InMemorySCD1Target:
    """Small deterministic target adapter for reference/certification tests."""

    def __init__(self, rows: Sequence[Mapping[str, Any]] = ()) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)

    def read(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(dict(row)) for row in self._rows)

    def replace(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)


__all__ = [
    "InMemorySCD1Target",
    "SCD1ApplyPolicy",
    "SCD1ApplyResult",
    "SCD1ConflictError",
    "SCD1OrderingError",
    "StaleRecordAction",
    "apply_scd1",
]
