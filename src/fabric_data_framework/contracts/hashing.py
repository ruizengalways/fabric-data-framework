"""Provider-neutral deterministic hashing primitives.

Cross-layer code must depend on this module rather than metadata/config ownership when
it needs the framework's canonical JSON SHA-256 identity.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_hash(payload: Any) -> str:
    """Return the framework canonical SHA-256 for a JSON-serializable payload."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["canonical_hash"]
