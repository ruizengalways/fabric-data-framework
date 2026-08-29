"""Delta Change Data Feed -> canonical CDC adapter.

Delta CDF exposes commit-grain ordering and row change types. The adapter pairs one
update_preimage/update_postimage for the same key+commit into one canonical UPDATE.
Because CDF does not expose a universal row sequence inside a commit, the adapter
assigns a deterministic key-sorted sequence for different keys and fails closed when
one key contains more than one logical mutation in the same commit.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any, Sequence

from pydantic import Field, model_validator

from ...capture.cdc import (
    CDCCheckpoint,
    CDCEvent,
    CDCNormalizedBatch,
    CDCOperation,
    CDCSourcePosition,
    build_cdc_checkpoint,
    normalize_cdc_batch,
)
from ...config import FrozenModel, canonical_hash


DELTA_CDF_PROFILE = "delta_cdf_v1"
_DELTA_PARTITION_PREFIX = "delta-cdf:"
_MAX_COMMIT_ROW_SEQUENCE = 2**63 - 1


class DeltaCDFAdapterError(ValueError):
    pass


class DeltaCDFChangeType(str, Enum):
    INSERT = "insert"
    DELETE = "delete"
    UPDATE_PREIMAGE = "update_preimage"
    UPDATE_POSTIMAGE = "update_postimage"


class DeltaCDFRecord(FrozenModel):
    change_type: DeltaCDFChangeType
    commit_version: int = Field(ge=0)
    commit_timestamp: datetime
    data: dict[str, Any]

    @model_validator(mode="after")
    def validate_timestamp(self) -> "DeltaCDFRecord":
        if self.commit_timestamp.tzinfo is None or self.commit_timestamp.utcoffset() is None:
            raise ValueError("Delta CDF commit_timestamp must be timezone-aware")
        return self

    @property
    def content_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class DeltaCDFBatchResult(FrozenModel):
    normalized_batch: CDCNormalizedBatch
    input_records: int = Field(ge=0)
    duplicate_records_ignored: int = Field(ge=0)
    logical_events: int = Field(ge=0)
    update_pairs: int = Field(ge=0)


def _key_for_record(record: DeltaCDFRecord, key_columns: tuple[str, ...]) -> tuple[Any, ...]:
    values = tuple(record.data.get(column) for column in key_columns)
    if any(value is None for value in values):
        raise DeltaCDFAdapterError(
            f"Delta CDF key columns cannot be null/missing: {key_columns}"
        )
    return values


def _key_payload(key_columns: tuple[str, ...], key: tuple[Any, ...]) -> dict[str, Any]:
    return dict(zip(key_columns, key, strict=True))


def _dedupe_exact_records(
    records: Sequence[DeltaCDFRecord],
) -> tuple[tuple[DeltaCDFRecord, ...], int]:
    seen: set[str] = set()
    accepted: list[DeltaCDFRecord] = []
    duplicates = 0
    for record in records:
        fingerprint = record.content_hash
        if fingerprint in seen:
            duplicates += 1
            continue
        seen.add(fingerprint)
        accepted.append(record)
    return tuple(accepted), duplicates


def _logical_event_for_group(
    *,
    table_reference: str,
    commit_version: int,
    row_sequence: int,
    key_columns: tuple[str, ...],
    key: tuple[Any, ...],
    records: tuple[DeltaCDFRecord, ...],
) -> tuple[CDCEvent, bool]:
    by_type: dict[DeltaCDFChangeType, list[DeltaCDFRecord]] = defaultdict(list)
    for record in records:
        by_type[record.change_type].append(record)

    for change_type, items in by_type.items():
        if len(items) > 1:
            raise DeltaCDFAdapterError(
                "Delta CDF contains more than one non-identical record for key "
                f"{key} commit={commit_version} change_type={change_type.value}; "
                "within-commit row order is not provable"
            )

    present = frozenset(by_type)
    is_update = present == frozenset(
        {DeltaCDFChangeType.UPDATE_PREIMAGE, DeltaCDFChangeType.UPDATE_POSTIMAGE}
    )
    is_insert = present == frozenset({DeltaCDFChangeType.INSERT})
    is_delete = present == frozenset({DeltaCDFChangeType.DELETE})
    if not (is_update or is_insert or is_delete):
        raise DeltaCDFAdapterError(
            "Delta CDF key has an ambiguous set of change records within one commit: "
            f"key={key}, commit={commit_version}, types={sorted(item.value for item in present)}"
        )

    key_payload = _key_payload(key_columns, key)
    position = CDCSourcePosition(
        partition=f"{_DELTA_PARTITION_PREFIX}{table_reference}",
        values=(commit_version, row_sequence),
    )
    event_id = (
        f"delta-cdf:{canonical_hash({'table': table_reference})[:16]}:"
        f"{commit_version}:{row_sequence}:{canonical_hash(key_payload)[:16]}"
    )
    metadata = {
        "provider": "delta_cdf",
        "table_reference": table_reference,
        "commit_version": commit_version,
        "change_types": sorted(item.value for item in present),
        "within_commit_order": "deterministic_key_order_not_source_temporal_order",
    }

    if is_update:
        before = dict(by_type[DeltaCDFChangeType.UPDATE_PREIMAGE][0].data)
        after_record = by_type[DeltaCDFChangeType.UPDATE_POSTIMAGE][0]
        after = dict(after_record.data)
        event_time = after_record.commit_timestamp
        operation = CDCOperation.UPDATE
    elif is_insert:
        insert = by_type[DeltaCDFChangeType.INSERT][0]
        before = None
        after = dict(insert.data)
        event_time = insert.commit_timestamp
        operation = CDCOperation.INSERT
    else:
        delete = by_type[DeltaCDFChangeType.DELETE][0]
        before = dict(delete.data)
        after = None
        event_time = delete.commit_timestamp
        operation = CDCOperation.DELETE

    return (
        CDCEvent(
            event_id=event_id,
            operation=operation,
            key=key_payload,
            position=position,
            before=before,
            after=after,
            event_time=event_time,
            transaction_id=f"delta-commit:{commit_version}",
            metadata=metadata,
        ),
        is_update,
    )


def delta_cdf_checkpoint(table_reference: str, commit_version: int) -> CDCCheckpoint:
    """Inclusive checkpoint meaning the full Delta commit version is applied."""

    if not table_reference:
        raise ValueError("table_reference is required")
    if commit_version < 0:
        raise ValueError("commit_version must be non-negative")
    return build_cdc_checkpoint(
        {
            f"{_DELTA_PARTITION_PREFIX}{table_reference}": (
                commit_version,
                _MAX_COMMIT_ROW_SEQUENCE,
            )
        }
    )


def normalize_delta_cdf_batch(
    records: Sequence[DeltaCDFRecord],
    *,
    table_reference: str,
    key_columns: tuple[str, ...],
    upper_commit_version: int,
    complete_through_upper: bool,
    lower_committed_version: int | None = None,
) -> DeltaCDFBatchResult:
    """Normalize a bounded complete Delta CDF version range into canonical CDC.

    ``lower_committed_version`` is inclusive applied progress. Records at/below it are
    allowed as overlap and are ignored by the canonical CDC normalizer. The upper
    checkpoint represents the *entire* commit version, including a version that has no
    row changes for this table.
    """

    if not table_reference:
        raise DeltaCDFAdapterError("table_reference is required")
    if not key_columns:
        raise DeltaCDFAdapterError("Delta CDF normalization requires key_columns")
    if len(set(key_columns)) != len(key_columns):
        raise DeltaCDFAdapterError("Delta CDF key_columns must be unique")
    if upper_commit_version < 0:
        raise DeltaCDFAdapterError("upper_commit_version must be non-negative")
    if lower_committed_version is not None:
        if lower_committed_version < 0:
            raise DeltaCDFAdapterError("lower_committed_version must be non-negative")
        if lower_committed_version > upper_commit_version:
            raise DeltaCDFAdapterError("Delta CDF lower version cannot exceed upper version")

    deduped, duplicate_count = _dedupe_exact_records(records)
    grouped: dict[tuple[int, tuple[Any, ...]], list[DeltaCDFRecord]] = defaultdict(list)
    for record in deduped:
        if record.commit_version > upper_commit_version:
            raise DeltaCDFAdapterError(
                f"Delta CDF record commit {record.commit_version} exceeds frozen upper "
                f"version {upper_commit_version}"
            )
        key = _key_for_record(record, key_columns)
        grouped[(record.commit_version, key)].append(record)

    events: list[CDCEvent] = []
    update_pairs = 0
    groups_by_commit: dict[
        int, list[tuple[tuple[Any, ...], tuple[DeltaCDFRecord, ...]]]
    ] = defaultdict(list)
    for (commit_version, key), items in grouped.items():
        groups_by_commit[commit_version].append((key, tuple(items)))

    for commit_version in sorted(groups_by_commit):
        ordered_groups = sorted(groups_by_commit[commit_version], key=lambda item: repr(item[0]))
        for row_sequence, (key, items) in enumerate(ordered_groups):
            event, is_update = _logical_event_for_group(
                table_reference=table_reference,
                commit_version=commit_version,
                row_sequence=row_sequence,
                key_columns=key_columns,
                key=key,
                records=items,
            )
            events.append(event)
            update_pairs += int(is_update)

    upper = delta_cdf_checkpoint(table_reference, upper_commit_version)
    lower = (
        delta_cdf_checkpoint(table_reference, lower_committed_version)
        if lower_committed_version is not None
        else None
    )
    normalized = normalize_cdc_batch(
        events,
        lower_checkpoint=lower,
        upper_checkpoint=upper,
        complete_through_upper=complete_through_upper,
    )
    return DeltaCDFBatchResult(
        normalized_batch=normalized,
        input_records=len(records),
        duplicate_records_ignored=duplicate_count,
        logical_events=len(events),
        update_pairs=update_pairs,
    )


__all__ = [
    "DELTA_CDF_PROFILE",
    "DeltaCDFAdapterError",
    "DeltaCDFBatchResult",
    "DeltaCDFChangeType",
    "DeltaCDFRecord",
    "delta_cdf_checkpoint",
    "normalize_delta_cdf_batch",
]
