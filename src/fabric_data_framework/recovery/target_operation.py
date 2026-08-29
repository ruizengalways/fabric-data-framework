"""Durable target-operation coordination layered over dataset retry semantics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from ..contracts.recovery import ReprocessRequest, UnknownOutcomeResolution
from ..contracts.target_operation import (
    TargetOperationJournalEntry,
    TargetOperationReconciliation,
    TargetOperationSpec,
    TargetOperationStatus,
)
from .runtime import (
    AttemptContext,
    PermanentExecutionError,
    RecoveryRepository,
    RecoveryRunResult,
    RetryPolicy,
    RetryableExecutionError,
    UnknownCommitOutcomeError,
    execute_with_retry,
)

T = TypeVar("T")


class TargetOperationJournal(Protocol):
    def reserve(
        self,
        spec: TargetOperationSpec,
        *,
        dataset_run_id: UUID,
    ) -> TargetOperationJournalEntry: ...

    def read(self, operation_key: str) -> TargetOperationJournalEntry | None: ...

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
    ) -> TargetOperationJournalEntry: ...


class TargetOperationUnresolvedError(RuntimeError):
    """The target may already be mutated; re-execution is forbidden until reconciled."""


class TargetOperationTerminalError(RuntimeError):
    """A semantically identical operation is in a terminal non-success state."""


@dataclass(frozen=True)
class TargetOperationExecutionResult(Generic[T]):
    value: T | None
    operation: TargetOperationJournalEntry
    mutation_executed: bool
    converged_without_reexecution: bool
    unknown_outcome_resolution: UnknownOutcomeResolution | None = None


def _transition(
    journal: TargetOperationJournal,
    entry: TargetOperationJournalEntry,
    *,
    status: TargetOperationStatus,
    dataset_run_id: UUID,
    outcome_reference: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> TargetOperationJournalEntry:
    return journal.transition(
        operation_key=entry.operation_key,
        expected_version=entry.version,
        status=status,
        dataset_run_id=dataset_run_id,
        outcome_reference=outcome_reference,
        error_code=error_code,
        error_message=error_message,
    )


def _apply_reconciliation(
    journal: TargetOperationJournal,
    entry: TargetOperationJournalEntry,
    *,
    dataset_run_id: UUID,
    reconcile_unknown: Callable[[TargetOperationJournalEntry], TargetOperationReconciliation] | None,
    mutation_executed: bool,
) -> TargetOperationExecutionResult[object] | TargetOperationJournalEntry:
    if reconcile_unknown is None:
        if entry.status is TargetOperationStatus.IN_PROGRESS:
            entry = _transition(
                journal,
                entry,
                status=TargetOperationStatus.COMMIT_UNKNOWN,
                dataset_run_id=dataset_run_id,
                error_code="RECOVERED_IN_PROGRESS_WITHOUT_OUTCOME",
                error_message=(
                    "prior target operation was IN_PROGRESS; outcome must be reconciled "
                    "before re-execution"
                ),
            )
        raise TargetOperationUnresolvedError(
            f"target operation {entry.operation_key} has uncertain commit outcome"
        )

    reconciliation = reconcile_unknown(entry)
    if reconciliation.resolution is UnknownOutcomeResolution.COMMITTED:
        committed = _transition(
            journal,
            entry,
            status=TargetOperationStatus.COMMITTED,
            dataset_run_id=dataset_run_id,
            outcome_reference=reconciliation.evidence_reference,
        )
        return TargetOperationExecutionResult(
            value=None,
            operation=committed,
            mutation_executed=mutation_executed,
            converged_without_reexecution=not mutation_executed,
            unknown_outcome_resolution=reconciliation.resolution,
        )

    if reconciliation.resolution is UnknownOutcomeResolution.NOT_COMMITTED:
        return _transition(
            journal,
            entry,
            status=TargetOperationStatus.NOT_COMMITTED,
            dataset_run_id=dataset_run_id,
            outcome_reference=reconciliation.evidence_reference,
        )

    if entry.status is TargetOperationStatus.IN_PROGRESS:
        _transition(
            journal,
            entry,
            status=TargetOperationStatus.COMMIT_UNKNOWN,
            dataset_run_id=dataset_run_id,
            outcome_reference=reconciliation.evidence_reference,
            error_code="TARGET_COMMIT_UNRESOLVED",
            error_message="target reconciliation could not determine commit outcome",
        )
    raise TargetOperationUnresolvedError(
        f"target operation {entry.operation_key} commit outcome remains unresolved"
    )


def execute_target_operation_once(
    *,
    journal: TargetOperationJournal,
    spec: TargetOperationSpec,
    dataset_run_id: UUID,
    execute_mutation: Callable[[TargetOperationJournalEntry], T],
    reconcile_unknown: (
        Callable[[TargetOperationJournalEntry], TargetOperationReconciliation] | None
    ) = None,
) -> TargetOperationExecutionResult[T]:
    """Execute or converge one semantic target mutation without blind re-execution.

    The journal reservation happens before mutation. A pre-existing COMMITTED entry
    converges immediately. A pre-existing IN_PROGRESS/COMMIT_UNKNOWN entry is treated
    as uncertain across process/attempt boundaries and must be reconciled first.
    """

    entry = journal.reserve(spec, dataset_run_id=dataset_run_id)

    if entry.status is TargetOperationStatus.COMMITTED:
        return TargetOperationExecutionResult(
            value=None,
            operation=entry,
            mutation_executed=False,
            converged_without_reexecution=True,
        )
    if entry.status is TargetOperationStatus.FAILED:
        raise TargetOperationTerminalError(
            f"target operation {entry.operation_key} is terminal FAILED"
        )

    if entry.status in {
        TargetOperationStatus.IN_PROGRESS,
        TargetOperationStatus.COMMIT_UNKNOWN,
    }:
        reconciled = _apply_reconciliation(
            journal,
            entry,
            dataset_run_id=dataset_run_id,
            reconcile_unknown=reconcile_unknown,
            mutation_executed=False,
        )
        if isinstance(reconciled, TargetOperationExecutionResult):
            return reconciled
        entry = reconciled

    if entry.status not in {
        TargetOperationStatus.PREPARED,
        TargetOperationStatus.NOT_COMMITTED,
    }:
        raise TargetOperationTerminalError(
            f"target operation {entry.operation_key} cannot start from {entry.status.value}"
        )

    entry = _transition(
        journal,
        entry,
        status=TargetOperationStatus.IN_PROGRESS,
        dataset_run_id=dataset_run_id,
    )

    try:
        value = execute_mutation(entry)
    except RetryableExecutionError as exc:
        _transition(
            journal,
            entry,
            status=TargetOperationStatus.NOT_COMMITTED,
            dataset_run_id=dataset_run_id,
            error_code=exc.error_code,
            error_message=str(exc),
        )
        raise
    except PermanentExecutionError as exc:
        _transition(
            journal,
            entry,
            status=TargetOperationStatus.FAILED,
            dataset_run_id=dataset_run_id,
            error_code=exc.error_code,
            error_message=str(exc),
        )
        raise
    except UnknownCommitOutcomeError as exc:
        unknown = _transition(
            journal,
            entry,
            status=TargetOperationStatus.COMMIT_UNKNOWN,
            dataset_run_id=dataset_run_id,
            error_code=exc.error_code,
            error_message=str(exc),
        )
        reconciled = _apply_reconciliation(
            journal,
            unknown,
            dataset_run_id=dataset_run_id,
            reconcile_unknown=reconcile_unknown,
            mutation_executed=True,
        )
        if isinstance(reconciled, TargetOperationExecutionResult):
            return reconciled
        raise RetryableExecutionError(
            "target reconciliation proved mutation was not committed",
            error_code="TARGET_NOT_COMMITTED_AFTER_UNKNOWN",
        ) from exc
    except Exception as exc:
        unknown = _transition(
            journal,
            entry,
            status=TargetOperationStatus.COMMIT_UNKNOWN,
            dataset_run_id=dataset_run_id,
            error_code="UNCLASSIFIED_TARGET_MUTATION_EXCEPTION",
            error_message=str(exc) or exc.__class__.__name__,
        )
        reconciled = _apply_reconciliation(
            journal,
            unknown,
            dataset_run_id=dataset_run_id,
            reconcile_unknown=reconcile_unknown,
            mutation_executed=True,
        )
        if isinstance(reconciled, TargetOperationExecutionResult):
            return reconciled
        raise RetryableExecutionError(
            "target reconciliation proved mutation was not committed",
            error_code="TARGET_NOT_COMMITTED_AFTER_UNKNOWN",
        ) from exc

    committed = _transition(
        journal,
        entry,
        status=TargetOperationStatus.COMMITTED,
        dataset_run_id=dataset_run_id,
    )
    return TargetOperationExecutionResult(
        value=value,
        operation=committed,
        mutation_executed=True,
        converged_without_reexecution=False,
    )


def execute_target_operation_with_retry(
    *,
    repository: RecoveryRepository,
    journal: TargetOperationJournal,
    pipeline_run_id: UUID,
    spec: TargetOperationSpec,
    execute_mutation: Callable[[AttemptContext, TargetOperationJournalEntry], T],
    retry_policy: RetryPolicy | None = None,
    reprocess_request: ReprocessRequest | None = None,
    reconcile_unknown: (
        Callable[
            [AttemptContext, TargetOperationJournalEntry],
            TargetOperationReconciliation,
        ]
        | None
    ) = None,
    backoff: Callable[[float], None] | None = None,
    initial_attempt: int = 1,
    root_dataset_run_id: UUID | None = None,
    previous_dataset_run_id: UUID | None = None,
) -> RecoveryRunResult[TargetOperationExecutionResult[T]]:
    """Run dataset retries while keeping one stable target operation key.

    Every new dataset attempt receives a new ``dataset_run_id`` from the existing
    recovery runtime, but all attempts reserve/transition the same semantic operation.
    Only NOT_COMMITTED may be re-issued. COMMITTED converges without mutation and
    uncertain prior attempts require explicit reconciliation.
    """

    def execute_attempt(context: AttemptContext) -> TargetOperationExecutionResult[T]:
        resolver = (
            (lambda entry: reconcile_unknown(context, entry))
            if reconcile_unknown is not None
            else None
        )
        return execute_target_operation_once(
            journal=journal,
            spec=spec,
            dataset_run_id=context.dataset_run_id,
            execute_mutation=lambda entry: execute_mutation(context, entry),
            reconcile_unknown=resolver,
        )

    return execute_with_retry(
        repository=repository,
        pipeline_run_id=pipeline_run_id,
        dataset_id=spec.dataset_id,
        effective_config_hash=spec.effective_config_hash,
        execute_attempt=execute_attempt,
        retry_policy=retry_policy,
        run_mode=spec.run_mode,
        reprocess_request=reprocess_request,
        backoff=backoff,
        initial_attempt=initial_attempt,
        root_dataset_run_id=root_dataset_run_id,
        previous_dataset_run_id=previous_dataset_run_id,
    )


__all__ = [
    "TargetOperationExecutionResult",
    "TargetOperationJournal",
    "TargetOperationTerminalError",
    "TargetOperationUnresolvedError",
    "execute_target_operation_once",
    "execute_target_operation_with_retry",
]
