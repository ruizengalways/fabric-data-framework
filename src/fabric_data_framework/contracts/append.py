"""Provider-neutral APPEND identity and business-payload primitives."""

from __future__ import annotations

from typing import Any, Mapping

from fabric_data_framework.contracts.hashing import canonical_hash


FRAMEWORK_FIELD_PREFIX = "_framework_"
APPEND_IDENTITY_HASH = "_framework_append_identity_hash"
APPEND_PAYLOAD_HASH = "_framework_append_payload_hash"
RESERVED_APPEND_FIELDS = frozenset({APPEND_IDENTITY_HASH, APPEND_PAYLOAD_HASH})


def business_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return source/business values while excluding framework-owned volatile evidence."""

    return {
        key: value
        for key, value in row.items()
        if not key.startswith(FRAMEWORK_FIELD_PREFIX)
    }


def append_payload_fingerprint(row: Mapping[str, Any]) -> str:
    return canonical_hash(business_payload(row))


def append_identity_fingerprint(identity: tuple[Any, ...]) -> str:
    return canonical_hash(identity)


__all__ = [
    "APPEND_IDENTITY_HASH",
    "APPEND_PAYLOAD_HASH",
    "FRAMEWORK_FIELD_PREFIX",
    "RESERVED_APPEND_FIELDS",
    "append_identity_fingerprint",
    "append_payload_fingerprint",
    "business_payload",
]
