from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fabric_data_framework.apply.cdc_scd2 import (
    CDC_CLOSED_PARTITION,
    CDC_CLOSED_POSITION,
    apply_cdc_scd2,
)
from fabric_data_framework.apply.scd2 import IS_CURRENT
from fabric_data_framework.capture.cdc import (
    CDCNormalizedBatch,
    CDCOperation,
    CDCOrderingError,
    CDCEvent,
    CDCSourcePosition,
    build_cdc_checkpoint,
)


def _time(hour: int) -> datetime:
    return datetime(2026, 9, 11, hour, tzinfo=timezone.utc)


def _event(position: int, operation: CDCOperation, *, partition: str = "p0") -> CDCEvent:
    return CDCEvent(
        event_id=f"{partition}-{position}-{operation.value}",
        operation=operation,
        key={"customer_id": "C1"},
        position=CDCSourcePosition(partition=partition, values=(position,)),
        after=(
            {"customer_id": "C1", "email": f"v{position}@example.test"}
            if operation is not CDCOperation.DELETE
            else None
        ),
        event_time=_time(9 + position),
    )


def _batch(event: CDCEvent, *, lower: int | None = None) -> CDCNormalizedBatch:
    partition = event.position.partition
    return CDCNormalizedBatch(
        events=(event,),
        lower_checkpoint=(
            build_cdc_checkpoint({partition: (lower,)}) if lower is not None else None
        ),
        upper_checkpoint=build_cdc_checkpoint({partition: event.position.values}),
    )


def _deleted_history():
    inserted = apply_cdc_scd2(
        (),
        _batch(_event(1, CDCOperation.INSERT)),
        business_key=("customer_id",),
        tracked_columns=("email",),
        dataset_run_id=uuid4(),
    )
    deleted = apply_cdc_scd2(
        inserted.rows,
        _batch(_event(3, CDCOperation.DELETE)),
        business_key=("customer_id",),
        tracked_columns=("email",),
        dataset_run_id=uuid4(),
    )
    assert not any(row[IS_CURRENT] for row in deleted.rows)
    return deleted.rows


def test_stale_and_equal_events_cannot_resurrect_deleted_key():
    history = _deleted_history()

    stale = apply_cdc_scd2(
        history,
        _batch(_event(2, CDCOperation.UPDATE)),
        business_key=("customer_id",),
        tracked_columns=("email",),
        dataset_run_id=uuid4(),
    )
    assert stale.stale_events_ignored == 1
    assert not any(row[IS_CURRENT] for row in stale.rows)

    equal = apply_cdc_scd2(
        history,
        _batch(_event(3, CDCOperation.UPDATE)),
        business_key=("customer_id",),
        tracked_columns=("email",),
        dataset_run_id=uuid4(),
    )
    assert equal.stale_events_ignored == 1
    assert not any(row[IS_CURRENT] for row in equal.rows)


def test_strictly_newer_event_can_reinsert_after_delete():
    result = apply_cdc_scd2(
        _deleted_history(),
        _batch(_event(4, CDCOperation.INSERT)),
        business_key=("customer_id",),
        tracked_columns=("email",),
        dataset_run_id=uuid4(),
    )

    current = [row for row in result.rows if row[IS_CURRENT]]
    assert len(current) == 1
    assert current[0]["email"] == "v4@example.test"
    assert result.mutations.inserted == 1


def test_closed_history_partition_mismatch_fails_closed():
    history = _deleted_history()
    with pytest.raises(CDCOrderingError, match="moved across source partitions"):
        apply_cdc_scd2(
            history,
            _batch(_event(4, CDCOperation.INSERT, partition="other")),
            business_key=("customer_id",),
            tracked_columns=("email",),
            dataset_run_id=uuid4(),
        )


def test_history_without_position_evidence_requires_trusted_lower_checkpoint():
    history = tuple(
        {
            key: value
            for key, value in row.items()
            if key not in {CDC_CLOSED_PARTITION, CDC_CLOSED_POSITION}
        }
        for row in _deleted_history()
    )

    with pytest.raises(CDCOrderingError, match="no committed lower checkpoint"):
        apply_cdc_scd2(
            history,
            _batch(_event(4, CDCOperation.INSERT)),
            business_key=("customer_id",),
            tracked_columns=("email",),
            dataset_run_id=uuid4(),
        )

    result = apply_cdc_scd2(
        history,
        _batch(_event(4, CDCOperation.INSERT), lower=3),
        business_key=("customer_id",),
        tracked_columns=("email",),
        dataset_run_id=uuid4(),
    )
    assert any(row[IS_CURRENT] for row in result.rows)
