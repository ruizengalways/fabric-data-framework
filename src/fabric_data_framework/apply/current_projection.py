"""Deterministic current-state projection derived from authoritative SCD2 history.

This module deliberately does not interpret the original source. It receives canonical
history rows plus the business keys whose history changed, re-reads the authoritative
current rows, and produces idempotent current-target mutations. A missing current
history row means delete from the derived current representation.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Mapping, Sequence

from pydantic import Field

from fabric_data_framework.contracts.audit import MutationCounts
from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.typed_values import canonical_typed_json_bytes
from fabric_data_framework.apply.scd2 import IS_CURRENT


class CurrentProjectionError(ValueError):
    """Raised when authoritative history cannot produce one safe current projection."""


class CurrentProjectionApplyResult(FrozenModel):
    rows: tuple[dict[str, Any], ...]
    upserts: tuple[dict[str, Any], ...]
    delete_keys: tuple[dict[str, Any], ...]
    affected_keys: int = Field(ge=0)
    mutations: MutationCounts


def _key(
    row: Mapping[str, Any],
    columns: tuple[str, ...],
    *,
    label: str,
) -> tuple[Any, ...]:
    values = tuple(row.get(column) for column in columns)
    if any(value is None for value in values):
        raise CurrentProjectionError(f"{label} key columns cannot be null/missing: {columns}")
    return values


def _key_payload(columns: tuple[str, ...], key: tuple[Any, ...]) -> dict[str, Any]:
    return dict(zip(columns, key, strict=True))


def _fingerprint(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_typed_json_bytes(dict(row))).hexdigest()


def _project_row(
    row: Mapping[str, Any],
    *,
    projected_columns: tuple[str, ...],
) -> dict[str, Any]:
    missing = [column for column in projected_columns if column not in row]
    if missing:
        raise CurrentProjectionError(
            "authoritative current history row is missing projected columns: "
            + ", ".join(missing)
        )
    return {column: deepcopy(row[column]) for column in projected_columns}


def apply_current_projection(
    existing_rows: Sequence[Mapping[str, Any]],
    history_rows: Sequence[Mapping[str, Any]],
    *,
    business_key: tuple[str, ...],
    projected_columns: tuple[str, ...],
    affected_keys: Sequence[tuple[Any, ...]] | None = None,
    current_flag_column: str = IS_CURRENT,
) -> CurrentProjectionApplyResult:
    """Derive current rows for affected business keys from canonical history.

    ``affected_keys=None`` performs a full rebuild. Incremental callers should pass the
    distinct business keys observed in committed history CDF. Exactly one current
    history row is allowed per affected key. Zero current rows means the derived target
    row must be deleted. Repeating the same change set is idempotent.
    """

    if not business_key:
        raise CurrentProjectionError("current projection requires business_key")
    if len(set(business_key)) != len(business_key):
        raise CurrentProjectionError("current projection business_key columns must be unique")
    if not projected_columns:
        raise CurrentProjectionError("current projection requires projected_columns")
    if len(set(projected_columns)) != len(projected_columns):
        raise CurrentProjectionError("current projection projected_columns must be unique")
    missing_keys = [column for column in business_key if column not in projected_columns]
    if missing_keys:
        raise CurrentProjectionError(
            "projected_columns must include every business key column: "
            + ", ".join(missing_keys)
        )

    existing_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for raw in existing_rows:
        row = deepcopy(dict(raw))
        key = _key(row, business_key, label="existing current target")
        if key in existing_by_key:
            raise CurrentProjectionError(
                f"existing current target contains duplicate business key {key!r}"
            )
        existing_by_key[key] = row

    history_current_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    all_history_keys: set[tuple[Any, ...]] = set()
    for raw in history_rows:
        row = dict(raw)
        key = _key(row, business_key, label="history")
        all_history_keys.add(key)
        current_flag = row.get(current_flag_column)
        if type(current_flag) is not bool:
            raise CurrentProjectionError(
                f"history current flag {current_flag_column!r} must be boolean"
            )
        if not current_flag:
            continue
        if key in history_current_by_key:
            raise CurrentProjectionError(
                f"authoritative history contains more than one current row for key {key!r}"
            )
        history_current_by_key[key] = _project_row(
            row,
            projected_columns=projected_columns,
        )

    if affected_keys is None:
        selected_keys = set(existing_by_key) | all_history_keys
    else:
        selected_keys = set()
        for raw_key in affected_keys:
            key = tuple(raw_key)
            if len(key) != len(business_key):
                raise CurrentProjectionError(
                    "affected key width does not match current projection business_key"
                )
            if any(value is None for value in key):
                raise CurrentProjectionError("affected current projection key cannot contain null")
            selected_keys.add(key)

    result_by_key = {key: deepcopy(row) for key, row in existing_by_key.items()}
    upserts: list[dict[str, Any]] = []
    delete_keys: list[dict[str, Any]] = []
    inserted = 0
    updated = 0
    deleted = 0

    for key in sorted(selected_keys, key=repr):
        authoritative = history_current_by_key.get(key)
        existing = existing_by_key.get(key)
        if authoritative is None:
            if existing is not None:
                result_by_key.pop(key, None)
                delete_keys.append(_key_payload(business_key, key))
                deleted += 1
            continue

        if existing is None:
            result_by_key[key] = deepcopy(authoritative)
            upserts.append(deepcopy(authoritative))
            inserted += 1
            continue

        if _fingerprint(existing) != _fingerprint(authoritative):
            result_by_key[key] = deepcopy(authoritative)
            upserts.append(deepcopy(authoritative))
            updated += 1

    return CurrentProjectionApplyResult(
        rows=tuple(deepcopy(result_by_key[key]) for key in sorted(result_by_key, key=repr)),
        upserts=tuple(upserts),
        delete_keys=tuple(delete_keys),
        affected_keys=len(selected_keys),
        mutations=MutationCounts(inserted=inserted, updated=updated, deleted=deleted),
    )


def rebuild_current_projection(
    existing_rows: Sequence[Mapping[str, Any]],
    history_rows: Sequence[Mapping[str, Any]],
    *,
    business_key: tuple[str, ...],
    projected_columns: tuple[str, ...],
    current_flag_column: str = IS_CURRENT,
) -> CurrentProjectionApplyResult:
    """Rebuild the entire derived current representation from authoritative history."""

    return apply_current_projection(
        existing_rows,
        history_rows,
        business_key=business_key,
        projected_columns=projected_columns,
        affected_keys=None,
        current_flag_column=current_flag_column,
    )


__all__ = [
    "CurrentProjectionApplyResult",
    "CurrentProjectionError",
    "apply_current_projection",
    "rebuild_current_projection",
]
