from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fabric_data_framework.apply.scd2 import (
    IS_CURRENT,
    VALID_FROM,
    VALID_TO,
    LateArrivingRecordError,
    apply_scd2,
)


def dt(day: int):
    return datetime(2026, 8, day, 10, tzinfo=timezone.utc)


def row(customer_id: str, name: str, day: int):
    return {"customer_id": customer_id, "name": name, "modified_at": dt(day)}


def test_scd2_insert_change_unchanged_and_idempotent_rerun():
    run1 = apply_scd2(
        [],
        [row("C001", "Alice", 1)],
        business_key=("customer_id",),
        tracked_columns=("name",),
        effective_time_column="modified_at",
        dataset_run_id=uuid4(),
    )
    assert run1.mutations.inserted == 1
    assert run1.rows[0][IS_CURRENT] is True

    run2 = apply_scd2(
        run1.rows,
        [row("C001", "Alice", 2), row("C001", "Alice Smith", 3)],
        business_key=("customer_id",),
        tracked_columns=("name",),
        effective_time_column="modified_at",
        dataset_run_id=uuid4(),
    )
    assert run2.mutations.updated == 1
    assert len(run2.rows) == 2
    assert run2.rows[0][VALID_TO] == dt(3)
    assert run2.rows[1][VALID_FROM] == dt(3)
    assert run2.rows[1][IS_CURRENT] is True

    rerun = apply_scd2(
        run2.rows,
        [row("C001", "Alice Smith", 3)],
        business_key=("customer_id",),
        tracked_columns=("name",),
        effective_time_column="modified_at",
        dataset_run_id=uuid4(),
    )
    assert rerun.rows == run2.rows
    assert rerun.mutations.inserted == 0
    assert rerun.mutations.updated == 0


def test_late_arriving_record_is_explicitly_rejected_until_policy_is_added():
    initial = apply_scd2(
        [],
        [row("C001", "Alice", 3)],
        business_key=("customer_id",),
        tracked_columns=("name",),
        effective_time_column="modified_at",
        dataset_run_id=uuid4(),
    )
    with pytest.raises(LateArrivingRecordError):
        apply_scd2(
            initial.rows,
            [row("C001", "Older Alice", 2)],
            business_key=("customer_id",),
            tracked_columns=("name",),
            effective_time_column="modified_at",
            dataset_run_id=uuid4(),
        )
