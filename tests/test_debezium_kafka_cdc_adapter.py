from datetime import datetime, timezone

import pytest

from fabric_data_framework.adapters.cdc import (
    DebeziumKafkaAdapterError,
    DebeziumKafkaRecord,
    DebeziumKafkaResumeGapError,
    DebeziumSnapshotReadPolicy,
    normalize_debezium_kafka_batch,
    plan_debezium_kafka_resume,
)
from fabric_data_framework.capture.cdc import CDCOperation, build_cdc_checkpoint


TOPIC = "dbserver1.inventory.customers"


def _record(offset: int, *, op: str, key=None, before=None, after=None, value=True):
    if value is None:
        payload = None
    else:
        payload = {
            "payload": {
                "before": before,
                "after": after,
                "op": op,
                "ts_ms": 1_787_958_000_000 + offset,
                "source": {"db": "inventory", "table": "customers", "lsn": offset * 10},
                "transaction": {"id": "tx-1"},
            }
        }
    return DebeziumKafkaRecord(
        topic=TOPIC,
        partition=0,
        offset=offset,
        key={"payload": key or {"id": 1}},
        value=payload,
        timestamp_ms=1_787_958_000_000 + offset,
    )


def test_debezium_kafka_maps_create_update_delete_to_canonical_cdc():
    result = normalize_debezium_kafka_batch(
        (
            _record(101, op="c", after={"id": 1, "name": "A"}),
            _record(
                102,
                op="u",
                before={"id": 1, "name": "A"},
                after={"id": 1, "name": "B"},
            ),
            _record(103, op="d", before={"id": 1, "name": "B"}),
        ),
        topic=TOPIC,
        lower_offsets={0: 100},
        upper_offsets={0: 103},
        complete_through_upper=True,
    )

    batch = result.normalized_batch
    assert [event.operation for event in batch.events] == [
        CDCOperation.INSERT,
        CDCOperation.UPDATE,
        CDCOperation.DELETE,
    ]
    assert [event.position.values for event in batch.events] == [(101,), (102,), (103,)]
    assert all(event.position.partition == f"{TOPIC}:0" for event in batch.events)
    assert batch.events[1].transaction_id == "tx-1"
    assert batch.events[1].metadata["source"]["lsn"] == 1020
    assert batch.events[1].event_time == datetime.fromtimestamp(
        (1_787_958_000_000 + 102) / 1000,
        tz=timezone.utc,
    )


def test_debezium_tombstone_is_transport_cleanup_not_second_delete():
    result = normalize_debezium_kafka_batch(
        (_record(104, op="d", value=None),),
        topic=TOPIC,
        lower_offsets={0: 103},
        upper_offsets={0: 104},
        complete_through_upper=True,
    )

    assert result.normalized_batch.events == ()
    assert result.tombstones_ignored == 1
    assert result.provider_records_seen == 1


def test_debezium_snapshot_read_fails_closed_unless_explicitly_mapped():
    record = _record(10, op="r", after={"id": 1, "name": "snapshot"})

    with pytest.raises(DebeziumKafkaAdapterError, match="snapshot-read"):
        normalize_debezium_kafka_batch(
            (record,),
            topic=TOPIC,
            upper_offsets={0: 10},
            complete_through_upper=True,
        )

    result = normalize_debezium_kafka_batch(
        (record,),
        topic=TOPIC,
        upper_offsets={0: 10},
        complete_through_upper=True,
        snapshot_read_policy=DebeziumSnapshotReadPolicy.AS_INSERT,
    )
    assert result.snapshot_reads_mapped == 1
    assert result.normalized_batch.events[0].operation is CDCOperation.INSERT


def test_debezium_adapter_requires_explicit_key_and_frozen_topic_window():
    missing_key = DebeziumKafkaRecord(
        topic=TOPIC,
        partition=0,
        offset=1,
        key=None,
        value={"payload": {"before": None, "after": {"id": 1}, "op": "c"}},
    )
    with pytest.raises(DebeziumKafkaAdapterError, match="explicit key"):
        normalize_debezium_kafka_batch(
            (missing_key,),
            topic=TOPIC,
            upper_offsets={0: 1},
            complete_through_upper=True,
        )

    with pytest.raises(DebeziumKafkaAdapterError, match="exceeds frozen upper"):
        normalize_debezium_kafka_batch(
            (_record(2, op="c", after={"id": 1}),),
            topic=TOPIC,
            upper_offsets={0: 1},
            complete_through_upper=True,
        )

    wrong_topic = _record(1, op="c", after={"id": 1}).model_copy(
        update={"topic": "another.topic"}
    )
    with pytest.raises(DebeziumKafkaAdapterError, match="mixed Debezium topics"):
        normalize_debezium_kafka_batch(
            (wrong_topic,),
            topic=TOPIC,
            upper_offsets={0: 1},
            complete_through_upper=True,
        )


def test_resume_uses_framework_apply_checkpoint_not_external_consumer_cursor():
    committed = build_cdc_checkpoint({f"{TOPIC}:0": (100,)})
    plan = plan_debezium_kafka_resume(
        topic=TOPIC,
        committed_checkpoint=committed,
        earliest_offsets={0: 90},
        latest_offsets={0: 120},
    )

    assert plan.partitions[0].start_offset == 101
    assert plan.partitions[0].upper_offset == 120
    assert plan.lower_checkpoint == committed
    assert plan.upper_checkpoint.position_for(f"{TOPIC}:0") == (120,)


def test_resume_fails_when_kafka_retention_lost_next_unapplied_offset():
    committed = build_cdc_checkpoint({f"{TOPIC}:0": (100,)})
    with pytest.raises(DebeziumKafkaResumeGapError, match="retention gap"):
        plan_debezium_kafka_resume(
            topic=TOPIC,
            committed_checkpoint=committed,
            earliest_offsets={0: 102},
            latest_offsets={0: 120},
        )


def test_resume_rejects_partition_change_by_default_but_can_make_it_explicit():
    committed = build_cdc_checkpoint({f"{TOPIC}:0": (100,)})
    with pytest.raises(DebeziumKafkaAdapterError, match="partition set changed"):
        plan_debezium_kafka_resume(
            topic=TOPIC,
            committed_checkpoint=committed,
            earliest_offsets={0: 90, 1: 0},
            latest_offsets={0: 120, 1: 5},
        )

    plan = plan_debezium_kafka_resume(
        topic=TOPIC,
        committed_checkpoint=committed,
        earliest_offsets={0: 90, 1: 0},
        latest_offsets={0: 120, 1: 5},
        allow_new_partitions=True,
    )
    assert [(item.partition, item.start_offset) for item in plan.partitions] == [
        (0, 101),
        (1, 0),
    ]


def test_resume_rejects_requested_upper_regression_or_future_offset():
    committed = build_cdc_checkpoint({f"{TOPIC}:0": (100,)})
    with pytest.raises(DebeziumKafkaAdapterError, match="regresses committed"):
        plan_debezium_kafka_resume(
            topic=TOPIC,
            committed_checkpoint=committed,
            earliest_offsets={0: 90},
            latest_offsets={0: 120},
            requested_upper_offsets={0: 99},
        )

    with pytest.raises(DebeziumKafkaAdapterError, match="exceeds provider latest"):
        plan_debezium_kafka_resume(
            topic=TOPIC,
            committed_checkpoint=committed,
            earliest_offsets={0: 90},
            latest_offsets={0: 120},
            requested_upper_offsets={0: 121},
        )
