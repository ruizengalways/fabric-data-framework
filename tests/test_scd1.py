from datetime import datetime, timezone

import pytest

from fabric_data_framework.apply.scd1 import (
    SCD1ApplyPolicy,
    SCD1ConflictError,
    SCD1OrderingError,
    StaleRecordAction,
    apply_scd1,
)


def _ts(hour: int) -> datetime:
    return datetime(2026, 8, 28, hour, tzinfo=timezone.utc)


def test_scd1_inserts_new_key_and_updates_newer_existing_row():
    existing = (
        {"tenant_id": "A", "customer_id": 1, "name": "Old", "modified_at": _ts(9)},
    )
    incoming = (
        {"tenant_id": "A", "customer_id": 1, "name": "New", "modified_at": _ts(10)},
        {"tenant_id": "A", "customer_id": 2, "name": "Second", "modified_at": _ts(10)},
    )

    result = apply_scd1(
        existing,
        incoming,
        merge_key=("tenant_id", "customer_id"),
        ordering_columns=("modified_at",),
    )

    assert result.mutations.inserted == 1
    assert result.mutations.updated == 1
    assert result.stale_ignored == 0
    assert {row["customer_id"]: row["name"] for row in result.rows} == {
        1: "New",
        2: "Second",
    }


def test_scd1_exact_rerun_is_idempotent():
    row = {"customer_id": 1, "name": "Same", "modified_at": _ts(10), "version": 7}

    result = apply_scd1(
        (row,),
        (row,),
        merge_key=("customer_id",),
        ordering_columns=("modified_at", "version"),
    )

    assert result.mutations.inserted == 0
    assert result.mutations.updated == 0
    assert result.duplicate_ignored == 1
    assert result.incoming_superseded == 0
    assert result.rows == (row,)


def test_scd1_selects_latest_incoming_row_per_key():
    incoming = (
        {"customer_id": 1, "name": "v1", "modified_at": _ts(9), "version": 1},
        {"customer_id": 1, "name": "v3", "modified_at": _ts(11), "version": 3},
        {"customer_id": 1, "name": "v2", "modified_at": _ts(10), "version": 2},
    )

    result = apply_scd1(
        (),
        incoming,
        merge_key=("customer_id",),
        ordering_columns=("modified_at", "version"),
    )

    assert len(result.rows) == 1
    assert result.rows[0]["name"] == "v3"
    assert result.mutations.inserted == 1
    assert result.incoming_superseded == 2
    assert result.duplicate_ignored == 0


def test_scd1_ignores_stale_incremental_row_by_default():
    existing = (
        {"customer_id": 1, "name": "Current", "modified_at": _ts(11), "version": 3},
    )
    incoming = (
        {"customer_id": 1, "name": "Stale", "modified_at": _ts(10), "version": 2},
    )

    result = apply_scd1(
        existing,
        incoming,
        merge_key=("customer_id",),
        ordering_columns=("modified_at", "version"),
    )

    assert result.rows[0]["name"] == "Current"
    assert result.stale_ignored == 1
    assert result.mutations.updated == 0


def test_scd1_can_fail_closed_on_stale_incremental_row():
    existing = (
        {"customer_id": 1, "name": "Current", "modified_at": _ts(11)},
    )
    incoming = (
        {"customer_id": 1, "name": "Stale", "modified_at": _ts(10)},
    )

    with pytest.raises(SCD1OrderingError, match="stale SCD1 row"):
        apply_scd1(
            existing,
            incoming,
            merge_key=("customer_id",),
            ordering_columns=("modified_at",),
            policy=SCD1ApplyPolicy(stale_record_action=StaleRecordAction.ERROR),
        )


def test_scd1_equal_position_conflict_fails_closed():
    existing = (
        {"customer_id": 1, "name": "A", "modified_at": _ts(10), "version": 5},
    )
    incoming = (
        {"customer_id": 1, "name": "B", "modified_at": _ts(10), "version": 5},
    )

    with pytest.raises(SCD1ConflictError, match="equal position"):
        apply_scd1(
            existing,
            incoming,
            merge_key=("customer_id",),
            ordering_columns=("modified_at", "version"),
        )


def test_scd1_conflicting_incoming_rows_at_same_position_fail_closed():
    incoming = (
        {"customer_id": 1, "name": "A", "modified_at": _ts(10)},
        {"customer_id": 1, "name": "B", "modified_at": _ts(10)},
    )

    with pytest.raises(SCD1ConflictError, match="conflicting incoming rows"):
        apply_scd1(
            (),
            incoming,
            merge_key=("customer_id",),
            ordering_columns=("modified_at",),
        )


def test_scd1_changed_unordered_update_requires_explicit_authoritative_policy():
    existing = ({"customer_id": 1, "name": "Old"},)
    incoming = ({"customer_id": 1, "name": "New"},)

    with pytest.raises(SCD1OrderingError, match="no ordering columns"):
        apply_scd1(existing, incoming, merge_key=("customer_id",))

    result = apply_scd1(
        existing,
        incoming,
        merge_key=("customer_id",),
        policy=SCD1ApplyPolicy(allow_unordered_updates=True),
    )
    assert result.rows[0]["name"] == "New"
    assert result.mutations.updated == 1


def test_scd1_rejects_null_merge_key_and_null_ordering_values():
    with pytest.raises(ValueError, match="merge key columns cannot be null"):
        apply_scd1(
            (),
            ({"customer_id": None, "name": "bad", "modified_at": _ts(10)},),
            merge_key=("customer_id",),
            ordering_columns=("modified_at",),
        )

    with pytest.raises(SCD1OrderingError, match="ordering columns cannot be null"):
        apply_scd1(
            (),
            ({"customer_id": 1, "name": "bad", "modified_at": None},),
            merge_key=("customer_id",),
            ordering_columns=("modified_at",),
        )
