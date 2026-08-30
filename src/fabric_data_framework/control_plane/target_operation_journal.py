"""Relational persistence for durable target-operation idempotency.

The current-state row is protected by optimistic compare-and-swap. Every successful
state change appends an immutable event in the same database transaction so an
operator can reconstruct why a retry was executed, skipped, or blocked for
reconciliation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError

from .schema import apply_baseline_schema, target_operation, target_operation_event
from ..contracts.recovery import UnknownOutcomeResolution
from fabric_data_framework.contracts.target_operation import (
    TargetOperationAction,
    TargetOperationClaim,
    TargetOperationEvent,
    TargetOperationIntent,
    TargetOperationRecord,
    TargetOperationStatus,
    require_target_operation_transition,
)


class TargetOperationVersionConflict(RuntimeError):
    """Raised when another writer wins the operation-state compare-and-swap."""


class TargetOperationSemanticConflict(RuntimeError):
    """Raised if a stored operation key is associated with different semantics."""


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _record_from_row(row: dict[str, object]) -> TargetOperationRecord:
    return TargetOperationRecord(
        operation_key=str(row["operation_key"]),
        dataset_id=str(row["dataset_id"]),
        operation_kind=str(row["operation_kind"]),
        target_reference=str(row["target_reference"]),
        effective_config_hash=str(row["effective_config_hash"]),
        input_fingerprint=str(row["input_fingerprint"]),
        semantic_version=int(row["semantic_version"]),
        status=TargetOperationStatus(str(row["status"])),
        owner_dataset_run_id=UUID(str(row["owner_dataset_run_id"])),
        attempt=int(row["attempt"]),
        version=int(row["version"]),
        outcome_reference=(
            str(row["outcome_reference"]) if row["outcome_reference"] is not None else None
        ),
        error_code=str(row["error_code"]) if row["error_code"] is not None else None,
        error_message=(
            str(row["error_message"]) if row["error_message"] is not None else None
        ),
        created_at=_aware(row["created_at"]),
        updated_at=_aware(row["updated_at"]),
        completed_at=_aware(row["completed_at"]),
    )


def _event_from_row(row: dict[str, object]) -> TargetOperationEvent:
    from_status = row["from_status"]
    return TargetOperationEvent(
        event_id=UUID(str(row["event_id"])),
        operation_key=str(row["operation_key"]),
        from_status=(TargetOperationStatus(str(from_status)) if from_status is not None else None),
        to_status=TargetOperationStatus(str(row["to_status"])),
        owner_dataset_run_id=UUID(str(row["owner_dataset_run_id"])),
        attempt=int(row["attempt"]),
        version=int(row["version"]),
        outcome_reference=(
            str(row["outcome_reference"]) if row["outcome_reference"] is not None else None
        ),
        error_code=str(row["error_code"]) if row["error_code"] is not None else None,
        error_message=(
            str(row["error_message"]) if row["error_message"] is not None else None
        ),
        occurred_at=_aware(row["occurred_at"]),
    )


def _assert_semantic_identity(record: TargetOperationRecord, intent: TargetOperationIntent) -> None:
    if record.operation_key != intent.operation_key or record.intent != intent:
        raise TargetOperationSemanticConflict(
            "target operation semantic identity differs from the stored operation key"
        )


def _insert_event(
    connection,
    *,
    operation_key: str,
    from_status: TargetOperationStatus | None,
    to_status: TargetOperationStatus,
    owner_dataset_run_id: UUID,
    attempt: int,
    version: int,
    outcome_reference: str | None,
    error_code: str | None,
    error_message: str | None,
    occurred_at: datetime,
) -> None:
    connection.execute(
        target_operation_event.insert().values(
            event_id=str(uuid4()),
            operation_key=operation_key,
            from_status=from_status.value if from_status is not None else None,
            to_status=to_status.value,
            owner_dataset_run_id=str(owner_dataset_run_id),
            attempt=attempt,
            version=version,
            outcome_reference=outcome_reference,
            error_code=error_code,
            error_message=error_message,
            occurred_at=occurred_at,
        )
    )


def read_target_operation(engine: Engine, operation_key: str) -> TargetOperationRecord | None:
    apply_baseline_schema(engine)
    with engine.connect() as connection:
        row = connection.execute(
            select(target_operation).where(target_operation.c.operation_key == operation_key)
        ).mappings().first()
    return _record_from_row(dict(row)) if row is not None else None


def read_target_operation_events(
    engine: Engine,
    operation_key: str,
) -> tuple[TargetOperationEvent, ...]:
    apply_baseline_schema(engine)
    with engine.connect() as connection:
        rows = connection.execute(
            select(target_operation_event)
            .where(target_operation_event.c.operation_key == operation_key)
            .order_by(target_operation_event.c.version, target_operation_event.c.occurred_at)
        ).mappings().all()
    return tuple(_event_from_row(dict(row)) for row in rows)


def claim_target_operation(
    engine: Engine,
    *,
    intent: TargetOperationIntent,
    dataset_run_id: UUID,
    attempt: int,
) -> TargetOperationClaim:
    """Atomically decide whether the caller may execute a semantic target mutation.

    - unseen operation -> create ``IN_PROGRESS`` and return ``EXECUTE``;
    - ``SUCCEEDED`` -> return ``SKIP_SUCCEEDED``;
    - ``IN_PROGRESS`` or ``UNKNOWN`` -> fail closed with ``RECONCILE_REQUIRED``;
    - ``NOT_COMMITTED`` -> CAS back to ``IN_PROGRESS`` and return ``EXECUTE``.

    ``IN_PROGRESS`` is deliberately treated as uncertain on re-entry. A process may
    have died after the physical target committed but before it could record success.
    """

    if attempt < 1:
        raise ValueError("attempt must be >= 1")

    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)
    key = intent.operation_key

    try:
        with engine.begin() as connection:
            row = connection.execute(
                select(target_operation).where(target_operation.c.operation_key == key)
            ).mappings().first()

            if row is None:
                connection.execute(
                    target_operation.insert().values(
                        operation_key=key,
                        dataset_id=intent.dataset_id,
                        operation_kind=intent.operation_kind,
                        target_reference=intent.target_reference,
                        effective_config_hash=intent.effective_config_hash.lower(),
                        input_fingerprint=intent.input_fingerprint.lower(),
                        semantic_version=intent.semantic_version,
                        status=TargetOperationStatus.IN_PROGRESS.value,
                        owner_dataset_run_id=str(dataset_run_id),
                        attempt=attempt,
                        version=1,
                        outcome_reference=None,
                        error_code=None,
                        error_message=None,
                        created_at=now,
                        updated_at=None,
                        completed_at=None,
                    )
                )
                _insert_event(
                    connection,
                    operation_key=key,
                    from_status=None,
                    to_status=TargetOperationStatus.IN_PROGRESS,
                    owner_dataset_run_id=dataset_run_id,
                    attempt=attempt,
                    version=1,
                    outcome_reference=None,
                    error_code=None,
                    error_message=None,
                    occurred_at=now,
                )
                record = TargetOperationRecord(
                    operation_key=key,
                    dataset_id=intent.dataset_id,
                    operation_kind=intent.operation_kind,
                    target_reference=intent.target_reference,
                    effective_config_hash=intent.effective_config_hash.lower(),
                    input_fingerprint=intent.input_fingerprint.lower(),
                    semantic_version=intent.semantic_version,
                    status=TargetOperationStatus.IN_PROGRESS,
                    owner_dataset_run_id=dataset_run_id,
                    attempt=attempt,
                    version=1,
                    created_at=now,
                )
                return TargetOperationClaim(action=TargetOperationAction.EXECUTE, record=record)

            current = _record_from_row(dict(row))
            _assert_semantic_identity(current, intent)

            if current.status is TargetOperationStatus.SUCCEEDED:
                return TargetOperationClaim(
                    action=TargetOperationAction.SKIP_SUCCEEDED,
                    record=current,
                )
            if current.status in {
                TargetOperationStatus.IN_PROGRESS,
                TargetOperationStatus.UNKNOWN,
            }:
                return TargetOperationClaim(
                    action=TargetOperationAction.RECONCILE_REQUIRED,
                    record=current,
                )

            require_target_operation_transition(
                current.status,
                TargetOperationStatus.IN_PROGRESS,
            )
            next_version = current.version + 1
            result = connection.execute(
                target_operation.update()
                .where(
                    target_operation.c.operation_key == key,
                    target_operation.c.version == current.version,
                    target_operation.c.status == TargetOperationStatus.NOT_COMMITTED.value,
                )
                .values(
                    status=TargetOperationStatus.IN_PROGRESS.value,
                    owner_dataset_run_id=str(dataset_run_id),
                    attempt=attempt,
                    version=next_version,
                    outcome_reference=None,
                    error_code=None,
                    error_message=None,
                    updated_at=now,
                    completed_at=None,
                )
            )
            if result.rowcount != 1:
                raise TargetOperationVersionConflict(
                    f"target operation {key} changed concurrently during retry claim"
                )
            _insert_event(
                connection,
                operation_key=key,
                from_status=current.status,
                to_status=TargetOperationStatus.IN_PROGRESS,
                owner_dataset_run_id=dataset_run_id,
                attempt=attempt,
                version=next_version,
                outcome_reference=None,
                error_code=None,
                error_message=None,
                occurred_at=now,
            )

        updated = read_target_operation(engine, key)
        assert updated is not None
        return TargetOperationClaim(action=TargetOperationAction.EXECUTE, record=updated)
    except IntegrityError as exc:
        raise TargetOperationVersionConflict(
            f"target operation {key} was claimed concurrently"
        ) from exc


def transition_target_operation(
    engine: Engine,
    *,
    operation_key: str,
    expected_version: int,
    status: TargetOperationStatus,
    dataset_run_id: UUID,
    attempt: int,
    outcome_reference: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> TargetOperationRecord:
    """CAS one lifecycle transition and append immutable journal evidence."""

    if expected_version < 1:
        raise ValueError("expected_version must be >= 1")
    if attempt < 1:
        raise ValueError("attempt must be >= 1")

    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        row = connection.execute(
            select(target_operation).where(target_operation.c.operation_key == operation_key)
        ).mappings().first()
        if row is None:
            raise KeyError(f"target operation not found: {operation_key}")

        current = _record_from_row(dict(row))
        if current.version != expected_version:
            raise TargetOperationVersionConflict(
                f"target operation {operation_key} expected version {expected_version}, "
                f"current version is {current.version}"
            )
        require_target_operation_transition(current.status, status)
        next_version = current.version + 1
        completed_at = None if status is TargetOperationStatus.IN_PROGRESS else now
        result = connection.execute(
            target_operation.update()
            .where(
                target_operation.c.operation_key == operation_key,
                target_operation.c.version == expected_version,
            )
            .values(
                status=status.value,
                owner_dataset_run_id=str(dataset_run_id),
                attempt=attempt,
                version=next_version,
                outcome_reference=outcome_reference,
                error_code=error_code,
                error_message=error_message,
                updated_at=now,
                completed_at=completed_at,
            )
        )
        if result.rowcount != 1:
            raise TargetOperationVersionConflict(
                f"target operation {operation_key} changed concurrently"
            )
        _insert_event(
            connection,
            operation_key=operation_key,
            from_status=current.status,
            to_status=status,
            owner_dataset_run_id=dataset_run_id,
            attempt=attempt,
            version=next_version,
            outcome_reference=outcome_reference,
            error_code=error_code,
            error_message=error_message,
            occurred_at=now,
        )

    updated = read_target_operation(engine, operation_key)
    assert updated is not None
    return updated


def mark_target_operation_succeeded(
    engine: Engine,
    *,
    operation_key: str,
    expected_version: int,
    dataset_run_id: UUID,
    attempt: int,
    outcome_reference: str | None = None,
) -> TargetOperationRecord:
    return transition_target_operation(
        engine,
        operation_key=operation_key,
        expected_version=expected_version,
        status=TargetOperationStatus.SUCCEEDED,
        dataset_run_id=dataset_run_id,
        attempt=attempt,
        outcome_reference=outcome_reference,
    )


def mark_target_operation_unknown(
    engine: Engine,
    *,
    operation_key: str,
    expected_version: int,
    dataset_run_id: UUID,
    attempt: int,
    error_code: str = "UNKNOWN_COMMIT_OUTCOME",
    error_message: str | None = None,
    outcome_reference: str | None = None,
) -> TargetOperationRecord:
    return transition_target_operation(
        engine,
        operation_key=operation_key,
        expected_version=expected_version,
        status=TargetOperationStatus.UNKNOWN,
        dataset_run_id=dataset_run_id,
        attempt=attempt,
        outcome_reference=outcome_reference,
        error_code=error_code,
        error_message=error_message,
    )


def mark_target_operation_not_committed(
    engine: Engine,
    *,
    operation_key: str,
    expected_version: int,
    dataset_run_id: UUID,
    attempt: int,
    outcome_reference: str | None = None,
) -> TargetOperationRecord:
    return transition_target_operation(
        engine,
        operation_key=operation_key,
        expected_version=expected_version,
        status=TargetOperationStatus.NOT_COMMITTED,
        dataset_run_id=dataset_run_id,
        attempt=attempt,
        outcome_reference=outcome_reference,
    )


def reconcile_target_operation(
    engine: Engine,
    *,
    operation_key: str,
    expected_version: int,
    resolution: UnknownOutcomeResolution,
    dataset_run_id: UUID,
    attempt: int,
    outcome_reference: str | None = None,
    error_message: str | None = None,
) -> TargetOperationRecord:
    """Persist a target probe result before the recovery loop acts on it.

    ``UNRESOLVED`` is recorded as ``UNKNOWN`` and therefore still blocks blind retry.
    ``NOT_COMMITTED`` is the only reconciliation result that opens a subsequent
    ``EXECUTE`` claim. ``COMMITTED`` converges permanently to ``SUCCEEDED``.
    """

    current = read_target_operation(engine, operation_key)
    if current is None:
        raise KeyError(f"target operation not found: {operation_key}")
    if current.status is TargetOperationStatus.SUCCEEDED:
        if resolution is UnknownOutcomeResolution.COMMITTED:
            return current
        raise ValueError("SUCCEEDED target operation cannot be reconciled backwards")

    status = {
        UnknownOutcomeResolution.COMMITTED: TargetOperationStatus.SUCCEEDED,
        UnknownOutcomeResolution.NOT_COMMITTED: TargetOperationStatus.NOT_COMMITTED,
        UnknownOutcomeResolution.UNRESOLVED: TargetOperationStatus.UNKNOWN,
    }[resolution]
    return transition_target_operation(
        engine,
        operation_key=operation_key,
        expected_version=expected_version,
        status=status,
        dataset_run_id=dataset_run_id,
        attempt=attempt,
        outcome_reference=outcome_reference,
        error_code=("UNKNOWN_COMMIT_UNRESOLVED" if resolution is UnknownOutcomeResolution.UNRESOLVED else None),
        error_message=error_message,
    )


__all__ = [
    "TargetOperationSemanticConflict",
    "TargetOperationVersionConflict",
    "claim_target_operation",
    "mark_target_operation_not_committed",
    "mark_target_operation_succeeded",
    "mark_target_operation_unknown",
    "read_target_operation",
    "read_target_operation_events",
    "reconcile_target_operation",
    "transition_target_operation",
]
