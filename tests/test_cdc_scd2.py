from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from fabric_data_framework.apply.cdc import CDC_PARTITION, CDC_POSITION
from fabric_data_framework.apply.cdc_scd2 import (
    CDC_CLOSED_POSITION,
    CDCSCD2ConflictError,
    CDCSCD2LateArrivingError,
    apply_cdc_scd2,
)
from fabric_data_framework.capture.cdc import (
    CDCEvent,
    CDCOperation,
    CDCSourcePosition,
    build_cdc_checkpoint,
    normalize_cdc_batch,
)
from fabric_data_framework.scd2 import (
    IS_CURRENT,
    RECORD_HASH,
    SOURCE_DATASET_RUN_ID,
    VALID_FROM,
    VALID_TO,
)


BASE_TIME = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


def _event(
    event_id: str,
    operation: CDCOperation,
    position: int,
    *,
    name: str | None = None,
    event_time: datetime | None = None,
) -> CDCEvent:
    after = None
    before = None
    if operation is CDCOperation.DELETE:
        before = {"customer_id": 1, "name": name or "before-delete"}
    else:
        after = {"customer_id": 1, "name": name or event_id}
    return CDCEvent(
        event_id=event_id,
        operation=operation,
        key={"customer_id": 1},
        position=CDCSourcePosition(partition="p0", values=(position, 0)),
        before=before,
        after=after,
        event_time=event_time or BASE_TIME + timedelta(seconds=position),
    )


def _batch(events, *, lower=None, upper=None):
    upper_value = upper if upper is not None else max(event.position.values[0] for event in events)
    return normalize_cdc_batch(
        events,
        lower_checkpoint=(
            build_cdc_checkpoint({"p0": (lower, 0)}) if lower is not None else None
        ),
        upper_checkpoint=build_cdc_checkpoint({"p0": (upper_value, 0)}),
        complete_through_upper=True,
    )


def test_cdc_scd2_insert_update_delete_reinsert_preserves_history():
    batch = _batch(
        [
            _event("i1", CDCOperation.INSERT, 1, name="A"),
            _event("u2", CDCOperation.UPDATE, 2, name="B"),
            _event("d3", CDCOperation.DELETE, 3, name="B"),
            _event("i4", CDCOperation.INSERT, 4, name="C"),
        ]
    )
    result = apply_cdc_scd2(
        [],
        batch,
        business_key=("customer_id",),
        tracked_columns=("name",),
        dataset_run_id=uuid4(),
    )

    assert result.mutations.inserted == 2
    assert result.mutations.updated == 1
    assert result.mutations.deleted == 1
    assert len(result.rows) == 3
    current = [row for row in result.rows if row[IS_CURRENT]]
    assert len(current) == 1
    assert current[0]["name"] == "C"
    assert current[0][CDC_POSITION] == (4, 0)
    closed = [row for row in result.rows if not row[IS_CURRENT]]
    assert [row["name"] for row in closed] == ["A", "B"]
    assert closed[1][CDC_CLOSED_POSITION] == (3, 0)


def test_cdc_scd2_source_position_disambiguates_equal_event_time():
    same_time = BASE_TIME
    batch = _batch(
        [
            _event("i1", CDCOperation.INSERT, 1, name="A", event_time=same_time),
            _event("u2", CDCOperation.UPDATE, 2, name="B", event_time=same_time),
        ]
    )
    result = apply_cdc_scd2(
        [],
        batch,
        business_key=("customer_id",),
        tracked_columns=("name",),
        dataset_run_id=uuid4(),
    )

    assert len(result.rows) == 2
    assert result.rows[0][VALID_FROM] == same_time
    assert result.rows[0][VALID_TO] == same_time
    assert result.rows[0][IS_CURRENT] is False
    assert result.rows[1][VALID_FROM] == same_time
    assert result.rows[1][IS_CURRENT] is True
    assert result.rows[1]["name"] == "B"


def test_cdc_scd2_rejects_retroactive_valid_time_even_when_source_position_is_newer():
    first = _batch([_event("i10", CDCOperation.INSERT, 10, name="A")])
    initial = apply_cdc_scd2(
        [],
        first,
        business_key=("customer_id",),
        tracked_columns=("name",),
        dataset_run_id=uuid4(),
    )
    late = _batch(
        [
            _event(
                "u11",
                CDCOperation.UPDATE,
                11,
                name="B",
                event_time=BASE_TIME + timedelta(seconds=5),
            )
        ],
        lower=10,
    )

    with pytest.raises(CDCSCD2LateArrivingError, match="retroactive history"):
        apply_cdc_scd2(
            initial.rows,
            late,
            business_key=("customer_id",),
            tracked_columns=("name",),
            dataset_run_id=uuid4(),
        )


def test_cdc_scd2_bootstrap_history_can_enter_cdc_only_with_committed_lower_checkpoint():
    bootstrap = [
        {
            "customer_id": 1,
            "name": "snapshot",
            VALID_FROM: BASE_TIME,
            VALID_TO: None,
            IS_CURRENT: True,
            RECORD_HASH: "bootstrap-hash",
            SOURCE_DATASET_RUN_ID: str(uuid4()),
        }
    ]
    event = _event("u6", CDCOperation.UPDATE, 6, name="cdc", event_time=BASE_TIME + timedelta(seconds=6))

    unsafe = _batch([event])
    with pytest.raises(Exception, match="no committed lower checkpoint"):
        apply_cdc_scd2(
            bootstrap,
            unsafe,
            business_key=("customer_id",),
            tracked_columns=("name",),
            dataset_run_id=uuid4(),
        )

    safe = _batch([event], lower=5)
    result = apply_cdc_scd2(
        bootstrap,
        safe,
        business_key=("customer_id",),
        tracked_columns=("name",),
        dataset_run_id=uuid4(),
    )
    assert len(result.rows) == 2
    assert [row for row in result.rows if row[IS_CURRENT]][0]["name"] == "cdc"


def test_cdc_scd2_equal_position_conflict_fails_closed():
    existing = [
        {
            "customer_id": 1,
            "name": "A",
            VALID_FROM: BASE_TIME,
            VALID_TO: None,
            IS_CURRENT: True,
            RECORD_HASH: "not-the-new-hash",
            SOURCE_DATASET_RUN_ID: str(uuid4()),
            CDC_PARTITION: "p0",
            CDC_POSITION: (2, 0),
        }
    ]
    batch = _batch(
        [_event("u2", CDCOperation.UPDATE, 2, name="B", event_time=BASE_TIME)]
    )

    with pytest.raises(CDCSCD2ConflictError, match="equal source position"):
        apply_cdc_scd2(
            existing,
            batch,
            business_key=("customer_id",),
            tracked_columns=("name",),
            dataset_run_id=uuid4(),
        )


def test_cdc_scd2_unchanged_event_advances_source_position_without_new_history_version():
    first = _batch([_event("i1", CDCOperation.INSERT, 1, name="A")])
    initial = apply_cdc_scd2(
        [],
        first,
        business_key=("customer_id",),
        tracked_columns=("name",),
        dataset_run_id=uuid4(),
    )
    second = _batch([_event("u2", CDCOperation.UPDATE, 2, name="A")], lower=1)
    result = apply_cdc_scd2(
        initial.rows,
        second,
        business_key=("customer_id",),
        tracked_columns=("name",),
        dataset_run_id=uuid4(),
    )

    assert len(result.rows) == 1
    assert result.rows[0][CDC_POSITION] == (2, 0)
    assert result.no_change_events == 1
    assert result.mutations.updated == 0
