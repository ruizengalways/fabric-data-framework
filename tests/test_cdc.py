from datetime import datetime, timezone

import pytest

from fabric_data_framework.apply.cdc import (
    CDCDeleteAction,
    CDCDeleteRejectedError,
    CDC_PARTITION,
    CDC_POSITION,
    apply_cdc_current_state,
)
from fabric_data_framework.capture.cdc import (
    CDCCheckpointTransition,
    CDCConflictError,
    CDCEvidenceError,
    CDCEvent,
    CDCOperation,
    CDCOrderingError,
    CDCSourcePosition,
    build_cdc_checkpoint,
    normalize_cdc_batch,
)
from fabric_data_framework.metadata.config import ApplyStrategy
from fabric_data_framework.contracts.runtime import StateCommitGate


def _position(value: int, *, partition: str = "p0", sequence: int = 0) -> CDCSourcePosition:
    return CDCSourcePosition(partition=partition, values=(value, sequence))


def _event(
    event_id: str,
    operation: CDCOperation,
    position: int,
    *,
    customer_id: int = 1,
    name: str | None = None,
    partition: str = "p0",
    sequence: int = 0,
) -> CDCEvent:
    after = None
    before = None
    if operation is not CDCOperation.DELETE:
        after = {"customer_id": customer_id, "name": name or event_id}
    else:
        before = {"customer_id": customer_id, "name": name or "before-delete"}
    return CDCEvent(
        event_id=event_id,
        operation=operation,
        key={"customer_id": customer_id},
        position=_position(position, partition=partition, sequence=sequence),
        before=before,
        after=after,
        event_time=datetime(2026, 8, 29, 0, position % 60, tzinfo=timezone.utc),
    )


