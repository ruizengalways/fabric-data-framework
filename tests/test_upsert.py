from datetime import datetime, timezone

import pytest

from fabric_data_framework.apply.upsert import (
    StaleRecordAction,
    UpsertApplyPolicy,
    UpsertConflictError,
    UpsertOrderingError,
    apply_upsert,
)


def _ts(hour: int) -> datetime:
    return datetime(2026, 8, 28, hour, tzinfo=timezone.utc)


def test_upsert_inserts_and_updates_with_composite_merge_key():
    existing = (
        {
            "tenant_id": "A",
            "customer_id": 1,
            "name": "Old",
            "modified_at": _ts(9),
            "target_only": "preserved",
        },
    )
    incoming = (
        {
            "tenant_id": "A",
            "customer_id": 1,
            "name": "New",
            "modified_at": _ts(10),
        },
        {
            "tenant_id": "A",
            "customer_id": 2,
            "name": "Second",
            "modified_at": _ts(10),
        },
    )

    result = apply_upsert(
        existing,
        incoming,
        merge_key=("tenant_id", "customer_id"),
        ordering_columns=("modified_at",),
    )

    rows = {row["customer_id"]: row for row in result.rows}
    assert result.mutations.inserted == 1
    assert result.mutations.updated == 1
    assert rows[1]["name"] == "New"
    assert rows[1]["target_only"] == "preserved"


def test_upsert_exact_rerun_is_idempotent():
    row = {"customer_id": 1, "name": "Same", "modified_at": _ts(10), "version": 7}

    result = apply_upsert(
        (row,),
        (row,),
        merge_key=("customer_id",),
        ordering_columns=("modified_at", "version"),
    )

    assert result.rows == (row,)
    assert result.mutations.inserted == 0
    assert result.mutations.updated == 0
    assert result.duplicate_ignored == 1


def test_upsert_selects_latest_candidate_and_counts_superseded_rows():
    incoming = (
        {"customer_id": 1, "name": "v1", "modified_at": _ts(9), "version": 1},
        {"customer_id": 1, "name": "v3", "modified_at": _ts(11), "version": 3},
        {"customer_id": 1, "name": "v2", "modified_at": _ts(10), "version": 2},
    )

    result = apply_upsert(
        (),
        incoming,
        merge_key=("customer_id",),
        ordering_columns=("modified_at", "version"),
    )

    assert result.rows[0]["name"] == "v3"
    assert result.mutations.inserted == 1
    assert result.incoming_superseded == 2
    assert result.duplicate_ignored == 0


def test_upsert_stale_row_is_ignored_or_can_fail_closed():
    existing = (
        {"customer_id": 1, "name": "Current", "modified_at": _ts(11), "version": 3},
    )
    stale = (
        {"customer_id": 1, "name": "Stale", "modified_at": _ts(10), "version": 2},
    )

    ignored = apply_upsert(
        existing,
        stale,
        merge_key=("customer_id",),
        ordering_columns=("modified_at", "version"),
    )
    assert ignored.rows[0]["name"] == "Current"
    assert ignored.stale_ignored == 1
    assert ignored.mutations.updated == 0

    with pytest.raises(UpsertOrderingError, match="stale UPSERT row"):
        apply_upsert(
            existing,
            stale,
            merge_key=("customer_id",),
            ordering_columns=("modified_at", "version"),
            policy=UpsertApplyPolicy(stale_record_action=StaleRecordAction.ERROR),
        )


def test_upsert_equal_position_conflict_fails_closed():
    existing = (
        {"customer_id": 1, "name": "A", "modified_at": _ts(10), "sequence": 5},
    )
    incoming = (
        {"customer_id": 1, "name": "B", "modified_at": _ts(10), "sequence": 5},
    )

    with pytest.raises(UpsertConflictError, match="equal position"):
        apply_upsert(
            existing,
            incoming,
            merge_key=("customer_id",),
            ordering_columns=("modified_at", "sequence"),
        )


def test_upsert_batch_conflict_at_equal_position_fails_closed():
    incoming = (
        {"customer_id": 1, "name": "A", "modified_at": _ts(10)},
        {"customer_id": 1, "name": "B", "modified_at": _ts(10)},
    )

    with pytest.raises(UpsertConflictError, match="conflicting incoming rows"):
        apply_upsert(
            (),
            incoming,
            merge_key=("customer_id",),
            ordering_columns=("modified_at",),
        )


def test_upsert_changed_unordered_update_requires_explicit_authority():
    existing = ({"customer_id": 1, "name": "Old"},)
    incoming = ({"customer_id": 1, "name": "New"},)

    with pytest.raises(UpsertOrderingError, match="no ordering columns"):
        apply_upsert(existing, incoming, merge_key=("customer_id",))

    result = apply_upsert(
        existing,
        incoming,
        merge_key=("customer_id",),
        policy=UpsertApplyPolicy(allow_unordered_updates=True),
    )
    assert result.rows[0]["name"] == "New"
    assert result.mutations.updated == 1
