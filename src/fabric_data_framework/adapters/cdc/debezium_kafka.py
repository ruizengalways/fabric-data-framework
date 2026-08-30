"""Debezium-on-Kafka CDC provider adapter.

This module translates Kafka Connect / Debezium envelopes into the provider-neutral
CDC contracts in :mod:`fabric_data_framework.capture.cdc`. Kafka topic/partition/
offset is the canonical physical ordering coordinate. Database-native LSN/binlog
fields remain provider metadata only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence

from pydantic import Field

from ...capture.cdc import (
    CDCCheckpoint,
    CDCContractError,
    CDCEvent,
    CDCNormalizedBatch,
    CDCOperation,
    CDCSourcePosition,
    build_cdc_checkpoint,
    normalize_cdc_batch,
)
from fabric_data_framework.contracts.base import FrozenModel


class DebeziumKafkaAdapterError(CDCContractError):
    """Raised when a Debezium/Kafka record cannot be normalized safely."""


class DebeziumSnapshotReadPolicy(str, Enum):
    ERROR = "ERROR"
    AS_INSERT = "AS_INSERT"


class DebeziumKafkaRecord(FrozenModel):
    """Minimal Kafka record evidence required by the adapter."""

    topic: str = Field(min_length=1)
    partition: int = Field(ge=0)
    offset: int = Field(ge=0)
    key: dict[str, Any] | None
    value: dict[str, Any] | None
    timestamp_ms: int | None = Field(default=None, ge=0)


class DebeziumKafkaBatchResult(FrozenModel):
    """Canonical CDC batch plus provider-only accounting evidence."""

    normalized_batch: CDCNormalizedBatch
    provider_records_seen: int = Field(ge=0)
    tombstones_ignored: int = Field(ge=0)
    snapshot_reads_mapped: int = Field(ge=0)


def _unwrap_connect_payload(value: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = value.get("payload")
    if isinstance(payload, Mapping):
        return payload
    return value


def _record_partition(topic: str, partition: int) -> str:
    return f"{topic}:{partition}"


def _checkpoint_from_offsets(
    topic: str,
    offsets: Mapping[int, int],
) -> CDCCheckpoint:
    if not offsets:
        raise DebeziumKafkaAdapterError("Debezium Kafka checkpoint requires partitions")
    normalized: dict[str, tuple[int, ...]] = {}
    for partition, offset in offsets.items():
        if not isinstance(partition, int) or isinstance(partition, bool) or partition < 0:
            raise DebeziumKafkaAdapterError("Kafka partition values must be non-negative integers")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise DebeziumKafkaAdapterError("Kafka offset values must be non-negative integers")
        normalized[_record_partition(topic, partition)] = (offset,)
    return build_cdc_checkpoint(normalized)


def _mapping_or_none(value: Any, field_name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise DebeziumKafkaAdapterError(
            f"Debezium {field_name} payload must be an object or null"
        )
    return dict(value)


def _event_time(envelope: Mapping[str, Any], record: DebeziumKafkaRecord) -> datetime | None:
    value = envelope.get("ts_ms")
    if value is None:
        value = record.timestamp_ms
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DebeziumKafkaAdapterError("Debezium ts_ms must be a non-negative integer")
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def _transaction_id(envelope: Mapping[str, Any]) -> str | None:
    transaction = envelope.get("transaction")
    if transaction is None:
        return None
    if isinstance(transaction, Mapping):
        value = transaction.get("id")
        return str(value) if value is not None else None
    if isinstance(transaction, str):
        return transaction
    raise DebeziumKafkaAdapterError("Debezium transaction metadata must be an object/string")


def _normalize_key(record: DebeziumKafkaRecord) -> dict[str, Any]:
    if record.key is None:
        raise DebeziumKafkaAdapterError(
            "Debezium Kafka record requires an explicit key; adapter will not infer business key"
        )
    raw_key = _unwrap_connect_payload(record.key)
    key = dict(raw_key)
    if not key:
        raise DebeziumKafkaAdapterError("Debezium Kafka record key cannot be empty")
    return key


def _validate_record_window(
    record: DebeziumKafkaRecord,
    *,
    topic: str,
    upper_offsets: Mapping[int, int],
) -> None:
    if record.topic != topic:
        raise DebeziumKafkaAdapterError(
            f"mixed Debezium topics are not allowed for one dataset batch: {record.topic}"
        )
    upper = upper_offsets.get(record.partition)
    if upper is None:
        raise DebeziumKafkaAdapterError(
            f"Kafka partition {record.partition} is absent from upper checkpoint"
        )
    if record.offset > upper:
        raise DebeziumKafkaAdapterError(
            f"Kafka record offset {record.offset} exceeds frozen upper offset {upper}"
        )


def _normalize_record(
    record: DebeziumKafkaRecord,
    *,
    snapshot_read_policy: DebeziumSnapshotReadPolicy,
) -> tuple[CDCEvent | None, bool]:
    if record.value is None:
        # Debezium can emit a Kafka tombstone after a DELETE. It is transport cleanup,
        # not a second business DELETE.
        return None, False

    envelope = _unwrap_connect_payload(record.value)
    op = envelope.get("op")
    if op not in {"c", "u", "d", "r"}:
        raise DebeziumKafkaAdapterError(f"unsupported Debezium operation: {op!r}")

    snapshot_read = op == "r"
    if snapshot_read and snapshot_read_policy is DebeziumSnapshotReadPolicy.ERROR:
        raise DebeziumKafkaAdapterError(
            "Debezium snapshot-read event is not accepted in CDC mode by default; "
            "use the framework snapshot/bootstrap contract or explicitly map it"
        )

    operation = {
        "c": CDCOperation.INSERT,
        "u": CDCOperation.UPDATE,
        "d": CDCOperation.DELETE,
        "r": CDCOperation.INSERT,
    }[op]

    before = _mapping_or_none(envelope.get("before"), "before")
    after = _mapping_or_none(envelope.get("after"), "after")
    key = _normalize_key(record)

    source = envelope.get("source")
    if source is not None and not isinstance(source, Mapping):
        raise DebeziumKafkaAdapterError("Debezium source metadata must be an object")

    metadata: dict[str, Any] = {
        "provider": "debezium_kafka",
        "debezium_op": op,
        "topic": record.topic,
        "kafka_partition": record.partition,
        "kafka_offset": record.offset,
    }
    if source is not None:
        metadata["source"] = dict(source)

    return (
        CDCEvent(
            event_id=f"{record.topic}:{record.partition}:{record.offset}",
            operation=operation,
            key=key,
            position=CDCSourcePosition(
                partition=_record_partition(record.topic, record.partition),
                values=(record.offset,),
            ),
            before=before,
            after=after,
            event_time=_event_time(envelope, record),
            transaction_id=_transaction_id(envelope),
            metadata=metadata,
        ),
        snapshot_read,
    )


def normalize_debezium_kafka_batch(
    records: Sequence[DebeziumKafkaRecord],
    *,
    topic: str,
    upper_offsets: Mapping[int, int],
    complete_through_upper: bool,
    lower_offsets: Mapping[int, int] | None = None,
    snapshot_read_policy: DebeziumSnapshotReadPolicy = DebeziumSnapshotReadPolicy.ERROR,
) -> DebeziumKafkaBatchResult:
    """Translate one frozen Debezium/Kafka window into canonical CDC semantics."""

    if not topic:
        raise DebeziumKafkaAdapterError("topic must be non-empty")

    upper_checkpoint = _checkpoint_from_offsets(topic, upper_offsets)
    lower_checkpoint = (
        _checkpoint_from_offsets(topic, lower_offsets)
        if lower_offsets is not None
        else None
    )

    events: list[CDCEvent] = []
    tombstones_ignored = 0
    snapshot_reads_mapped = 0
    for record in records:
        _validate_record_window(record, topic=topic, upper_offsets=upper_offsets)
        event, snapshot_read = _normalize_record(
            record,
            snapshot_read_policy=snapshot_read_policy,
        )
        if event is None:
            tombstones_ignored += 1
            continue
        if snapshot_read:
            snapshot_reads_mapped += 1
        events.append(event)

    normalized = normalize_cdc_batch(
        events,
        upper_checkpoint=upper_checkpoint,
        lower_checkpoint=lower_checkpoint,
        complete_through_upper=complete_through_upper,
    )
    return DebeziumKafkaBatchResult(
        normalized_batch=normalized,
        provider_records_seen=len(records),
        tombstones_ignored=tombstones_ignored,
        snapshot_reads_mapped=snapshot_reads_mapped,
    )


__all__ = [
    "DebeziumKafkaAdapterError",
    "DebeziumKafkaBatchResult",
    "DebeziumKafkaRecord",
    "DebeziumSnapshotReadPolicy",
    "normalize_debezium_kafka_batch",
]
