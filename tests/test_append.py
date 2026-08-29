import pytest

from fabric_data_framework.apply.append import (
    APPEND_IDENTITY_HASH,
    APPEND_PAYLOAD_HASH,
    AppendConflictError,
    AppendIdentityError,
    apply_append,
)


def test_append_inserts_new_rows_and_persists_append_evidence():
    result = apply_append(
        ({"event_id": "E0", "value": 0},),
        (
            {"event_id": "E1", "value": 10},
            {"event_id": "E2", "value": 20},
        ),
        append_identity=("event_id",),
    )

    assert result.inserted == 2
    assert result.replayed == 0
    assert result.duplicate_incoming == 0
    assert [row["event_id"] for row in result.rows] == ["E0", "E1", "E2"]
    assert APPEND_IDENTITY_HASH in result.rows[1]
    assert APPEND_PAYLOAD_HASH in result.rows[1]


def test_append_exact_replay_is_noop_even_when_framework_lineage_changes():
    first = apply_append(
        (),
        ({"event_id": "E1", "value": 10, "_framework_dataset_run_id": "run-1"},),
        append_identity=("event_id",),
    )

    second = apply_append(
        first.rows,
        ({"event_id": "E1", "value": 10, "_framework_dataset_run_id": "run-2"},),
        append_identity=("event_id",),
    )

    assert second.rows == first.rows
    assert second.inserted == 0
    assert second.replayed == 1


def test_append_existing_identity_with_changed_business_payload_fails_closed():
    first = apply_append(
        (),
        ({"event_id": "E1", "value": 10},),
        append_identity=("event_id",),
    )

    with pytest.raises(AppendConflictError, match="different payload"):
        apply_append(
            first.rows,
            ({"event_id": "E1", "value": 11},),
            append_identity=("event_id",),
        )


def test_append_collapses_exact_incoming_duplicate_but_rejects_conflicting_duplicate():
    result = apply_append(
        (),
        (
            {"event_id": "E1", "value": 10},
            {"event_id": "E1", "value": 10},
        ),
        append_identity=("event_id",),
    )
    assert result.inserted == 1
    assert result.duplicate_incoming == 1

    with pytest.raises(AppendConflictError, match="incoming batch reuses"):
        apply_append(
            (),
            (
                {"event_id": "E1", "value": 10},
                {"event_id": "E1", "value": 11},
            ),
            append_identity=("event_id",),
        )


def test_append_requires_present_non_null_scalar_identity():
    with pytest.raises(AppendIdentityError, match="missing"):
        apply_append((), ({"value": 1},), append_identity=("event_id",))
    with pytest.raises(AppendIdentityError, match="cannot be null"):
        apply_append((), ({"event_id": None},), append_identity=("event_id",))
    with pytest.raises(AppendIdentityError, match="stable scalar"):
        apply_append((), ({"event_id": [1, 2]},), append_identity=("event_id",))


def test_append_rejects_duplicate_identity_already_present_in_target():
    with pytest.raises(AppendIdentityError, match="target already contains duplicate"):
        apply_append(
            (
                {"event_id": "E1", "value": 10},
                {"event_id": "E1", "value": 10},
            ),
            (),
            append_identity=("event_id",),
        )


def test_append_exact_replay_can_ignore_target_only_columns_for_legacy_row():
    result = apply_append(
        ({"event_id": "E1", "value": 10, "warehouse_loaded_at": "later"},),
        ({"event_id": "E1", "value": 10},),
        append_identity=("event_id",),
    )
    assert result.inserted == 0
    assert result.replayed == 1


def test_append_rejects_source_spoofing_framework_append_evidence():
    with pytest.raises(AppendIdentityError, match="framework-owned"):
        apply_append(
            (),
            (
                {
                    "event_id": "E1",
                    "value": 10,
                    APPEND_PAYLOAD_HASH: "spoofed",
                },
            ),
            append_identity=("event_id",),
        )


def test_append_supports_composite_identity():
    result = apply_append(
        (),
        (
            {"source": "A", "event_id": 1, "value": "x"},
            {"source": "A", "event_id": 2, "value": "y"},
        ),
        append_identity=("source", "event_id"),
    )
    assert result.inserted == 2
