"""Append-once apply semantics with explicit immutable record identity.

APPEND is not "blindly extend a list".  A production append target needs a stable
source-controlled identity so retries/backfills/replays can distinguish an exact
re-observation from a conflicting reuse of an already-published identity.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from pydantic import Field

from ..config import FrozenModel, canonical_hash


APPEND_IDENTITY_HASH = "_framework_append_identity_hash"
APPEND_PAYLOAD_HASH = "_framework_append_payload_hash"
_RESERVED_APPEND_FIELDS = frozenset({APPEND_IDENTITY_HASH, APPEND_PAYLOAD_HASH})


class AppendApplyError(ValueError):
    """Base append-once semantic error."""


class AppendIdentityError(AppendApplyError):
    """Append identity is missing, null, malformed or already duplicated in target."""


class AppendConflictError(AppendApplyError):
    """The same append identity was observed with conflicting business payload."""


class AppendApplyResult(FrozenModel):
    rows: tuple[dict[str, Any], ...]
    inserted: int = Field(ge=0)
    replayed: int = Field(ge=0)
    duplicate_incoming: int = Field(ge=0)


def _identity(row: Mapping[str, Any], append_identity: tuple[str, ...]) -> tuple[Any, ...]:
    if not append_identity:
        raise AppendIdentityError("APPEND requires at least one append_identity column")
    values: list[Any] = []
    for column in append_identity:
        if column not in row:
            raise AppendIdentityError(f"append identity column {column!r} is missing")
        value = row[column]
        if value is None:
            raise AppendIdentityError(f"append identity column {column!r} cannot be null")
        if isinstance(value, (dict, list, set)):
            raise AppendIdentityError(
                f"append identity column {column!r} must be a stable scalar value"
            )
        values.append(value)
    return tuple(values)


def _business_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return source/business payload while excluding framework-owned volatile evidence."""

    return {key: value for key, value in row.items() if not key.startswith("_framework_")}


def _incoming_fingerprint(row: Mapping[str, Any]) -> str:
    return canonical_hash(_business_payload(row))


def _existing_fingerprint_for_incoming(
    existing: Mapping[str, Any], incoming: Mapping[str, Any]
) -> str:
    stored = existing.get(APPEND_PAYLOAD_HASH)
    if stored is not None:
        return str(stored)

    incoming_payload = _business_payload(incoming)
    missing = [column for column in incoming_payload if column not in existing]
    if missing:
        raise AppendConflictError(
            "existing append identity is missing incoming business columns: "
            + ", ".join(sorted(missing))
        )
    # Existing targets may legitimately carry target-only enrichment/audit columns.
    # Compare the complete incoming business projection, not unrelated target fields.
    return canonical_hash({column: existing[column] for column in incoming_payload})


def _decorate(row: Mapping[str, Any], identity: tuple[Any, ...], payload_hash: str) -> dict[str, Any]:
    if _RESERVED_APPEND_FIELDS.intersection(row):
        raise AppendIdentityError(
            "incoming row cannot provide framework-owned append identity/hash fields"
        )
    decorated = deepcopy(dict(row))
    decorated[APPEND_IDENTITY_HASH] = canonical_hash(identity)
    decorated[APPEND_PAYLOAD_HASH] = payload_hash
    return decorated


def apply_append(
    existing_rows: Sequence[Mapping[str, Any]],
    incoming_rows: Sequence[Mapping[str, Any]],
    *,
    append_identity: tuple[str, ...],
) -> AppendApplyResult:
    """Plan an append-once mutation without mutating the supplied target rows.

    Guarantees:

    - every identity is explicit and non-null;
    - duplicate identities already present in target fail closed;
    - exact duplicate observations inside one incoming batch are collapsed;
    - conflicting duplicate observations fail before any mutation is returned;
    - an existing identity with the same business payload is an idempotent replay;
    - an existing identity with different business payload fails closed;
    - only genuinely new identities are appended.
    """

    if not append_identity:
        raise AppendIdentityError("APPEND requires at least one append_identity column")
    if len(set(append_identity)) != len(append_identity):
        raise AppendIdentityError("append_identity columns must be unique")

    existing = tuple(deepcopy(dict(row)) for row in existing_rows)
    existing_by_identity: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in existing:
        identity = _identity(row, append_identity)
        if identity in existing_by_identity:
            raise AppendIdentityError(
                f"target already contains duplicate append identity {identity!r}"
            )
        stored_identity_hash = row.get(APPEND_IDENTITY_HASH)
        if stored_identity_hash is not None and str(stored_identity_hash) != canonical_hash(identity):
            raise AppendIdentityError(
                f"target append identity evidence does not match row identity {identity!r}"
            )
        existing_by_identity[identity] = row

    unique_incoming: dict[tuple[Any, ...], tuple[dict[str, Any], str]] = {}
    order: list[tuple[Any, ...]] = []
    duplicate_incoming = 0
    for raw_row in incoming_rows:
        row = deepcopy(dict(raw_row))
        identity = _identity(row, append_identity)
        payload_hash = _incoming_fingerprint(row)
        prior = unique_incoming.get(identity)
        if prior is not None:
            if prior[1] != payload_hash:
                raise AppendConflictError(
                    f"incoming batch reuses append identity {identity!r} with conflicting payload"
                )
            duplicate_incoming += 1
            continue
        unique_incoming[identity] = (row, payload_hash)
        order.append(identity)

    appended: list[dict[str, Any]] = []
    replayed = 0
    for identity in order:
        row, payload_hash = unique_incoming[identity]
        current = existing_by_identity.get(identity)
        if current is not None:
            if _existing_fingerprint_for_incoming(current, row) != payload_hash:
                raise AppendConflictError(
                    f"append identity {identity!r} already exists with different payload"
                )
            replayed += 1
            continue
        appended.append(_decorate(row, identity, payload_hash))

    return AppendApplyResult(
        rows=existing + tuple(appended),
        inserted=len(appended),
        replayed=replayed,
        duplicate_incoming=duplicate_incoming,
    )


class InMemoryAppendTarget:
    """Deterministic target adapter used by reference/certification tests."""

    def __init__(self, rows: Sequence[Mapping[str, Any]] = ()) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)

    def read(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(dict(row)) for row in self._rows)

    def replace(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = tuple(deepcopy(dict(row)) for row in rows)


__all__ = [
    "APPEND_IDENTITY_HASH",
    "APPEND_PAYLOAD_HASH",
    "AppendApplyError",
    "AppendApplyResult",
    "AppendConflictError",
    "AppendIdentityError",
    "InMemoryAppendTarget",
    "apply_append",
]
