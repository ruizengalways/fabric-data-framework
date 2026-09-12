"""Fail-closed dataset execution claims backed by the Control Plane.

The lease is a durable mutual-exclusion claim, not a timer-based best-effort lock.
It is removed after ordinary success/failure.  If a process disappears while holding
the claim, the row deliberately remains and requires an explicit operator recovery
after the abandoned execution has been proven terminated.  Automatically stealing an
expired time lease would permit an old writer to mutate a target after a new writer had
started, so ``expires_at`` is retained only as an operational review deadline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import Field, model_validator
from sqlalchemy import Engine, delete, select
from sqlalchemy.exc import IntegrityError

from fabric_data_framework.contracts.base import FrozenModel

from .schema import apply_baseline_schema, dataset_lease


class DatasetLeaseConflict(RuntimeError):
    """Raised when a dataset already has a durable execution claim."""


class DatasetLeaseReleaseConflict(RuntimeError):
    """Raised when a caller cannot release the exact claim it acquired."""


class DatasetLeaseState(FrozenModel):
    dataset_id: str = Field(min_length=1)
    lease_owner: str = Field(min_length=1)
    dataset_run_id: UUID
    lease_version: int = Field(ge=1)
    acquired_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_times(self) -> "DatasetLeaseState":
        for label, value in (
            ("acquired_at", self.acquired_at),
            ("expires_at", self.expires_at),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must be timezone-aware")
        if self.expires_at <= self.acquired_at:
            raise ValueError("expires_at must be after acquired_at")
        return self


def _from_row(row: dict[str, object]) -> DatasetLeaseState:
    acquired_at = row["acquired_at"]
    expires_at = row["expires_at"]
    if not isinstance(acquired_at, datetime) or not isinstance(expires_at, datetime):
        raise RuntimeError("persisted dataset lease timestamps are invalid")
    if acquired_at.tzinfo is None:
        acquired_at = acquired_at.replace(tzinfo=timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return DatasetLeaseState(
        dataset_id=str(row["dataset_id"]),
        lease_owner=str(row["lease_owner"]),
        dataset_run_id=UUID(str(row["dataset_run_id"])),
        lease_version=int(str(row["lease_version"])),
        acquired_at=acquired_at,
        expires_at=expires_at,
    )


def read_dataset_lease(engine: Engine, dataset_id: str) -> DatasetLeaseState | None:
    """Read the current durable execution claim for one dataset."""

    apply_baseline_schema(engine)
    with engine.connect() as connection:
        row = connection.execute(
            select(dataset_lease).where(dataset_lease.c.dataset_id == dataset_id)
        ).mappings().first()
    return _from_row(dict(row)) if row is not None else None


def acquire_dataset_lease(
    engine: Engine,
    *,
    dataset_id: str,
    lease_owner: str,
    dataset_run_id: UUID,
    review_deadline: datetime,
) -> DatasetLeaseState:
    """Atomically claim exclusive dataset mutation authority.

    ``review_deadline`` is intentionally not an automatic takeover boundary.  It tells
    operations when an apparently abandoned claim needs investigation; recovery must
    still prove that the old executor cannot resume before removing the row.
    """

    if not dataset_id or not lease_owner:
        raise ValueError("dataset_id and lease_owner are required")
    if review_deadline.tzinfo is None or review_deadline.utcoffset() is None:
        raise ValueError("review_deadline must be timezone-aware")

    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)
    if review_deadline <= now:
        raise ValueError("review_deadline must be in the future")
    state = DatasetLeaseState(
        dataset_id=dataset_id,
        lease_owner=lease_owner,
        dataset_run_id=dataset_run_id,
        lease_version=1,
        acquired_at=now,
        expires_at=review_deadline,
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                dataset_lease.insert().values(
                    dataset_id=dataset_id,
                    lease_owner=lease_owner,
                    dataset_run_id=str(dataset_run_id),
                    lease_version=state.lease_version,
                    acquired_at=state.acquired_at,
                    expires_at=state.expires_at,
                )
            )
    except IntegrityError as exc:
        existing = read_dataset_lease(engine, dataset_id)
        if existing is None:
            raise
        detail = f" owner={existing.lease_owner!r} run={existing.dataset_run_id}"
        raise DatasetLeaseConflict(
            f"dataset {dataset_id!r} is already claimed for mutation;{detail}"
        ) from exc
    return state


def release_dataset_lease(engine: Engine, lease: DatasetLeaseState) -> None:
    """Release only the exact claim returned by :func:`acquire_dataset_lease`."""

    apply_baseline_schema(engine)
    with engine.begin() as connection:
        result = connection.execute(
            delete(dataset_lease).where(
                dataset_lease.c.dataset_id == lease.dataset_id,
                dataset_lease.c.lease_owner == lease.lease_owner,
                dataset_lease.c.dataset_run_id == str(lease.dataset_run_id),
                dataset_lease.c.lease_version == lease.lease_version,
            )
        )
    if result.rowcount != 1:
        raise DatasetLeaseReleaseConflict(
            f"dataset lease {lease.dataset_id!r} changed before exact release"
        )


__all__ = [
    "DatasetLeaseConflict",
    "DatasetLeaseReleaseConflict",
    "DatasetLeaseState",
    "acquire_dataset_lease",
    "read_dataset_lease",
    "release_dataset_lease",
]
