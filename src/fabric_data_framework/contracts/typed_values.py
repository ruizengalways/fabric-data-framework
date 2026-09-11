"""Deterministic typed value encoding for persisted framework evidence and hashing."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import math
from typing import Any, Mapping, Sequence
from uuid import UUID


TYPE_FIELD = "$type"
VALUE_FIELD = "value"
ITEMS_FIELD = "items"


class TypedValueError(ValueError):
    """Raised when a value cannot be encoded or decoded safely."""


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise TypedValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc)


def encode_typed_value(value: Any) -> dict[str, Any]:
    """Encode one supported Python value into a JSON-native, type-preserving object.

    The representation is intentionally explicit. Unsupported values fail closed rather
    than falling back to ``str(value)`` because stringification can silently collapse
    distinct business values.
    """

    if value is None:
        return {TYPE_FIELD: "none"}
    if isinstance(value, bool):
        return {TYPE_FIELD: "bool", VALUE_FIELD: value}
    if isinstance(value, int):
        return {TYPE_FIELD: "int", VALUE_FIELD: str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypedValueError("non-finite float values are not supported")
        return {TYPE_FIELD: "float", VALUE_FIELD: value.hex()}
    if isinstance(value, str):
        return {TYPE_FIELD: "str", VALUE_FIELD: value}
    if isinstance(value, datetime):
        normalized = _aware_datetime(value)
        return {
            TYPE_FIELD: "datetime",
            VALUE_FIELD: normalized.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        }
    if isinstance(value, date):
        return {TYPE_FIELD: "date", VALUE_FIELD: value.isoformat()}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise TypedValueError("non-finite Decimal values are not supported")
        normalized = value.normalize()
        if normalized == 0:
            normalized = Decimal(0)
        return {TYPE_FIELD: "decimal", VALUE_FIELD: str(normalized)}
    if isinstance(value, UUID):
        return {TYPE_FIELD: "uuid", VALUE_FIELD: str(value)}
    if isinstance(value, tuple):
        return {
            TYPE_FIELD: "tuple",
            ITEMS_FIELD: [encode_typed_value(item) for item in value],
        }
    if isinstance(value, list):
        return {
            TYPE_FIELD: "list",
            ITEMS_FIELD: [encode_typed_value(item) for item in value],
        }
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypedValueError("mapping keys must be strings")
        return {
            TYPE_FIELD: "dict",
            ITEMS_FIELD: [
                [key, encode_typed_value(value[key])]
                for key in sorted(value)
            ],
        }
    raise TypedValueError(f"unsupported typed value: {type(value).__name__}")


def _require_exact_keys(payload: Mapping[str, Any], expected: set[str]) -> None:
    observed = set(payload)
    if observed != expected:
        raise TypedValueError(
            "typed value has invalid fields: "
            f"expected={sorted(expected)}, observed={sorted(observed)}"
        )


def decode_typed_value(payload: Any) -> Any:
    """Decode a value produced by :func:`encode_typed_value`.

    Tagged payloads are strict: malformed or unknown representations fail closed.
    """

    if not isinstance(payload, dict) or TYPE_FIELD not in payload:
        raise TypedValueError("typed value must be an object containing $type")
    kind = payload.get(TYPE_FIELD)
    if not isinstance(kind, str):
        raise TypedValueError("typed value $type must be a string")

    if kind == "none":
        _require_exact_keys(payload, {TYPE_FIELD})
        return None
    if kind == "bool":
        _require_exact_keys(payload, {TYPE_FIELD, VALUE_FIELD})
        value = payload[VALUE_FIELD]
        if type(value) is not bool:
            raise TypedValueError("bool typed value must contain a boolean")
        return value
    if kind == "int":
        _require_exact_keys(payload, {TYPE_FIELD, VALUE_FIELD})
        value = payload[VALUE_FIELD]
        if not isinstance(value, str):
            raise TypedValueError("int typed value must contain a string")
        try:
            return int(value)
        except ValueError as exc:
            raise TypedValueError("invalid encoded int value") from exc
    if kind == "float":
        _require_exact_keys(payload, {TYPE_FIELD, VALUE_FIELD})
        value = payload[VALUE_FIELD]
        if not isinstance(value, str):
            raise TypedValueError("float typed value must contain a string")
        try:
            parsed = float.fromhex(value)
        except ValueError as exc:
            raise TypedValueError("invalid encoded float value") from exc
        if not math.isfinite(parsed):
            raise TypedValueError("non-finite encoded float value")
        return parsed
    if kind == "str":
        _require_exact_keys(payload, {TYPE_FIELD, VALUE_FIELD})
        value = payload[VALUE_FIELD]
        if not isinstance(value, str):
            raise TypedValueError("str typed value must contain a string")
        return value
    if kind == "datetime":
        _require_exact_keys(payload, {TYPE_FIELD, VALUE_FIELD})
        value = payload[VALUE_FIELD]
        if not isinstance(value, str):
            raise TypedValueError("datetime typed value must contain a string")
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise TypedValueError("invalid encoded datetime value") from exc
        return _aware_datetime(parsed)
    if kind == "date":
        _require_exact_keys(payload, {TYPE_FIELD, VALUE_FIELD})
        value = payload[VALUE_FIELD]
        if not isinstance(value, str):
            raise TypedValueError("date typed value must contain a string")
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise TypedValueError("invalid encoded date value") from exc
    if kind == "decimal":
        _require_exact_keys(payload, {TYPE_FIELD, VALUE_FIELD})
        value = payload[VALUE_FIELD]
        if not isinstance(value, str):
            raise TypedValueError("decimal typed value must contain a string")
        try:
            parsed = Decimal(value)
        except Exception as exc:
            raise TypedValueError("invalid encoded Decimal value") from exc
        if not parsed.is_finite():
            raise TypedValueError("non-finite encoded Decimal value")
        return parsed
    if kind == "uuid":
        _require_exact_keys(payload, {TYPE_FIELD, VALUE_FIELD})
        value = payload[VALUE_FIELD]
        if not isinstance(value, str):
            raise TypedValueError("uuid typed value must contain a string")
        try:
            return UUID(value)
        except ValueError as exc:
            raise TypedValueError("invalid encoded UUID value") from exc
    if kind in {"list", "tuple"}:
        _require_exact_keys(payload, {TYPE_FIELD, ITEMS_FIELD})
        items = payload[ITEMS_FIELD]
        if not isinstance(items, list):
            raise TypedValueError(f"{kind} typed value items must be a list")
        decoded = [decode_typed_value(item) for item in items]
        return decoded if kind == "list" else tuple(decoded)
    if kind == "dict":
        _require_exact_keys(payload, {TYPE_FIELD, ITEMS_FIELD})
        items = payload[ITEMS_FIELD]
        if not isinstance(items, list):
            raise TypedValueError("dict typed value items must be a list")
        result: dict[str, Any] = {}
        previous_key: str | None = None
        for item in items:
            if not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], str):
                raise TypedValueError("dict typed value item must be [string-key, typed-value]")
            key = item[0]
            if key in result:
                raise TypedValueError("dict typed value contains a duplicate key")
            if previous_key is not None and key <= previous_key:
                raise TypedValueError("dict typed value keys must be strictly sorted")
            result[key] = decode_typed_value(item[1])
            previous_key = key
        return result
    raise TypedValueError(f"unsupported typed value tag: {kind!r}")


def canonical_typed_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for a supported typed value."""

    return json.dumps(
        encode_typed_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def decode_legacy_or_typed_scalar(payload: Any) -> Any:
    """Decode new tagged scalar values while accepting safe legacy JSON scalars.

    Legacy persisted JSON cannot distinguish an original datetime from an ISO-looking
    string, so legacy strings remain strings. Container-shaped legacy payloads are
    rejected rather than guessed.
    """

    if isinstance(payload, dict) and TYPE_FIELD in payload:
        value = decode_typed_value(payload)
        if isinstance(value, (list, tuple, dict)):
            raise TypedValueError("expected a scalar typed value")
        return value
    if payload is None or type(payload) in {str, int, float, bool}:
        if isinstance(payload, float) and not math.isfinite(payload):
            raise TypedValueError("non-finite legacy float value")
        return payload
    raise TypedValueError("unsupported legacy persisted scalar representation")


__all__ = [
    "TypedValueError",
    "canonical_typed_json_bytes",
    "decode_legacy_or_typed_scalar",
    "decode_typed_value",
    "encode_typed_value",
]
