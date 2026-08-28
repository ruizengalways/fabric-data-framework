"""Safe resume planning for Debezium CDC consumed from Kafka."""

from __future__ import annotations

from typing import Mapping

from pydantic import Field, model_validator

from ...capture.cdc import CDCCheckpoint, build_cdc_checkpoint
from ...config import FrozenModel
from .debezium_kafka import DebeziumKafkaAdapterError


class DebeziumKafkaResumeGapError(DebeziumKafkaAdapterError):
    """Raised when Kafka retention no longer covers the next unapplied event."""


class DebeziumKafkaPartitionResume(FrozenModel):
    partition: int = Field(ge=0)
    start_offset: int = Field(ge=0)
    upper_offset: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> "DebeziumKafkaPartitionResume":
        if self.start_offset > self.upper_offset + 1:
            raise ValueError("Kafka resume start cannot skip beyond upper + 1")
        return self

    @property
    def has_work(self) -> bool:
        return self.start_offset <= self.upper_offset


class DebeziumKafkaResumePlan(FrozenModel):
    """Provider seek ranges derived from framework downstream apply progress."""

    topic: str = Field(min_length=1)
    lower_checkpoint: CDCCheckpoint | None = None
    upper_checkpoint: CDCCheckpoint
    partitions: tuple[DebeziumKafkaPartitionResume, ...]

    @property
    def has_work(self) -> bool:
        return any(item.has_work for item in self.partitions)


def _parse_committed_offsets(
    topic: str,
    checkpoint: CDCCheckpoint | None,
) -> dict[int, int]:
    if checkpoint is None:
        return {}

    result: dict[int, int] = {}
    prefix = f"{topic}:"
    for position in checkpoint.positions:
        if not position.partition.startswith(prefix):
            raise DebeziumKafkaAdapterError(
                "committed CDC checkpoint contains a different provider topic"
            )
        partition_text = position.partition[len(prefix) :]
        try:
            partition = int(partition_text)
        except ValueError as exc:
            raise DebeziumKafkaAdapterError(
                f"invalid Kafka partition in CDC checkpoint: {position.partition}"
            ) from exc
        if partition < 0 or len(position.values) != 1:
            raise DebeziumKafkaAdapterError(
                "Debezium Kafka checkpoint requires one non-negative offset per partition"
            )
        result[partition] = position.values[0]
    return result


def _validate_provider_offsets(
    earliest_offsets: Mapping[int, int],
    latest_offsets: Mapping[int, int],
) -> set[int]:
    partitions = set(earliest_offsets)
    if not partitions or partitions != set(latest_offsets):
        raise DebeziumKafkaAdapterError(
            "Kafka earliest/latest offset evidence must cover the same non-empty partitions"
        )
    for partition in partitions:
        earliest = earliest_offsets[partition]
        latest = latest_offsets[partition]
        for label, value in (("partition", partition), ("earliest", earliest), ("latest", latest)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise DebeziumKafkaAdapterError(
                    f"Kafka {label} values must be non-negative integers"
                )
        if earliest > latest + 1:
            raise DebeziumKafkaAdapterError(
                "Kafka earliest offset cannot be beyond latest available offset + 1"
            )
    return partitions


def plan_debezium_kafka_resume(
    *,
    topic: str,
    committed_checkpoint: CDCCheckpoint | None,
    earliest_offsets: Mapping[int, int],
    latest_offsets: Mapping[int, int],
    requested_upper_offsets: Mapping[int, int] | None = None,
    allow_new_partitions: bool = False,
) -> DebeziumKafkaResumePlan:
    """Plan a source rewind/seek without trusting an external consumer cursor.

    ``latest_offsets`` are inclusive latest available record offsets after any Kafka
    client/API-specific conversion. ``committed_checkpoint`` is downstream semantic
    apply progress. External consumer-group progress may be ahead after downstream
    failure and therefore is intentionally not an input to this correctness decision.
    """

    if not topic:
        raise DebeziumKafkaAdapterError("topic must be non-empty")
    provider_partitions = _validate_provider_offsets(earliest_offsets, latest_offsets)

    upper_offsets = (
        dict(requested_upper_offsets)
        if requested_upper_offsets is not None
        else dict(latest_offsets)
    )
    if set(upper_offsets) != provider_partitions:
        raise DebeziumKafkaAdapterError(
            "requested upper offsets must cover exactly the provider partition set"
        )
    for partition, upper in upper_offsets.items():
        if not isinstance(upper, int) or isinstance(upper, bool) or upper < 0:
            raise DebeziumKafkaAdapterError("requested upper offsets must be non-negative integers")
        if upper > latest_offsets[partition]:
            raise DebeziumKafkaAdapterError(
                f"requested upper offset for partition {partition} exceeds provider latest"
            )

    committed = _parse_committed_offsets(topic, committed_checkpoint)
    committed_partitions = set(committed)
    if not committed_partitions.issubset(provider_partitions):
        raise DebeziumKafkaResumeGapError(
            "provider no longer exposes every partition in committed CDC state"
        )
    new_partitions = provider_partitions - committed_partitions
    if committed_checkpoint is not None and new_partitions and not allow_new_partitions:
        raise DebeziumKafkaAdapterError(
            "Kafka partition set changed after CDC state was committed; "
            "explicit repartition handling is required"
        )

    partition_plans: list[DebeziumKafkaPartitionResume] = []
    normalized_upper: dict[str, tuple[int, ...]] = {}
    for partition in sorted(provider_partitions):
        earliest = earliest_offsets[partition]
        upper = upper_offsets[partition]
        previous = committed.get(partition)
        if previous is not None:
            next_required = previous + 1
            if earliest > next_required:
                raise DebeziumKafkaResumeGapError(
                    f"Kafka retention gap for partition {partition}: "
                    f"earliest={earliest}, next_required={next_required}"
                )
            if upper < previous:
                raise DebeziumKafkaAdapterError(
                    f"requested upper offset regresses committed partition {partition}"
                )
            start = max(earliest, next_required)
        else:
            start = earliest

        partition_plans.append(
            DebeziumKafkaPartitionResume(
                partition=partition,
                start_offset=start,
                upper_offset=upper,
            )
        )
        normalized_upper[f"{topic}:{partition}"] = (upper,)

    return DebeziumKafkaResumePlan(
        topic=topic,
        lower_checkpoint=committed_checkpoint,
        upper_checkpoint=build_cdc_checkpoint(normalized_upper),
        partitions=tuple(partition_plans),
    )


__all__ = [
    "DebeziumKafkaPartitionResume",
    "DebeziumKafkaResumeGapError",
    "DebeziumKafkaResumePlan",
    "plan_debezium_kafka_resume",
]
