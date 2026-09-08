"""Governed quarantine review and manual-correction persistence.

Original quarantine batches remain immutable evidence. Review decisions are append-only
optimistic transitions and manual correction bytes remain in governed data-plane storage;
the Control Plane stores only exact references and hashes.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError

from fabric_data_framework.contracts.quarantine import (
    QuarantineCase,
    QuarantineManualCorrection,
    QuarantineResolution,
    QuarantineReviewEvent,
    QuarantineStatus,
)
from .schema import (
    apply_baseline_schema,
    quarantine_batch,
    quarantine_manual_correction,
    quarantine_review_event,
)


class QuarantineGovernanceError(RuntimeError):
    """Base quarantine-governance validation error."""


class QuarantineTransitionConflict(QuarantineGovernanceError):
    """Raised when the requested review transition no longer owns current state."""


_ALLOWED_TRANSITIONS = {
    QuarantineStatus.OPEN: frozenset(
        {
            QuarantineStatus.UNDER_REVIEW,
            QuarantineStatus.RESOLVED,
            QuarantineStatus.REJECTED,
            QuarantineStatus.WAIVED,
        }
    ),
    QuarantineStatus.UNDER_REVIEW: frozenset(
        {
            QuarantineStatus.RESOLVED,
            QuarantineStatus.REJECTED,
            QuarantineStatus.WAIVED,
        }
    ),
    QuarantineStatus.RESOLVED: frozenset(),
    QuarantineStatus.REJECTED: frozenset(),
    QuarantineStatus.WAIVED: frozenset(),
    QuarantineStatus.REPLAYED: frozenset(),
}


def _resolution_allowed(event: QuarantineReviewEvent) -> bool:
    if event.to_status is QuarantineStatus.RESOLVED:
        return event.resolution in {
            QuarantineResolution.SOURCE_CORRECTED,
            QuarantineResolution.RULE_OR_MAPPING_FIXED,
            QuarantineResolution.MANUAL_CORRECTION,
        }
    if event.to_status is QuarantineStatus.REJECTED:
        return event.resolution is QuarantineResolution.REJECTED_AS_INVALID
    if event.to_status is QuarantineStatus.WAIVED:
        return event.resolution is QuarantineResolution.ACCEPTED_EXCEPTION
    return event.resolution is None


def _batch_row(connection, quarantine_id: UUID):
    row = connection.execute(
        select(quarantine_batch).where(
            quarantine_batch.c.quarantine_id == str(quarantine_id)
        )
    ).mappings().first()
    if row is None:
        raise KeyError(f"quarantine batch {quarantine_id} not found")
    return row


def _event_from_row(row) -> QuarantineReviewEvent:
    resolution = row["resolution"]
    correction_id = row["correction_id"]
    return QuarantineReviewEvent(
        event_id=UUID(str(row["event_id"])),
        quarantine_id=UUID(str(row["quarantine_id"])),
        dataset_id=str(row["dataset_id"]),
        from_status=QuarantineStatus(str(row["from_status"])),
        to_status=QuarantineStatus(str(row["to_status"])),
        resolution=(
            QuarantineResolution(str(resolution)) if resolution is not None else None
        ),
        actor=str(row["actor"]),
        reason=str(row["reason"]),
        ticket_reference=(
            str(row["ticket_reference"])
            if row["ticket_reference"] is not None
            else None
        ),
        correction_id=(UUID(str(correction_id)) if correction_id is not None else None),
        occurred_at=row["occurred_at"],
    )


def _correction_from_row(row) -> QuarantineManualCorrection:
    return QuarantineManualCorrection(
        correction_id=UUID(str(row["correction_id"])),
        quarantine_id=UUID(str(row["quarantine_id"])),
        dataset_id=str(row["dataset_id"]),
        original_source_reference=str(row["original_source_reference"]),
        correction_reference=str(row["correction_reference"]),
        correction_payload_sha256=str(row["correction_payload_sha256"]),
        corrected_by=str(row["corrected_by"]),
        reason=str(row["reason"]),
        ticket_reference=(
            str(row["ticket_reference"])
            if row["ticket_reference"] is not None
            else None
        ),
        created_at=row["created_at"],
    )


def _ordered_events(connection, quarantine_id: UUID) -> tuple[QuarantineReviewEvent, ...]:
    rows = connection.execute(
        select(quarantine_review_event).where(
            quarantine_review_event.c.quarantine_id == str(quarantine_id)
        )
    ).mappings().all()
    by_from: dict[QuarantineStatus, QuarantineReviewEvent] = {}
    for row in rows:
        event = _event_from_row(row)
        if event.from_status in by_from:
            raise QuarantineGovernanceError(
                f"quarantine {quarantine_id} has multiple transitions from "
                f"{event.from_status.value}"
            )
        by_from[event.from_status] = event

    ordered: list[QuarantineReviewEvent] = []
    current = QuarantineStatus.OPEN
    seen: set[QuarantineStatus] = set()
    while current in by_from:
        if current in seen:
            raise QuarantineGovernanceError(
                f"quarantine {quarantine_id} review transition cycle detected"
            )
        seen.add(current)
        event = by_from[current]
        ordered.append(event)
        current = event.to_status

    if len(ordered) != len(rows):
        raise QuarantineGovernanceError(
            f"quarantine {quarantine_id} contains disconnected review transitions"
        )
    return tuple(ordered)


def _case_from_connection(connection, quarantine_id: UUID) -> QuarantineCase:
    batch = _batch_row(connection, quarantine_id)
    events = _ordered_events(connection, quarantine_id)
    latest = events[-1] if events else None
    replayed_by = batch["replayed_by_dataset_run_id"]
    if replayed_by is not None:
        return QuarantineCase(
            quarantine_id=quarantine_id,
            dataset_id=str(batch["dataset_id"]),
            status=QuarantineStatus.REPLAYED,
            latest_review_event_id=(latest.event_id if latest is not None else None),
            resolution=(latest.resolution if latest is not None else None),
            correction_id=(latest.correction_id if latest is not None else None),
            replayed_by_dataset_run_id=UUID(str(replayed_by)),
        )
    return QuarantineCase(
        quarantine_id=quarantine_id,
        dataset_id=str(batch["dataset_id"]),
        status=(latest.to_status if latest is not None else QuarantineStatus.OPEN),
        latest_review_event_id=(latest.event_id if latest is not None else None),
        resolution=(latest.resolution if latest is not None else None),
        correction_id=(latest.correction_id if latest is not None else None),
    )


def get_quarantine_case(engine: Engine, quarantine_id: UUID) -> QuarantineCase:
    """Return current governed status, deriving REPLAYED from semantic replay evidence."""

    apply_baseline_schema(engine)
    with engine.connect() as connection:
        return _case_from_connection(connection, quarantine_id)


def read_quarantine_review_events(
    engine: Engine,
    quarantine_id: UUID,
) -> tuple[QuarantineReviewEvent, ...]:
    """Read the validated review chain in lifecycle order, not timestamp order."""

    apply_baseline_schema(engine)
    with engine.connect() as connection:
        _batch_row(connection, quarantine_id)
        return _ordered_events(connection, quarantine_id)


def read_quarantine_manual_correction(
    engine: Engine,
    correction_id: UUID,
) -> QuarantineManualCorrection:
    """Read one immutable manual-correction reference/hash record."""

    apply_baseline_schema(engine)
    with engine.connect() as connection:
        row = connection.execute(
            select(quarantine_manual_correction).where(
                quarantine_manual_correction.c.correction_id == str(correction_id)
            )
        ).mappings().first()
    if row is None:
        raise KeyError(f"quarantine manual correction {correction_id} not found")
    return _correction_from_row(row)


def _validate_event(connection, event: QuarantineReviewEvent, *, allow_manual: bool) -> None:
    batch = _batch_row(connection, event.quarantine_id)
    if str(batch["dataset_id"]) != event.dataset_id:
        raise QuarantineGovernanceError(
            f"quarantine {event.quarantine_id} belongs to dataset {batch['dataset_id']}, "
            f"not {event.dataset_id}"
        )
    case = _case_from_connection(connection, event.quarantine_id)
    if case.status is not event.from_status:
        raise QuarantineTransitionConflict(
            f"quarantine {event.quarantine_id} expected {event.from_status.value}, "
            f"current status is {case.status.value}"
        )
    if event.to_status not in _ALLOWED_TRANSITIONS[event.from_status]:
        raise QuarantineGovernanceError(
            f"invalid quarantine transition {event.from_status.value}->{event.to_status.value}"
        )
    if not _resolution_allowed(event):
        raise QuarantineGovernanceError(
            f"resolution {event.resolution} is not valid for {event.to_status.value}"
        )
    if event.resolution is QuarantineResolution.MANUAL_CORRECTION and not allow_manual:
        raise QuarantineGovernanceError(
            "MANUAL_CORRECTION must use resolve_quarantine_with_manual_correction"
        )


def _insert_event(connection, event: QuarantineReviewEvent) -> None:
    connection.execute(
        quarantine_review_event.insert().values(
            event_id=str(event.event_id),
            transition_key=f"{event.quarantine_id}:{event.from_status.value}",
            quarantine_id=str(event.quarantine_id),
            dataset_id=event.dataset_id,
            from_status=event.from_status.value,
            to_status=event.to_status.value,
            resolution=(event.resolution.value if event.resolution is not None else None),
            actor=event.actor,
            reason=event.reason,
            ticket_reference=event.ticket_reference,
            correction_id=(str(event.correction_id) if event.correction_id is not None else None),
            occurred_at=event.occurred_at,
        )
    )


def record_quarantine_review_event(engine: Engine, event: QuarantineReviewEvent) -> QuarantineCase:
    """Append one non-manual optimistic lifecycle transition.

    The transition key is unique per ``quarantine_id + from_status``. Competing reviewers
    therefore cannot both advance the same prior state; one receives a fail-closed
    ``QuarantineTransitionConflict``.
    """

    apply_baseline_schema(engine)
    try:
        with engine.begin() as connection:
            _validate_event(connection, event, allow_manual=False)
            _insert_event(connection, event)
            return _case_from_connection(connection, event.quarantine_id)
    except IntegrityError as exc:
        raise QuarantineTransitionConflict(
            f"quarantine {event.quarantine_id} transition from "
            f"{event.from_status.value} was already claimed"
        ) from exc


def resolve_quarantine_with_manual_correction(
    engine: Engine,
    *,
    correction: QuarantineManualCorrection,
    event: QuarantineReviewEvent,
) -> QuarantineCase:
    """Atomically retain manual-correction provenance and resolve its review case.

    This operation never changes the original quarantine payload or Bronze. The actual
    corrected rows must already exist in governed storage at ``correction_reference``;
    replay later consumes that approved correction through an explicit provider.
    """

    if event.quarantine_id != correction.quarantine_id:
        raise QuarantineGovernanceError("manual correction/event quarantine_id mismatch")
    if event.dataset_id != correction.dataset_id:
        raise QuarantineGovernanceError("manual correction/event dataset_id mismatch")
    if event.from_status is not QuarantineStatus.UNDER_REVIEW:
        raise QuarantineGovernanceError("manual correction requires UNDER_REVIEW current state")
    if event.to_status is not QuarantineStatus.RESOLVED:
        raise QuarantineGovernanceError("manual correction must resolve the quarantine case")
    if event.resolution is not QuarantineResolution.MANUAL_CORRECTION:
        raise QuarantineGovernanceError("manual correction event requires MANUAL_CORRECTION resolution")
    if event.correction_id != correction.correction_id:
        raise QuarantineGovernanceError("manual correction/event correction_id mismatch")
    if correction.correction_reference == correction.original_source_reference:
        raise QuarantineGovernanceError(
            "manual correction reference must be distinct from immutable original payload"
        )

    apply_baseline_schema(engine)
    try:
        with engine.begin() as connection:
            batch = _batch_row(connection, correction.quarantine_id)
            if str(batch["dataset_id"]) != correction.dataset_id:
                raise QuarantineGovernanceError(
                    f"quarantine {correction.quarantine_id} belongs to dataset "
                    f"{batch['dataset_id']}, not {correction.dataset_id}"
                )
            source_reference = batch["source_reference"]
            if source_reference is None:
                raise QuarantineGovernanceError(
                    "manual correction requires retained original quarantine payload reference"
                )
            if str(source_reference) != correction.original_source_reference:
                raise QuarantineGovernanceError(
                    "manual correction original_source_reference does not match quarantine evidence"
                )
            _validate_event(connection, event, allow_manual=True)
            connection.execute(
                quarantine_manual_correction.insert().values(
                    correction_id=str(correction.correction_id),
                    quarantine_id=str(correction.quarantine_id),
                    dataset_id=correction.dataset_id,
                    original_source_reference=correction.original_source_reference,
                    correction_reference=correction.correction_reference,
                    correction_payload_sha256=correction.correction_payload_sha256,
                    corrected_by=correction.corrected_by,
                    reason=correction.reason,
                    ticket_reference=correction.ticket_reference,
                    created_at=correction.created_at,
                )
            )
            _insert_event(connection, event)
            return _case_from_connection(connection, correction.quarantine_id)
    except IntegrityError as exc:
        raise QuarantineTransitionConflict(
            f"quarantine {correction.quarantine_id} manual correction or transition "
            "was already recorded"
        ) from exc


__all__ = [
    "QuarantineGovernanceError",
    "QuarantineTransitionConflict",
    "get_quarantine_case",
    "read_quarantine_manual_correction",
    "read_quarantine_review_events",
    "record_quarantine_review_event",
    "resolve_quarantine_with_manual_correction",
]
