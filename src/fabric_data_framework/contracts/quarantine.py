"""Quarantine batch contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field

from .base import FrozenModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QuarantineScope(str, Enum):
    ROW = "ROW"
    BATCH = "BATCH"


class QuarantineBatch(FrozenModel):
    quarantine_id: UUID = Field(default_factory=uuid4)
    dataset_run_id: UUID
    dataset_id: str = Field(min_length=1)
    scope: QuarantineScope
    row_count: int = Field(ge=1)
    reason_code: str = Field(min_length=1)
    reason_detail: str | None = None
    source_reference: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    replayed_by_dataset_run_id: UUID | None = None

__all__ = ["QuarantineBatch", "QuarantineScope"]
