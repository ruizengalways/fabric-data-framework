"""Deterministic in-memory/reference SCD2 apply engine."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping, Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .operations import MutationCounts


VALID_FROM = "_framework_valid_from"
VALID_TO = "_framework_valid_to"
IS_CURRENT = "_framework_is_current"
RECORD_HASH = "_framework_record_hash"
SOURCE_DATASET_RUN_ID = "_framework_source_dataset_run_id"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SCD2ApplyResult(FrozenModel):
    rows: tuple[dict[str, Any], ...]
    mutations: MutationCounts


class LateArrivingRecordError(ValueError):
    pass


class SCD2ConflictError(ValueError):
    pass


def _hash_attributes(row: Mapping[str, Any], tracked_columns: tuple[str, ...]) -> str:
    payload = {column: row.get(column) for column in tracked_columns}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _key(row: Mapping[str, Any], columns: tuple[str, ...]) -> tuple[Any, ...]:
    values = tuple(row.get(column) for column in columns)
    if any(value is None for value in values):
        raise ValueError(f"SCD2 key columns cannot be null: {columns}")
    return values


def assert_one_current_row(rows: Sequence[Mapping[str, Any]], business_key: tuple[str, ...]) -> None:
    current: dict[tuple[Any, ...], int] = {}
    for row in rows:
        if row.get(IS_CURRENT) is True:
            key = _key(row, business_key)
            current[key] = current.get(key, 0) + 1
    duplicates = {key: count for key, count in current.items() if count > 1}
    if duplicates:
        raise ValueError(f"SCD2 current-row invariant violated: {duplicates}")


def apply_scd2(
    existing_rows: Sequence[Mapping[str, Any]],
    incoming_rows: Sequence[Mapping[str, Any]],
    *,
    business_key: tuple[str, ...],
    tracked_columns: tuple[str, ...],
    effective_time_column: str,
    dataset_run_id: UUID,
) -> SCD2ApplyResult:
    if not business_key:
        raise ValueError("business_key is required for SCD2")
    if not tracked_columns:
        raise ValueError("tracked_columns is required for SCD2")

    rows = [deepcopy(dict(row)) for row in existing_rows]
    assert_one_current_row(rows, business_key)

    inserted = 0
    updated = 0

    ordered = sorted(
        (deepcopy(dict(row)) for row in incoming_rows),
        key=lambda row: (row[effective_time_column], _key(row, business_key)),
    )

    for incoming in ordered:
        effective_at = incoming.get(effective_time_column)
        if not isinstance(effective_at, datetime):
            raise TypeError(f"{effective_time_column} must contain datetime values")
        key = _key(incoming, business_key)
        new_hash = _hash_attributes(incoming, tracked_columns)

        current_index = next(
            (
                index
                for index, row in enumerate(rows)
                if row.get(IS_CURRENT) is True and _key(row, business_key) == key
            ),
            None,
        )

        if current_index is None:
            new_row = dict(incoming)
            new_row.update(
                {
                    VALID_FROM: effective_at,
                    VALID_TO: None,
                    IS_CURRENT: True,
                    RECORD_HASH: new_hash,
                    SOURCE_DATASET_RUN_ID: str(dataset_run_id),
                }
            )
            rows.append(new_row)
            inserted += 1
            continue

        current = rows[current_index]
        current_from = current.get(VALID_FROM)
        if not isinstance(current_from, datetime):
            raise TypeError("existing SCD2 current row missing datetime valid_from")

        if effective_at < current_from:
            raise LateArrivingRecordError(
                f"late-arriving row for key {key}: {effective_at.isoformat()} < {current_from.isoformat()}"
            )

        current_hash = current.get(RECORD_HASH)
        if current_hash == new_hash:
            continue

        if effective_at == current_from:
            raise SCD2ConflictError(
                f"conflicting row for key {key} at existing effective timestamp {effective_at.isoformat()}"
            )

        current[VALID_TO] = effective_at
        current[IS_CURRENT] = False

        new_row = dict(incoming)
        new_row.update(
            {
                VALID_FROM: effective_at,
                VALID_TO: None,
                IS_CURRENT: True,
                RECORD_HASH: new_hash,
                SOURCE_DATASET_RUN_ID: str(dataset_run_id),
            }
        )
        rows.append(new_row)
        updated += 1

    assert_one_current_row(rows, business_key)
    rows.sort(key=lambda row: (_key(row, business_key), row[VALID_FROM]))
    return SCD2ApplyResult(
        rows=tuple(rows),
        mutations=MutationCounts(inserted=inserted, updated=updated, deleted=0),
    )


class InMemorySCD2Target:
    """Test target adapter that commits only after reconciliation succeeds."""

    def __init__(self, rows: Sequence[Mapping[str, Any]] = ()) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)

    def read(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(dict(row)) for row in self._rows)

    def replace(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)
