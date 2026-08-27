"""Normalized Bronze metadata envelope used by downstream framework logic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BronzeRecord(FrozenModel):
    data: dict[str, Any]
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: UUID
    dataset_run_id: UUID
    source_system: str
    source_object: str
    operation: str = "UPSERT"
    source_commit_ts: datetime | None = None
    source_sequence: str | int | None = None
    schema_version: int = 1

    def as_flat_record(self) -> dict[str, Any]:
        return {
            **self.data,
            "_framework_ingested_at": self.ingested_at,
            "_framework_run_id": str(self.run_id),
            "_framework_dataset_run_id": str(self.dataset_run_id),
            "_framework_source_system": self.source_system,
            "_framework_source_object": self.source_object,
            "_framework_operation": self.operation,
            "_framework_source_commit_ts": self.source_commit_ts,
            "_framework_source_sequence": self.source_sequence,
            "_framework_schema_version": self.schema_version,
        }


def normalize_bronze(
    rows: tuple[dict[str, Any], ...],
    *,
    pipeline_run_id: UUID,
    dataset_run_id: UUID,
    source_system: str,
    source_object: str,
    event_time_column: str | None,
    source_sequence_columns: tuple[str, ...] = (),
) -> tuple[BronzeRecord, ...]:
    records: list[BronzeRecord] = []
    for row in rows:
        commit_ts = row.get(event_time_column) if event_time_column else None
        if commit_ts is not None and not isinstance(commit_ts, datetime):
            raise TypeError("event_time_column values must be datetime when present")
        source_sequence: str | int | None = None
        if source_sequence_columns:
            values = tuple(row[column] for column in source_sequence_columns)
            source_sequence = "|".join(str(value) for value in values)
        records.append(
            BronzeRecord(
                data=dict(row),
                run_id=pipeline_run_id,
                dataset_run_id=dataset_run_id,
                source_system=source_system,
                source_object=source_object,
                source_commit_ts=commit_ts,
                source_sequence=source_sequence,
            )
        )
    return tuple(records)
