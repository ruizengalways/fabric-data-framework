from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from fabric_data_framework.apply.record_hash import hash_tracked_attributes
from fabric_data_framework.apply.scd2 import apply_scd2
from fabric_data_framework.contracts.typed_values import (
    TypedValueError,
    canonical_typed_json_bytes,
    decode_typed_value,
    encode_typed_value,
)


NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 11, 13, 0, tzinfo=timezone.utc)


def test_typed_codec_round_trips_supported_nested_values():
    value = {
        "none": None,
        "bool": True,
        "int": 1,
        "float": 1.5,
        "text": "1",
        "datetime": NOW,
        "decimal": Decimal("1.2300"),
        "uuid": UUID("12345678-1234-5678-1234-567812345678"),
        "list": [1, "x"],
        "tuple": (False, Decimal("2.0")),
        "nested": {"b": 2, "a": 1},
    }

    decoded = decode_typed_value(encode_typed_value(value))

    assert decoded["none"] is None
    assert decoded["bool"] is True
    assert decoded["int"] == 1 and type(decoded["int"]) is int
    assert decoded["float"] == 1.5 and type(decoded["float"]) is float
    assert decoded["text"] == "1"
    assert decoded["datetime"] == NOW
    assert decoded["decimal"] == Decimal("1.23")
    assert decoded["uuid"] == value["uuid"]
    assert decoded["list"] == [1, "x"]
    assert decoded["tuple"] == (False, Decimal("2"))
    assert decoded["nested"] == {"a": 1, "b": 2}


def test_canonical_typed_bytes_ignore_dict_input_order():
    assert canonical_typed_json_bytes({"b": 2, "a": 1}) == canonical_typed_json_bytes(
        {"a": 1, "b": 2}
    )


def test_typed_hash_distinguishes_values_that_default_str_would_collapse():
    assert hash_tracked_attributes({"v": Decimal("1")}, ("v",)) != hash_tracked_attributes(
        {"v": "1"}, ("v",)
    )
    assert hash_tracked_attributes({"v": NOW}, ("v",)) != hash_tracked_attributes(
        {"v": NOW.isoformat()}, ("v",)
    )
    assert hash_tracked_attributes({"v": 1}, ("v",)) != hash_tracked_attributes(
        {"v": True}, ("v",)
    )


def test_scd2_creates_new_version_when_tracked_type_changes():
    first = apply_scd2(
        (),
        ({"customer_id": "C1", "value": Decimal("1"), "changed_at": NOW},),
        business_key=("customer_id",),
        tracked_columns=("value",),
        effective_time_column="changed_at",
        dataset_run_id=uuid4(),
    )

    second = apply_scd2(
        first.rows,
        ({"customer_id": "C1", "value": "1", "changed_at": LATER},),
        business_key=("customer_id",),
        tracked_columns=("value",),
        effective_time_column="changed_at",
        dataset_run_id=uuid4(),
    )

    assert second.mutations.updated == 1
    assert len(second.rows) == 2
    current = next(row for row in second.rows if row["_framework_is_current"])
    assert current["value"] == "1"
    assert type(current["value"]) is str


def test_typed_codec_rejects_naive_datetime_and_unsupported_type():
    with pytest.raises(TypedValueError, match="timezone-aware"):
        encode_typed_value(datetime(2026, 9, 11, 12, 0))

    with pytest.raises(TypedValueError, match="unsupported typed value"):
        encode_typed_value(object())
