"""Shared fail-closed validation for text retained as integration evidence."""

from __future__ import annotations

import re


_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(client[_-]?secret|password|passwd|access[_-]?token|refresh[_-]?token)\b"),
    re.compile(r"(?i)\bauthorization\s*[:=]"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)([?&](sig|token|secret|password|client_secret)=)"),
)


def assert_safe_retained_text(value: str, field_name: str = "retained evidence text") -> str:
    """Reject obvious credential-bearing text before it is written to retained evidence."""

    for pattern in _SECRET_PATTERNS:
        if pattern.search(value):
            raise ValueError(f"{field_name} appears to contain credential material")
    if "://" in value:
        authority = value.split("://", 1)[1].split("/", 1)[0]
        if "@" in authority and ":" in authority.split("@", 1)[0]:
            raise ValueError(f"{field_name} must not contain URI user-info credentials")
    return value


__all__ = ["assert_safe_retained_text"]
