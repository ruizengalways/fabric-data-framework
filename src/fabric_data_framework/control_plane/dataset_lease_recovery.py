"""Governed abandoned dataset-lease recovery.

A lease expiry is only an operator review deadline.  Recovery requires explicit proof
that the old executor cannot resume and deletes only the exact persisted lease identity
inside the same transaction that appends immutable recovery evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import Field, model_validator
from sqlalchemy import Engine, delete, select

from fabric_data_framework.contracts.base import FrozenModel

from .schema import apply_baseline_schema, dataset_lease, dataset_lease_recovery_event


class DatasetLeaseRecoveryConflict(RuntimeError):
    pass


class DatasetLeaseRecoveryEvent(FrozenModel):
    event_id: UUID = Field(default_factory=uuid4)
    dataset_id: str = Field(min_length=1)
    lease_owner: str = Field(min_length=1)
    dataset_run_id: UUID
    lease_version: int = Field(ge=1)
    recovered_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    proof_reference: str = Field(min_length=1)
    review_deadline: datetime
    recovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_times(self) -> "DatasetLeaseRecoveryEvent":
        for label, value in (
            ("review_deadline", self.review_deadline),
            ("recovered_at", self.recovered_at),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must be timezone-aware")
        return self


def recover_abandoned_dataset_lease(
    engine: Engine,
    *,
    dataset_id: str,
    expected_lease_owner: str,
    expected_dataset_run_id: UUID,
    expected_lease_version: int,
    recovered_by: str,
    reason: str,
    proof_reference: str,
    recovered_at: datetime | None = None,
) -> DatasetLeaseRecoveryEvent:
    """Release one proven-abandoned lease and retain immutable operator evidence.

    Automatic timeout takeover is deliberately impossible.  The persisted review
    deadline must have elapsed, and caller-provided lease identity must match exactly.
    """

    if expected_lease_version < 1:
        raise ValueError("expected_lease_version must be >= 1")
    if not all((dataset_id, expected_lease_owner, recovered_by, reason, proof_reference)):
        raise ValueError("lease recovery identity, actor, reason and proof are required")
    now = recovered_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("recovered_at must be timezone-aware")

    apply_baseline_schema(engine)
    with engine.begin() as connection:
        row = connection.execute(
            select(dataset_lease).where(dataset_lease.c.dataset_id == dataset_id)
        ).mappings().first()
        if row is None:
            raise DatasetLeaseRecoveryConflict(
                f"dataset {dataset_id!r} has no lease to recover"
            )
        if (
            str(row["lease_owner"]) != expected_lease_owner
            or UUID(str(row["dataset_run_id"])) != expected_dataset_run_id
            or int(row["lease_version"]) != expected_lease_version
        ):
            raise DatasetLeaseRecoveryConflict(
                "dataset lease identity changed before governed recovery"
            )
        deadline = row["expires_at"]
        if not isinstance(deadline, datetime):
            raise DatasetLeaseRecoveryConflict("persisted lease review deadline is invalid")
        if deadline.tzinfo is None or deadline.utcoffset() is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if now < deadline:
            raise DatasetLeaseRecoveryConflict(
                "dataset lease review deadline has not elapsed; automatic/early takeover is forbidden"
            )

        event = DatasetLeaseRecoveryEvent(
            dataset_id=dataset_id,
            lease_owner=expected_lease_owner,
            dataset_run_id=expected_dataset_run_id,
            lease_version=expected_lease_version,
            recovered_by=recovered_by,
            reason=reason,
            proof_reference=proof_reference,
            review_deadline=deadline,
            recovered_at=now,
        )
        connection.execute(
            dataset_lease_recovery_event.insert().values(
                event_id=str(event.event_id),
                dataset_id=event.dataset_id,
                lease_owner=event.lease_owner,
                dataset_run_id=str(event.dataset_run_id),
                lease_version=event.lease_version,
                recovered_by=event.recovered_by,
                reason=event.reason,
                proof_reference=event.proof_reference,
                review_deadline=event.review_deadline,
                recovered_at=event.recovered_at,
            )
        )
        result = connection.execute(
            delete(dataset_lease).where(
                dataset_lease.c.dataset_id == dataset_id,
                dataset_lease.c.lease_owner == expected_lease_owner,
                dataset_lease.c.dataset_run_id == str(expected_dataset_run_id),
                dataset_lease.c.lease_version == expected_lease_version,
            )
        )
        if result.rowcount != 1:
            raise DatasetLeaseRecoveryConflict(
                "dataset lease changed concurrently during governed recovery"
            )
    return event


def read_dataset_lease_recovery_events(
    engine: Engine,
    *,
    dataset_id: str,
) -> tuple[DatasetLeaseRecoveryEvent, ...]:
    apply_baseline_schema(engine)
    with engine.connect() as connection:
        rows = connection.execute(
            select(dataset_lease_recovery_event)
            .where(dataset_lease_recovery_event.c.dataset_id == dataset_id)
            .order_by(dataset_lease_recovery_event.c.recovered_at)
        ).mappings().all()
    events = []
    for row in rows:
        review_deadline = row["review_deadline"]
        recovered_at = row["recovered_at"]
        if not isinstance(review_deadline, datetime) or not isinstance(recovered_at, datetime):
            raise RuntimeError("persisted dataset lease recovery timestamps are invalid")
        if review_deadline.tzinfo is None or review_deadline.utcoffset() is None:
            review_deadline = review_deadline.replace(tzinfo=timezone.utc)
        if recovered_at.tzinfo is None or recovered_at.utcoffset() is None:
            recovered_at = recovered_at.replace(tzinfo=timezone.utc)
        events.append(
            DatasetLeaseRecoveryEvent(
                event_id=UUID(str(row["event_id"])),
                dataset_id=str(row["dataset_id"]),
                lease_owner=str(row["lease_owner"]),
                dataset_run_id=UUID(str(row["dataset_run_id"])),
                lease_version=int(row["lease_version"]),
                recovered_by=str(row["recovered_by"]),
                reason=str(row["reason"]),
                proof_reference=str(row["proof_reference"]),
                review_deadline=review_deadline,
                recovered_at=recovered_at,
            )
        )
    return tuple(events)


__all__ = [
    "DatasetLeaseRecoveryConflict",
    "DatasetLeaseRecoveryEvent",
    "read_dataset_lease_recovery_events",
    "recover_abandoned_dataset_lease",
]
