"""Audited current-projection mode transition state changes.

Physical target replacement happens outside the relational Control Plane.  This module
owns the environment-local checkpoint reset and append-only transition evidence that
must follow a successful physical transition.  It never silently resets progress.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field, model_validator
from sqlalchemy import Engine, delete, select

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.current_projection import CurrentProjectionMode

from .schema import (
    apply_baseline_schema,
    cdc_checkpoint,
    current_projection_transition_event,
)


class ProjectionTransitionStatus(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CurrentProjectionTransitionEvent(FrozenModel):
    event_id: UUID = Field(default_factory=uuid4)
    transition_id: UUID
    dataset_id: str = Field(min_length=1)
    from_mode: CurrentProjectionMode
    to_mode: CurrentProjectionMode
    status: ProjectionTransitionStatus
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    ticket_reference: str | None = None
    checkpoint_version_before: int | None = Field(default=None, ge=1)
    checkpoint_reset: bool = False
    detail: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_event(self) -> "CurrentProjectionTransitionEvent":
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.checkpoint_reset and self.checkpoint_version_before is None:
            raise ValueError("checkpoint_reset requires checkpoint_version_before")
        return self


def _insert_event(connection, event: CurrentProjectionTransitionEvent) -> None:
    connection.execute(
        current_projection_transition_event.insert().values(
            event_id=str(event.event_id),
            transition_id=str(event.transition_id),
            dataset_id=event.dataset_id,
            from_mode=event.from_mode.value,
            to_mode=event.to_mode.value,
            status=event.status.value,
            actor=event.actor,
            reason=event.reason,
            ticket_reference=event.ticket_reference,
            checkpoint_version_before=event.checkpoint_version_before,
            checkpoint_reset=event.checkpoint_reset,
            detail=event.detail,
            occurred_at=event.occurred_at,
        )
    )


def record_projection_transition_event(
    engine: Engine,
    event: CurrentProjectionTransitionEvent,
) -> None:
    """Append immutable transition evidence without changing runtime checkpoint state."""

    apply_baseline_schema(engine)
    with engine.begin() as connection:
        _insert_event(connection, event)


def complete_projection_transition(
    engine: Engine,
    *,
    transition_id: UUID,
    dataset_id: str,
    from_mode: CurrentProjectionMode,
    to_mode: CurrentProjectionMode,
    actor: str,
    reason: str,
    ticket_reference: str | None,
    expected_checkpoint_version: int | None,
    reset_checkpoint: bool,
    detail: str | None = None,
) -> CurrentProjectionTransitionEvent:
    """Atomically reset an exact checkpoint when required and append COMPLETED evidence.

    Leaving ``DELTA_PROJECTION`` must pass the exact checkpoint version observed before
    physical target replacement.  Any concurrent checkpoint change fails closed.
    """

    if not dataset_id or not actor or not reason:
        raise ValueError("dataset_id, actor and reason are required")
    if reset_checkpoint and expected_checkpoint_version is None:
        raise ValueError("checkpoint reset requires expected_checkpoint_version")

    apply_baseline_schema(engine)
    with engine.begin() as connection:
        current = connection.execute(
            select(cdc_checkpoint.c.version).where(
                cdc_checkpoint.c.dataset_id == dataset_id
            )
        ).scalar_one_or_none()

        if reset_checkpoint:
            if current is None:
                raise RuntimeError(
                    "current projection transition expected a CDC checkpoint to reset"
                )
            if int(current) != expected_checkpoint_version:
                raise RuntimeError(
                    "current projection checkpoint changed during physical mode transition"
                )
            result = connection.execute(
                delete(cdc_checkpoint).where(
                    cdc_checkpoint.c.dataset_id == dataset_id,
                    cdc_checkpoint.c.version == expected_checkpoint_version,
                )
            )
            if result.rowcount != 1:
                raise RuntimeError(
                    "current projection checkpoint changed during exact reset"
                )
        elif expected_checkpoint_version is not None:
            if current is None or int(current) != expected_checkpoint_version:
                raise RuntimeError(
                    "current projection checkpoint does not match transition evidence"
                )

        event = CurrentProjectionTransitionEvent(
            transition_id=transition_id,
            dataset_id=dataset_id,
            from_mode=from_mode,
            to_mode=to_mode,
            status=ProjectionTransitionStatus.COMPLETED,
            actor=actor,
            reason=reason,
            ticket_reference=ticket_reference,
            checkpoint_version_before=expected_checkpoint_version,
            checkpoint_reset=reset_checkpoint,
            detail=detail,
        )
        _insert_event(connection, event)
    return event


def read_projection_transition_events(
    engine: Engine,
    *,
    transition_id: UUID,
) -> tuple[CurrentProjectionTransitionEvent, ...]:
    apply_baseline_schema(engine)
    with engine.connect() as connection:
        rows = connection.execute(
            select(current_projection_transition_event)
            .where(
                current_projection_transition_event.c.transition_id
                == str(transition_id)
            )
            .order_by(current_projection_transition_event.c.occurred_at)
        ).mappings().all()
    events = []
    for row in rows:
        occurred_at = row["occurred_at"]
        if not isinstance(occurred_at, datetime):
            raise RuntimeError("persisted projection transition timestamp is invalid")
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        events.append(
            CurrentProjectionTransitionEvent(
                event_id=UUID(str(row["event_id"])),
                transition_id=UUID(str(row["transition_id"])),
                dataset_id=str(row["dataset_id"]),
                from_mode=CurrentProjectionMode(str(row["from_mode"])),
                to_mode=CurrentProjectionMode(str(row["to_mode"])),
                status=ProjectionTransitionStatus(str(row["status"])),
                actor=str(row["actor"]),
                reason=str(row["reason"]),
                ticket_reference=(
                    str(row["ticket_reference"])
                    if row["ticket_reference"] is not None
                    else None
                ),
                checkpoint_version_before=(
                    int(row["checkpoint_version_before"])
                    if row["checkpoint_version_before"] is not None
                    else None
                ),
                checkpoint_reset=bool(row["checkpoint_reset"]),
                detail=str(row["detail"]) if row["detail"] is not None else None,
                occurred_at=occurred_at,
            )
        )
    return tuple(events)


__all__ = [
    "CurrentProjectionTransitionEvent",
    "ProjectionTransitionStatus",
    "complete_projection_transition",
    "read_projection_transition_events",
    "record_projection_transition_event",
]
