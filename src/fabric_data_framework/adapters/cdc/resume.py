"""Safe resume and Kafka cursor coordination for Debezium CDC.

The framework downstream checkpoint is the semantic source of truth. Kafka
consumer-group offsets are transport cursors only: they may be ahead after a target
failure or behind after a consumer rebalance/restart. A consumer must therefore seek
to the framework-derived next offset before replay and may only commit the provider
cursor after downstream state has been durably committed.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping

from pydantic import Field, model_validator

from ...capture.cdc import CDCCheckpoint, build_cdc_checkpoint
from fabric_data_framework.contracts.base import FrozenModel
from .debezium_kafka import DebeziumKafkaAdapterError


class DebeziumKafkaResumeGapError(DebeziumKafkaAdapterError):
    """Raised when Kafka retention no longer covers the next unapplied event."""


class KafkaCursorRelation(str, Enum):
    """Relationship of a consumer-group next offset to framework-required next offset."""

    MISSING = "MISSING"
    BEHIND = "BEHIND"
    ALIGNED = "ALIGNED"
    AHEAD = "AHEAD"


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

    @property
    def provider_commit_next_offset(self) -> int:
        """Kafka committed offsets represent the next record to consume."""

        return self.upper_offset + 1


class DebeziumKafkaResumePlan(FrozenModel):
    """Provider seek ranges derived from framework downstream apply progress."""

    topic: str = Field(min_length=1)
    lower_checkpoint: CDCCheckpoint | None = None
    upper_checkpoint: CDCCheckpoint
    partitions: tuple[DebeziumKafkaPartitionResume, ...]

    @property
    def has_work(self) -> bool:
        return any(item.has_work for item in self.partitions)

    @property
    def provider_commit_next_offsets(self) -> dict[int, int]:
        """Offsets safe to commit only after the framework upper checkpoint commits."""

        return {
            item.partition: item.provider_commit_next_offset
            for item in self.partitions
        }


class DebeziumKafkaPartitionCursorAlignment(FrozenModel):
    partition: int = Field(ge=0)
    framework_next_offset: int = Field(ge=0)
    consumer_group_next_offset: int | None = Field(default=None, ge=0)
    relation: KafkaCursorRelation
    seek_required: bool

    @model_validator(mode="after")
    def validate_relation(self) -> "DebeziumKafkaPartitionCursorAlignment":
        current = self.consumer_group_next_offset
        desired = self.framework_next_offset
        expected = (
            KafkaCursorRelation.MISSING
            if current is None
            else KafkaCursorRelation.BEHIND
            if current < desired
            else KafkaCursorRelation.AHEAD
            if current > desired
            else KafkaCursorRelation.ALIGNED
        )
        if self.relation is not expected:
            raise ValueError("Kafka cursor relation does not match supplied offsets")
        if self.seek_required != (expected is not KafkaCursorRelation.ALIGNED):
            raise ValueError("seek_required must be true unless provider cursor is aligned")
        return self


class DebeziumKafkaCursorCoordinationPlan(FrozenModel):
    """Transport actions surrounding one bounded downstream-safe Kafka replay."""

    resume: DebeziumKafkaResumePlan
    alignments: tuple[DebeziumKafkaPartitionCursorAlignment, ...]

    @property
    def seek_offsets(self) -> dict[int, int]:
        """Explicit seeks required before reading the bounded batch."""

        return {
            item.partition: item.framework_next_offset
            for item in self.alignments
            if item.seek_required
        }

    @property
    def commit_next_offsets_after_downstream_success(self) -> dict[int, int]:
        """Provider cursor values that may be committed after framework state success."""

        return self.resume.provider_commit_next_offsets


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


def plan_debezium_kafka_cursor_coordination(
    *,
    topic: str,
    committed_checkpoint: CDCCheckpoint | None,
    earliest_offsets: Mapping[int, int],
    latest_offsets: Mapping[int, int],
    consumer_group_next_offsets: Mapping[int, int],
    requested_upper_offsets: Mapping[int, int] | None = None,
    allow_new_partitions: bool = False,
) -> DebeziumKafkaCursorCoordinationPlan:
    """Plan provider seeks and deferred consumer-group commits around a safe replay.

    Kafka group offsets use Kafka's normal *next offset to consume* convention. They
    are observed for transport alignment only; they never override framework apply
    progress. An ahead cursor is rewound, a behind cursor is advanced by explicit
    seek, and a missing cursor is initialized at the framework-required position.

    The returned ``commit_next_offsets_after_downstream_success`` must not be applied
    until the target operation, reconciliation, and framework CDC checkpoint commit
    have all succeeded.
    """

    resume = plan_debezium_kafka_resume(
        topic=topic,
        committed_checkpoint=committed_checkpoint,
        earliest_offsets=earliest_offsets,
        latest_offsets=latest_offsets,
        requested_upper_offsets=requested_upper_offsets,
        allow_new_partitions=allow_new_partitions,
    )
    provider_partitions = {item.partition for item in resume.partitions}
    unknown_group_partitions = set(consumer_group_next_offsets) - provider_partitions
    if unknown_group_partitions:
        raise DebeziumKafkaAdapterError(
            "consumer-group cursor contains partitions not present in provider evidence: "
            f"{sorted(unknown_group_partitions)}"
        )

    alignments: list[DebeziumKafkaPartitionCursorAlignment] = []
    for item in resume.partitions:
        current = consumer_group_next_offsets.get(item.partition)
        if current is not None and (
            not isinstance(current, int) or isinstance(current, bool) or current < 0
        ):
            raise DebeziumKafkaAdapterError(
                "consumer-group next offsets must be non-negative integers"
            )
        desired = item.start_offset
        relation = (
            KafkaCursorRelation.MISSING
            if current is None
            else KafkaCursorRelation.BEHIND
            if current < desired
            else KafkaCursorRelation.AHEAD
            if current > desired
            else KafkaCursorRelation.ALIGNED
        )
        alignments.append(
            DebeziumKafkaPartitionCursorAlignment(
                partition=item.partition,
                framework_next_offset=desired,
                consumer_group_next_offset=current,
                relation=relation,
                seek_required=relation is not KafkaCursorRelation.ALIGNED,
            )
        )

    return DebeziumKafkaCursorCoordinationPlan(
        resume=resume,
        alignments=tuple(alignments),
    )


__all__ = [
    "DebeziumKafkaCursorCoordinationPlan",
    "DebeziumKafkaPartitionCursorAlignment",
    "DebeziumKafkaPartitionResume",
    "DebeziumKafkaResumeGapError",
    "DebeziumKafkaResumePlan",
    "KafkaCursorRelation",
    "plan_debezium_kafka_cursor_coordination",
    "plan_debezium_kafka_resume",
]
