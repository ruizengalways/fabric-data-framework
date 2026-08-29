"""Provider-neutral CDC event, ordering and checkpoint contracts.

Provider adapters translate Debezium/binlog/LSN/Kafka/native Fabric coordinates into
``partition + integer position tuple`` before entering this module. The framework
never guesses ordering from opaque provider tokens.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence

from pydantic import Field, model_validator

from ..config import FrozenModel, canonical_hash
from ..runtime import StateCommitGate


class CDCContractError(ValueError):
    """Base error for malformed or unsafe CDC evidence."""


class CDCOrderingError(CDCContractError):
    """Raised when the framework cannot prove a deterministic event order."""


class CDCConflictError(CDCContractError):
    """Raised when one event identity/source position carries conflicting content."""


class CDCEvidenceError(CDCContractError):
    """Raised when a bounded CDC window cannot be proven complete/safe."""


class CDCOperation(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class CDCSourcePosition(FrozenModel):
    """Canonical totally ordered position inside one source partition."""

    partition: str = Field(default="default", min_length=1)
    values: tuple[int, ...]

    @model_validator(mode="after")
    def validate_values(self) -> "CDCSourcePosition":
        if not self.values:
            raise ValueError("CDC source position requires at least one integer component")
        if any(value < 0 for value in self.values):
            raise ValueError("CDC source position components must be non-negative integers")
        return self


class CDCCheckpoint(FrozenModel):
    """Committed inclusive CDC position per source partition."""

    positions: tuple[CDCSourcePosition, ...] = ()

    @model_validator(mode="after")
    def validate_positions(self) -> "CDCCheckpoint":
        partitions = tuple(item.partition for item in self.positions)
        if len(set(partitions)) != len(partitions):
            raise ValueError("CDC checkpoint partitions must be unique")
        if partitions != tuple(sorted(partitions)):
            raise ValueError("CDC checkpoint positions must be sorted by partition")
        return self

    def position_for(self, partition: str) -> tuple[int, ...] | None:
        return next(
            (item.values for item in self.positions if item.partition == partition),
            None,
        )


class CDCEvent(FrozenModel):
    """Canonical row-level change event independent from provider envelope format."""

    event_id: str = Field(min_length=1)
    operation: CDCOperation
    key: dict[str, Any]
    position: CDCSourcePosition
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    event_time: datetime | None = None
    transaction_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_event(self) -> "CDCEvent":
        if not self.key or any(value is None for value in self.key.values()):
            raise ValueError("CDC event key must be non-empty and cannot contain null values")
        if self.event_time is not None and (
            self.event_time.tzinfo is None or self.event_time.utcoffset() is None
        ):
            raise ValueError("CDC event_time must be timezone-aware")
        if self.operation in {CDCOperation.INSERT, CDCOperation.UPDATE} and self.after is None:
            raise ValueError(f"CDC {self.operation.value} event requires after payload")
        if self.operation is CDCOperation.DELETE and self.after is not None:
            raise ValueError("CDC DELETE event cannot contain after payload")
        for payload_name, payload in (("before", self.before), ("after", self.after)):
            if payload is None:
                continue
            if any(name.startswith("_framework_cdc_") for name in payload):
                raise ValueError(f"CDC {payload_name} payload uses reserved framework CDC fields")
            for key_name, key_value in self.key.items():
                if key_name in payload and payload[key_name] != key_value:
                    raise ValueError(
                        f"CDC {payload_name} payload key {key_name} conflicts with event key"
                    )
        return self

    @property
    def content_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))

    @property
    def key_hash(self) -> str:
        return canonical_hash(self.key)


class CDCNormalizedBatch(FrozenModel):
    """Deduplicated bounded CDC events ready for semantic apply."""

    events: tuple[CDCEvent, ...]
    lower_checkpoint: CDCCheckpoint | None
    upper_checkpoint: CDCCheckpoint
    duplicate_events_ignored: int = Field(default=0, ge=0)
    already_committed_events_ignored: int = Field(default=0, ge=0)


class CDCCheckpointTransition(FrozenModel):
    """State transition that cannot advance before target/reconciliation gates pass."""

    before: CDCCheckpoint | None = None
    after: CDCCheckpoint
    gate: StateCommitGate

    @model_validator(mode="after")
    def validate_transition(self) -> "CDCCheckpointTransition":
        if self.before is not None:
            for previous in self.before.positions:
                next_position = self.after.position_for(previous.partition)
                if next_position is None:
                    raise ValueError(
                        f"CDC checkpoint cannot drop partition {previous.partition}"
                    )
                if next_position < previous.values:
                    raise ValueError(
                        f"CDC checkpoint cannot regress partition {previous.partition}"
                    )
        changed = self.before is None or self.after != self.before
        if changed and not self.gate.can_advance_state:
            raise ValueError(
                "CDC checkpoint cannot advance before target commit and required reconciliation"
            )
        return self


def build_cdc_checkpoint(
    positions: Mapping[str, Sequence[int]],
) -> CDCCheckpoint:
    """Build a deterministic checkpoint from provider-normalized partition positions."""

    return CDCCheckpoint(
        positions=tuple(
            CDCSourcePosition(partition=partition, values=tuple(values))
            for partition, values in sorted(positions.items())
        )
    )


def _validate_window(
    lower_checkpoint: CDCCheckpoint | None,
    upper_checkpoint: CDCCheckpoint,
) -> None:
    if lower_checkpoint is None:
        return
    for previous in lower_checkpoint.positions:
        upper = upper_checkpoint.position_for(previous.partition)
        if upper is None:
            raise CDCEvidenceError(
                f"CDC upper checkpoint dropped partition {previous.partition}"
            )
        if upper < previous.values:
            raise CDCEvidenceError(
                f"CDC upper checkpoint regressed partition {previous.partition}"
            )


def normalize_cdc_batch(
    events: Sequence[CDCEvent],
    *,
    upper_checkpoint: CDCCheckpoint,
    lower_checkpoint: CDCCheckpoint | None = None,
    complete_through_upper: bool,
) -> CDCNormalizedBatch:
    """Validate/dedupe one frozen CDC source window.

    ``lower_checkpoint`` is inclusive committed state, so events at or below it are
    ignored as overlap/rerun evidence. ``upper_checkpoint`` is the frozen inclusive
    boundary. A provider must explicitly prove completeness through that boundary.
    """

    if not complete_through_upper:
        raise CDCEvidenceError(
            "CDC batch cannot be accepted without completeness evidence through upper checkpoint"
        )
    _validate_window(lower_checkpoint, upper_checkpoint)

    seen_ids: dict[str, str] = {}
    seen_positions: dict[tuple[str, tuple[int, ...]], tuple[str, str]] = {}
    key_partitions: dict[str, str] = {}
    accepted: list[CDCEvent] = []
    duplicate_events_ignored = 0
    already_committed_events_ignored = 0

    for event in events:
        event_hash = event.content_hash
        prior_hash = seen_ids.get(event.event_id)
        if prior_hash is not None:
            if prior_hash != event_hash:
                raise CDCConflictError(
                    f"CDC event_id {event.event_id} carries conflicting payload/evidence"
                )
            duplicate_events_ignored += 1
            continue
        seen_ids[event.event_id] = event_hash

        position_key = (event.position.partition, event.position.values)
        prior_position = seen_positions.get(position_key)
        if prior_position is not None:
            prior_event_id, prior_position_hash = prior_position
            if prior_event_id != event.event_id or prior_position_hash != event_hash:
                raise CDCOrderingError(
                    "multiple CDC events share one canonical source position; provider adapter "
                    "must include a row/transaction sequence component"
                )
        else:
            seen_positions[position_key] = (event.event_id, event_hash)

        upper = upper_checkpoint.position_for(event.position.partition)
        if upper is None:
            raise CDCEvidenceError(
                f"CDC event partition {event.position.partition} is absent from upper checkpoint"
            )
        if event.position.values > upper:
            raise CDCEvidenceError(
                f"CDC event {event.event_id} is beyond the frozen upper checkpoint"
            )

        if lower_checkpoint is not None:
            lower = lower_checkpoint.position_for(event.position.partition)
            if lower is not None and event.position.values <= lower:
                already_committed_events_ignored += 1
                continue

        previous_partition = key_partitions.get(event.key_hash)
        if previous_partition is not None and previous_partition != event.position.partition:
            raise CDCOrderingError(
                "one CDC key appears in multiple partitions inside the bounded batch; "
                "a deterministic per-key order cannot be proven"
            )
        key_partitions[event.key_hash] = event.position.partition
        accepted.append(event)

    accepted.sort(
        key=lambda event: (
            event.position.partition,
            event.position.values,
            event.event_id,
        )
    )
    return CDCNormalizedBatch(
        events=tuple(accepted),
        lower_checkpoint=lower_checkpoint,
        upper_checkpoint=upper_checkpoint,
        duplicate_events_ignored=duplicate_events_ignored,
        already_committed_events_ignored=already_committed_events_ignored,
    )


__all__ = [
    "CDCCheckpoint",
    "CDCCheckpointTransition",
    "CDCConflictError",
    "CDCContractError",
    "CDCEvidenceError",
    "CDCEvent",
    "CDCNormalizedBatch",
    "CDCOperation",
    "CDCOrderingError",
    "CDCSourcePosition",
    "build_cdc_checkpoint",
    "normalize_cdc_batch",
]