def test_cdc_event_requires_operation_payload_and_aware_time():
    with pytest.raises(ValueError, match="requires after payload"):
        CDCEvent(
            event_id="u1",
            operation=CDCOperation.UPDATE,
            key={"customer_id": 1},
            position=_position(1),
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        CDCEvent(
            event_id="i1",
            operation=CDCOperation.INSERT,
            key={"customer_id": 1},
            position=_position(1),
            after={"customer_id": 1},
            event_time=datetime(2026, 8, 29),
        )


def test_cdc_batch_deduplicates_exact_event_identity():
    event = _event("e1", CDCOperation.INSERT, 1)
    batch = normalize_cdc_batch(
        [event, event],
        upper_checkpoint=build_cdc_checkpoint({"p0": (1, 0)}),
        complete_through_upper=True,
    )

    assert batch.events == (event,)
    assert batch.duplicate_events_ignored == 1


def test_cdc_event_identity_conflict_fails_closed():
    first = _event("same", CDCOperation.UPDATE, 1, name="A")
    second = _event("same", CDCOperation.UPDATE, 1, name="B")

    with pytest.raises(CDCConflictError, match="event_id same"):
        normalize_cdc_batch(
            [first, second],
            upper_checkpoint=build_cdc_checkpoint({"p0": (1, 0)}),
            complete_through_upper=True,
        )


def test_cdc_shared_source_position_requires_provider_row_sequence():
    first = _event("e1", CDCOperation.INSERT, 10, customer_id=1)
    second = _event("e2", CDCOperation.INSERT, 10, customer_id=2)

    with pytest.raises(CDCOrderingError, match="share one canonical source position"):
        normalize_cdc_batch(
            [first, second],
            upper_checkpoint=build_cdc_checkpoint({"p0": (10, 0)}),
            complete_through_upper=True,
        )


def test_cdc_same_key_across_partitions_fails_closed():
    first = _event("e1", CDCOperation.UPDATE, 1, partition="p0")
    second = _event("e2", CDCOperation.UPDATE, 1, partition="p1")

    with pytest.raises(CDCOrderingError, match="multiple partitions"):
        normalize_cdc_batch(
            [first, second],
            upper_checkpoint=build_cdc_checkpoint({"p0": (1, 0), "p1": (1, 0)}),
            complete_through_upper=True,
        )


def test_cdc_window_requires_completeness_and_rejects_events_beyond_upper():
    event = _event("e2", CDCOperation.UPDATE, 2)

    with pytest.raises(CDCEvidenceError, match="completeness evidence"):
        normalize_cdc_batch(
            [event],
            upper_checkpoint=build_cdc_checkpoint({"p0": (2, 0)}),
            complete_through_upper=False,
        )

    with pytest.raises(CDCEvidenceError, match="beyond the frozen upper"):
        normalize_cdc_batch(
            [event],
            upper_checkpoint=build_cdc_checkpoint({"p0": (1, 0)}),
            complete_through_upper=True,
        )


def test_cdc_lower_checkpoint_filters_already_committed_overlap():
    old = _event("old", CDCOperation.UPDATE, 5)
    new = _event("new", CDCOperation.UPDATE, 6)
    batch = normalize_cdc_batch(
        [new, old],
        lower_checkpoint=build_cdc_checkpoint({"p0": (5, 0)}),
        upper_checkpoint=build_cdc_checkpoint({"p0": (6, 0)}),
        complete_through_upper=True,
    )

    assert [event.event_id for event in batch.events] == ["new"]
    assert batch.already_committed_events_ignored == 1


def test_cdc_checkpoint_advance_requires_target_and_reconciliation_gate():
    before = build_cdc_checkpoint({"p0": (5, 0)})
    after = build_cdc_checkpoint({"p0": (6, 0)})

    with pytest.raises(ValueError, match="cannot advance"):
        CDCCheckpointTransition(
            before=before,
            after=after,
            gate=StateCommitGate(
                target_committed=True,
                reconciliation_required=True,
                reconciliation_passed=False,
            ),
        )

    transition = CDCCheckpointTransition(
        before=before,
        after=after,
        gate=StateCommitGate(
            target_committed=True,
            reconciliation_required=True,
            reconciliation_passed=True,
        ),
    )
    assert transition.after == after


@pytest.mark.parametrize("strategy", [ApplyStrategy.UPSERT, ApplyStrategy.SCD1])
def test_cdc_current_state_handles_insert_update_delete_reinsert(strategy):
    events = [
        _event("i1", CDCOperation.INSERT, 1, name="A"),
        _event("u1", CDCOperation.UPDATE, 2, name="B"),
        _event("d1", CDCOperation.DELETE, 3, name="B"),
        _event("i2", CDCOperation.INSERT, 4, name="C"),
    ]
    batch = normalize_cdc_batch(
        events,
        upper_checkpoint=build_cdc_checkpoint({"p0": (4, 0)}),
        complete_through_upper=True,
    )

    result = apply_cdc_current_state(
        [],
        batch,
        merge_key=("customer_id",),
        strategy=strategy,
    )

    assert result.mutations.inserted == 2
    assert result.mutations.updated == 1
    assert result.mutations.deleted == 1
    assert result.rows[0]["name"] == "C"
    assert result.rows[0][CDC_PARTITION] == "p0"
    assert result.rows[0][CDC_POSITION] == (4, 0)


def test_cdc_bootstrap_row_requires_committed_lower_checkpoint_before_first_update():
    existing = [{"customer_id": 1, "name": "snapshot"}]
    event = _event("u6", CDCOperation.UPDATE, 6, name="cdc")

    unsafe = normalize_cdc_batch(
        [event],
        upper_checkpoint=build_cdc_checkpoint({"p0": (6, 0)}),
        complete_through_upper=True,
    )
    with pytest.raises(CDCOrderingError, match="no committed lower checkpoint"):
        apply_cdc_current_state(
            existing,
            unsafe,
            merge_key=("customer_id",),
            strategy=ApplyStrategy.UPSERT,
        )

    safe = normalize_cdc_batch(
        [event],
        lower_checkpoint=build_cdc_checkpoint({"p0": (5, 0)}),
        upper_checkpoint=build_cdc_checkpoint({"p0": (6, 0)}),
        complete_through_upper=True,
    )
    result = apply_cdc_current_state(
        existing,
        safe,
        merge_key=("customer_id",),
        strategy=ApplyStrategy.UPSERT,
    )
    assert result.rows[0]["name"] == "cdc"
    assert result.rows[0][CDC_POSITION] == (6, 0)


def test_cdc_stale_event_is_ignored_against_newer_target_position():
    existing = [
        {
            "customer_id": 1,
            "name": "newer",
            CDC_PARTITION: "p0",
            CDC_POSITION: (10, 0),
        }
    ]
    batch = normalize_cdc_batch(
        [_event("u9", CDCOperation.UPDATE, 9, name="older")],
        lower_checkpoint=build_cdc_checkpoint({"p0": (5, 0)}),
        upper_checkpoint=build_cdc_checkpoint({"p0": (9, 0)}),
        complete_through_upper=True,
    )
    result = apply_cdc_current_state(
        existing,
        batch,
        merge_key=("customer_id",),
        strategy=ApplyStrategy.SCD1,
    )

    assert result.rows[0]["name"] == "newer"
    assert result.stale_events_ignored == 1
    assert result.mutations.updated == 0


def test_cdc_delete_policy_can_ignore_or_fail():
    existing = [
        {
            "customer_id": 1,
            "name": "A",
            CDC_PARTITION: "p0",
            CDC_POSITION: (1, 0),
        }
    ]
    batch = normalize_cdc_batch(
        [_event("d2", CDCOperation.DELETE, 2, name="A")],
        lower_checkpoint=build_cdc_checkpoint({"p0": (1, 0)}),
        upper_checkpoint=build_cdc_checkpoint({"p0": (2, 0)}),
        complete_through_upper=True,
    )

    ignored = apply_cdc_current_state(
        existing,
        batch,
        merge_key=("customer_id",),
        strategy=ApplyStrategy.UPSERT,
        delete_action=CDCDeleteAction.IGNORE,
    )
    assert ignored.rows[0]["name"] == "A"
    assert ignored.delete_policy_events_ignored == 1

    with pytest.raises(CDCDeleteRejectedError, match="rejected by policy"):
        apply_cdc_current_state(
            existing,
            batch,
            merge_key=("customer_id",),
            strategy=ApplyStrategy.UPSERT,
            delete_action=CDCDeleteAction.ERROR,
        )


def test_cdc_exact_update_rerun_is_no_change_when_position_and_payload_match():
    existing = [
        {
            "customer_id": 1,
            "name": "A",
            CDC_PARTITION: "p0",
            CDC_POSITION: (2, 0),
        }
    ]
    batch = normalize_cdc_batch(
        [_event("u2", CDCOperation.UPDATE, 2, name="A")],
        upper_checkpoint=build_cdc_checkpoint({"p0": (2, 0)}),
        complete_through_upper=True,
    )
    result = apply_cdc_current_state(
        existing,
        batch,
        merge_key=("customer_id",),
        strategy=ApplyStrategy.UPSERT,
    )

    assert result.no_change_events == 1
    assert result.mutations.updated == 0
