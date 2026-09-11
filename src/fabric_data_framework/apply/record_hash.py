"""Canonical type-preserving hashing for change-detection apply strategies."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from fabric_data_framework.contracts.typed_values import canonical_typed_json_bytes


def hash_tracked_attributes(
    row: Mapping[str, Any],
    tracked_columns: tuple[str, ...],
) -> str:
    """Hash tracked values without collapsing distinct Python value types."""

    payload = {column: row.get(column) for column in tracked_columns}
    return hashlib.sha256(canonical_typed_json_bytes(payload)).hexdigest()


__all__ = ["hash_tracked_attributes"]
