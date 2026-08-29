"""Durable relational target-operation journal with optimistic concurrency."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError

from .contracts.target_operation import (
    TargetOperationJournalEntry,
    TargetOperationSpec,
    TargetOperationStatus,
    validate_target_operation_transition,
)
from .control_plane import apply_baseline_schema, target_operation


class TargetOperationIdentityConflict(RuntimeError):
    """Raised when one operation key is associated with different semantics."""


class TargetOperationVersionConflict(RuntimeError):
    """Raised when a stale writer loses an optimistic-concurrency race."""


class TargetOperationTransitionConflict(RuntimeError):
    """Raised when an idempotent-looking transition carries conflicting evidence."""


def _entry_from_row(row: dict[str, object]) -> TargetOperationJournalEntry:
    return TargetOperationJournalEntry(
        operation_key=str(row["operation_key"]),
        dataset_id=str(row["dataset_id"]),
        run_mode=str(row["run_mode"]),
        apply_strategy=str(row["apply_strategy"]),
        target_reference=str(row["target_reference"]),
        effective_config_hash=str(row["effective_config_hash"]),
        mutation_scope_hash=str(row["mutation_scope_hash"]),
        first_dataset_run_id=UUID(str(row["first_dataset_run_id"])),
        last_dataset_run_id=UUID(str(row["last_dataset_run_id"])),
        status=str(row["status"]),
        attempts_started=int(row["attempts_started"]),
        outcome_reference=(
            str(row["outcome_reference"]) if row["outcome_reference"] is not None else None
        ),
        last_error_code=(
            str(row["last_error_code"]) if row["last_error_code"] is not None else None
        ),
        last_error_message=(
            str(row["last_error_message"])
            if row["last_error_message"] is not None
            else None
        ),
        version=int(row["version"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        committed_at=row["committed_at"],
    )


def _assert_identity(entry: TargetOperationJournalEntry, spec: TargetOperationSpec) -> None:
    if not entry.matches(spec):
        raise TargetOperationIdentityConflict(
            f"target operation key {spec.operation_key} already exists with different semantics"
        )


def read_target_operation(
    engine: Engine,
    operation_key: str,
) -> TargetOperationJournalEntry | None:
    apply_baseline_schema(engine)
    with engine.connect() as connection:
        row = connection.execute(
            select(target_operation).where(
                target_operation.c.operation_key == operation_key
            )
        ).mappings().first()
    return _entry_from_row(dict(row)) if row is not None else None


def reserve_target_operation(
    engine: Engine,
    spec: TargetOperationSpec,
    *,
    dataset_run_id: UUID,
) -> TargetOperationJournalEntry:
    """Reserve a stable semantic mutation before any target write.

    Exact repeat is idempotent. A concurrent insert may race on the primary key; in
    that case the winner is re-read and accepted only when its semantic identity is
    exactly the same.
    """

    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)
    values = {
        "operation_key": spec.operation_key,
        "dataset_id": spec.dataset_id,
        "run_mode": spec.run_mode.value,
        "apply_strategy": spec.apply_strategy.value,
        "target_reference": spec.target_reference,
        "effective_config_hash": spec.effective_config_hash,
        "mutation_scope_hash": spec.mutation_scope_hash,
        "first_dataset_run_id": str(dataset_run_id),
        "last_dataset_run_id": str(dataset_run_id),
        "status": TargetOperationStatus.PREPARED.value,
        "attempts_started": 0,
        "outcome_reference": None,
        "last_error_code": None,
        "last_error_message": None,
        "version": 1,
        "committed_at": None,
        "created_at": now,
        "updated_at": None,
    }

    try:
        with engine.begin() as connection:
            row = connection.execute(
                select(target_operation).where(
                    target_operation.c.operation_key == spec.operation_key
                )
            ).mappings().first()
            if row is not None:
                entry = _entry_from_row(dict(row))
                _assert_identity(entry, spec)
                return entry
            connection.execute(target_operation.insert().values(**values))
    except IntegrityError:
        winner = read_target_operation(engine, spec.operation_key)
        if winner is None:
            raise
        _assert_identity(winner, spec)
        return winner

    return TargetOperationJournalEntry(
        operation_key=spec.operation_key,
        dataset_id=spec.dataset_id,
        run_mode=spec.run_mode,
        apply_strategy=spec.apply_strategy,
        target_reference=spec.target_reference,
        effective_config_hash=spec.effective_config_hash,
        mutation_scope_hash=spec.mutation_scope_hash,
        first_dataset_run_id=dataset_run_id,
        last_dataset_run_id=dataset_run_id,
        status=TargetOperationStatus.PREPARED,
        attempts_started=0,
        version=1,
        created_at=now,
    )


def transition_target_operation(
    engine: Engine,
    *,
    operation_key: str,
    expected_version: int,
    status: TargetOperationStatus,
    dataset_run_id: UUID,
    outcome_reference: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> TargetOperationJournalEntry:
    """Advance one journal lifecycle using compare-and-swap semantics."""

    if expected_version < 1:
        raise ValueError("expected_version must be >= 1")
    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)

    with engine.begin() as connection:
        row = connection.execute(
            select(target_operation).where(
                target_operation.c.operation_key == operation_key
            )
        ).mappings().first()
        if row is None:
            raise KeyError(f"target operation not found: {operation_key}")

        current = _entry_from_row(dict(row))
        if current.version != expected_version:
            raise TargetOperationVersionConflict(
                f"target operation {operation_key} expected version {expected_version}, "
                f"current version is {current.version}"
            )

        if current.status is status:
            if status is not TargetOperationStatus.COMMITTED and (
                current.last_dataset_run_id != dataset_run_id
            ):
                raise TargetOperationTransitionConflict(
                    f"target operation {operation_key} is already {status.value} under "
                    f"dataset run {current.last_dataset_run_id}"
                )
            for label, supplied, existing in (
                ("outcome_reference", outcome_reference, current.outcome_reference),
                ("error_code", error_code, current.last_error_code),
                ("error_message", error_message, current.last_error_message),
            ):
                if supplied is not None and supplied != existing:
                    raise TargetOperationTransitionConflict(
                        f"idempotent {status.value} transition conflicts on {label}"
                    )
            return current

        validate_target_operation_transition(current.status, status)
        next_version = current.version + 1
        attempts_started = current.attempts_started + (
            1 if status is TargetOperationStatus.IN_PROGRESS else 0
        )
        committed_at = now if status is TargetOperationStatus.COMMITTED else None
        result = connection.execute(
            target_operation.update()
            .where(
                target_operation.c.operation_key == operation_key,
                target_operation.c.version == expected_version,
            )
            .values(
                last_dataset_run_id=str(dataset_run_id),
                status=status.value,
                attempts_started=attempts_started,
                outcome_reference=outcome_reference,
                last_error_code=(
                    error_code if error_code is not None else current.last_error_code
                ),
                last_error_message=(
                    error_message
                    if error_message is not None
                    else current.last_error_message
                ),
                version=next_version,
                committed_at=committed_at,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            raise TargetOperationVersionConflict(
                f"target operation {operation_key} changed concurrently"
            )
        updated = connection.execute(
            select(target_operation).where(
                target_operation.c.operation_key == operation_key
            )
        ).mappings().one()

    return _entry_from_row(dict(updated))


class RelationalTargetOperationJournal:
    """Small Engine-backed journal adapter pending the final production repository."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def reserve(
        self,
        spec: TargetOperationSpec,
        *,
        dataset_run_id: UUID,
    ) -> TargetOperationJournalEntry:
        return reserve_target_operation(
            self.engine,
            spec,
            dataset_run_id=dataset_run_id,
        )

    def read(self, operation_key: str) -> TargetOperationJournalEntry | None:
        return read_target_operation(self.engine, operation_key)

    def transition(
        self,
        *,
        operation_key: str,
        expected_version: int,
        status: TargetOperationStatus,
        dataset_run_id: UUID,
        outcome_reference: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> TargetOperationJournalEntry:
        return transition_target_operation(
            self.engine,
            operation_key=operation_key,
            expected_version=expected_version,
            status=status,
            dataset_run_id=dataset_run_id,
            outcome_reference=outcome_reference,
            error_code=error_code,
            error_message=error_message,
        )


__all__ = [
    "RelationalTargetOperationJournal",
    "TargetOperationIdentityConflict",
    "TargetOperationTransitionConflict",
    "TargetOperationVersionConflict",
    "read_target_operation",
    "reserve_target_operation",
    "transition_target_operation",
]
