"""Credential safety, redaction and bounded retention helpers."""

from __future__ import annotations

from datetime import date, datetime
import json
import math
import re
from typing import Any, Mapping, Sequence
from uuid import UUID


_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(client[_-]?secret|password|passwd|access[_-]?token|refresh[_-]?token)\b"),
    re.compile(r"(?i)\bauthorization\s*[:=]"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)([?&](sig|token|secret|password|client_secret)=)"),
)
_SENSITIVE_KEY = re.compile(
    r"(?i)(password|passwd|pwd|token|secret|authorization|account[_-]?key|"
    r"shared[_-]?access[_-]?signature|connection[_-]?string)"
)
_ASSIGNMENT_SECRET = re.compile(
    r"(?i)\b(password|passwd|pwd|client[_-]?secret|access[_-]?token|refresh[_-]?token|"
    r"token|secret|authorization|account[_-]?key|shared[_-]?access[_-]?signature)"
    r"\s*[:=]\s*([^\s,;]+)"
)
_BEARER_SECRET = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_URI_USERINFO = re.compile(r"([a-z][a-z0-9+.-]*://)([^/@\s:]+):([^/@\s]+)@", re.I)

AUDIT_MAX_DEPTH = 6
AUDIT_MAX_STRING = 2048
AUDIT_MAX_ITEMS = 50
AUDIT_MAX_SERIALIZED_BYTES = 16384
_REDACTED = "[REDACTED]"
_TRUNCATED = "... [truncated]"


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


def _truncate_text(value: str, limit: int = AUDIT_MAX_STRING) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - len(_TRUNCATED))] + _TRUNCATED


def sanitize_audit_text(value: object, *, max_length: int = AUDIT_MAX_STRING) -> str:
    """Redact common credential syntax and bound one retained audit string."""

    text = str(value)
    text = _ASSIGNMENT_SECRET.sub(lambda match: f"{match.group(1)}={_REDACTED}", text)
    text = _BEARER_SECRET.sub(f"Bearer {_REDACTED}", text)
    text = _URI_USERINFO.sub(lambda match: f"{match.group(1)}{_REDACTED}@", text)
    return _truncate_text(text, max_length)


def _sanitize(value: Any, *, depth: int) -> Any:
    if depth > AUDIT_MAX_DEPTH:
        return "[MAX_DEPTH_REACHED]"
    if value is None or type(value) in {bool, int}:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else "[NON_FINITE_FLOAT]"
    if isinstance(value, str):
        return sanitize_audit_text(value)
    if isinstance(value, Exception):
        return sanitize_audit_text(f"{type(value).__name__}: {value}")
    if isinstance(value, (UUID, datetime, date)):
        return str(value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        items = list(value.items())
        for raw_key, raw_value in items[:AUDIT_MAX_ITEMS]:
            key = _truncate_text(str(raw_key), 256)
            if _SENSITIVE_KEY.search(key):
                result[key] = _REDACTED
            else:
                result[key] = _sanitize(raw_value, depth=depth + 1)
        if len(items) > AUDIT_MAX_ITEMS:
            result["_truncated_items"] = len(items) - AUDIT_MAX_ITEMS
        return result
    if isinstance(value, (list, tuple)):
        items = list(value)
        result = [_sanitize(item, depth=depth + 1) for item in items[:AUDIT_MAX_ITEMS]]
        if len(items) > AUDIT_MAX_ITEMS:
            result.append(f"[{len(items) - AUDIT_MAX_ITEMS} more item(s) truncated]")
        return result
    return f"[UNSUPPORTED_AUDIT_VALUE:{type(value).__name__}]"


def sanitize_audit_value(value: Any) -> Any:
    """Recursively sanitize provider/audit data before constructing audit models."""

    sanitized = _sanitize(value, depth=0)
    try:
        encoded = json.dumps(
            sanitized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return {"_truncated": True, "reason": "audit payload could not be serialized safely"}
    if len(encoded) <= AUDIT_MAX_SERIALIZED_BYTES:
        return sanitized
    return {
        "_truncated": True,
        "reason": "audit payload exceeded retained size limit",
        "original_serialized_bytes": len(encoded),
    }


def sanitize_audit_details(value: object | None) -> dict[str, Any] | None:
    if value is None:
        return None
    sanitized = sanitize_audit_value(value)
    if isinstance(sanitized, dict):
        return sanitized
    return {"value": sanitized}


__all__ = [
    "AUDIT_MAX_DEPTH",
    "AUDIT_MAX_ITEMS",
    "AUDIT_MAX_SERIALIZED_BYTES",
    "AUDIT_MAX_STRING",
    "assert_safe_retained_text",
    "sanitize_audit_details",
    "sanitize_audit_text",
    "sanitize_audit_value",
]
