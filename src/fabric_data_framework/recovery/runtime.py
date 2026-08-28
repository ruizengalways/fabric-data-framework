"""Fail-closed retry and unknown-outcome recovery runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Generic, Protocol, TypeVar
from uuid import UUID, uuid4

from pydantic import Field

from ..config import DatasetStatus, FrozenModel, RunMode
from ..contracts.recovery import (
    DatasetAttemptLineage,
    ReprocessRequest,
    ReprocessRequestStatus,
    UnknownOutcomeResolution,
)
from ..operations import DatasetRunAudit


T = TypeVar("T")


class FailureDisposition(str, Enum):
    RETRYABLE = "RETRYABLE"
    NON_RETRYABLE = "NON_RETRYABLE"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"


class FailureClassification(FrozenModel):
    disposition: FailureDisposition
    error_code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class RetryPolicy(FrozenModel):
    max_attempts: int = Field(default=3, ge=1)
    initial_backoff_seconds: float = Field(default=1.0, ge=0)
    multiplier: float = Field(default=2.0, ge=1)
    max_backoff_seconds: float = Field(default=60.0, ge=0)

    def delay_after_attempt(self, attempt: int) -> float:
        """Delay before the next attempt after a failed 1-based attempt."""

        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        delay = self.initial_backoff_seconds * (self.multiplier ** (attempt - 1))
        return min(delay, self.max_backoff_seconds)


class RetryableExecutionError(RuntimeError):
    def __init__(self, message: str, *, error_code: str = "TRANSIENT_FAILURE") -> None:
        super().__init__(message)
        self.error_code = error_code


class PermanentExecutionError(RuntimeError):
    def __init__(self, message: str, *, error_code: str = "PERMANENT_FAILURE") -> None:
        super().__init__(message)
        self.error_code = error_code


class UnknownCommitOutcomeError(RuntimeError):
    """Target mutation may have committed but the caller cannot prove the outcome."""

    def __init__(self, message: str, *, error_code: str = "UNKNOWN_COMMIT_OUTCOME") -> None:
        super().__init__(message)
        self.error_code = error_code


class RecoveryExhaustedError(RuntimeError):
    def __init__(self, message: str, *, last_error: BaseException) -> None:
        super().__init__(message)
        self.last_error = last_error


class UnknownOutcomeUnresolvedError(RuntimeError):
    pass


class RecoveryRepository(Protocol):
    def record_dataset_run(self, audit: DatasetRunAudit) -> None: ...
    def record_attempt_lineage(self, lineage: DatasetAttemptLineage) -> None: ...
    def record_reprocess_request(self, request: ReprocessRequest) -> None: ...


@dataclass(frozen=True)
class AttemptContext:
    pipeline_run_id: UUID
    dataset_run_id: UUID
    dataset_id: str
    root_dataset_run_id: UUID
    previous_dataset_run_id: UUID | None
    attempt: int
    run_mode: RunMode
    reprocess_request_id: UUID | None


@dataclass(frozen=True)
class RecoveryRunResult(Generic[T]):
    value: T | None
    dataset_run_id: UUID
    root_dataset_run_id: UUID
    attempts: int
    resolved_unknown_outcome: UnknownOutcomeResolution | None = None


def classify_failure(exc: BaseException) -> FailureClassification:
    """Conservatively classify failures; unknown exceptions are not auto-retried."""

    if isinstance(exc, RetryableExecutionError):
        return FailureClassification(
            disposition=FailureDisposition.RETRYABLE,
            error_code=exc.error_code,
            message=str(exc),
        )
    if isinstance(exc, UnknownCommitOutcomeError):
        return FailureClassification(
            disposition=FailureDisposition.UNKNOWN_OUTCOME,
            error_code=exc.error_code,
            message=str(exc),
        )
    if isinstance(exc, PermanentExecutionError):
        return FailureClassification(
            disposition=FailureDisposition.NON_RETRYABLE,
            error_code=exc.error_code,
            message=str(exc),
        )
    return FailureClassification(
        disposition=FailureDisposition.NON_RETRYABLE,
        error_code="UNCLASSIFIED_FAILURE",
        message=str(exc) or exc.__class__.__name__,
    )


def _record_terminal_audit(
    repository: RecoveryRepository,
    *,
    context: AttemptContext,
    effective_config_hash: str,
    status: DatasetStatus,
    error_code: str | None = None,
    error_message: str | None = None,
    retryable: bool | None = None,
) -> None:
    repository.record_dataset_run(
        DatasetRunAudit(
            dataset_run_id=context.dataset_run_id,
            pipeline_run_id=context.pipeline_run_id,
            dataset_id=context.dataset_id,
            attempt=context.attempt,
            run_mode=context.run_mode,
            status=status,
            effective_config_hash=effective_config_hash,
            error_code=error_code,
            error_message=error_message,
            retryable=retryable,
        )
    )


def _update_reprocess_status(
    repository: RecoveryRepository,
    request: ReprocessRequest | None,
    status: ReprocessRequestStatus,
) -> ReprocessRequest | None:
    if request is None:
        return None
    updated = request.model_copy(update={"status": status})
    repository.record_reprocess_request(updated)
    return updated


def execute_with_retry(
    *,
    repository: RecoveryRepository,
    pipeline_run_id: UUID,
    dataset_id: str,
    effective_config_hash: str,
    execute_attempt: Callable[[AttemptContext], T],
    retry_policy: RetryPolicy | None = None,
    run_mode: RunMode = RunMode.NORMAL,
    reprocess_request: ReprocessRequest | None = None,
    resolve_unknown_outcome: (
        Callable[[AttemptContext, UnknownCommitOutcomeError], UnknownOutcomeResolution] | None
    ) = None,
    backoff: Callable[[float], None] | None = None,
    initial_attempt: int = 1,
    root_dataset_run_id: UUID | None = None,
    previous_dataset_run_id: UUID | None = None,
) -> RecoveryRunResult[T]:
    """Execute bounded attempts while preserving immutable attempt lineage.

    Automatic retries are permitted only for explicitly retryable failures.  An
    uncertain target commit is reconciled before any retry.  COMMITTED converges to
    success, NOT_COMMITTED may retry, and UNRESOLVED stops to avoid duplicate writes.
    """

    if initial_attempt < 1:
        raise ValueError("initial_attempt must be >= 1")
    if initial_attempt == 1:
        if root_dataset_run_id is not None or previous_dataset_run_id is not None:
            raise ValueError("attempt 1 cannot provide prior lineage")
    elif root_dataset_run_id is None or previous_dataset_run_id is None:
        raise ValueError("continuing attempts requires root and previous dataset run ids")

    if run_mode is RunMode.NORMAL:
        if reprocess_request is not None:
            raise ValueError("NORMAL run cannot attach a reprocess request")
    else:
        if reprocess_request is None:
            raise ValueError(f"{run_mode.value} run requires a ReprocessRequest")
        if reprocess_request.run_mode is not run_mode:
            raise ValueError("reprocess request run_mode must match execution run_mode")
        if reprocess_request.dataset_id != dataset_id:
            raise ValueError("reprocess request dataset_id must match execution dataset_id")

    policy = retry_policy or RetryPolicy()
    backoff_fn = backoff or (lambda _seconds: None)
    active_request = _update_reprocess_status(
        repository, reprocess_request, ReprocessRequestStatus.RUNNING
    )

    first_new_run_id: UUID | None = None
    root_id = root_dataset_run_id
    previous_id = previous_dataset_run_id
    last_error: BaseException | None = None

    for offset in range(policy.max_attempts):
        attempt = initial_attempt + offset
        dataset_run_id = uuid4()
        if first_new_run_id is None:
            first_new_run_id = dataset_run_id
        if root_id is None:
            root_id = dataset_run_id
        context = AttemptContext(
            pipeline_run_id=pipeline_run_id,
            dataset_run_id=dataset_run_id,
            dataset_id=dataset_id,
            root_dataset_run_id=root_id,
            previous_dataset_run_id=previous_id,
            attempt=attempt,
            run_mode=run_mode,
            reprocess_request_id=(
                active_request.reprocess_request_id if active_request is not None else None
            ),
        )
        repository.record_attempt_lineage(
            DatasetAttemptLineage(
                dataset_run_id=dataset_run_id,
                dataset_id=dataset_id,
                root_dataset_run_id=root_id,
                previous_dataset_run_id=previous_id,
                attempt=attempt,
                run_mode=run_mode,
                reprocess_request_id=context.reprocess_request_id,
            )
        )

        try:
            value = execute_attempt(context)
        except BaseException as exc:  # executor boundary must finalize every attempt
            last_error = exc
            classification = classify_failure(exc)

            if classification.disposition is FailureDisposition.UNKNOWN_OUTCOME:
                if resolve_unknown_outcome is None:
                    _record_terminal_audit(
                        repository,
                        context=context,
                        effective_config_hash=effective_config_hash,
                        status=DatasetStatus.FAILED,
                        error_code="UNKNOWN_COMMIT_UNRESOLVED",
                        error_message=classification.message,
                        retryable=False,
                    )
                    _update_reprocess_status(
                        repository, active_request, ReprocessRequestStatus.FAILED
                    )
                    raise UnknownOutcomeUnresolvedError(
                        "unknown commit outcome requires reconciliation before retry"
                    ) from exc

                resolution = resolve_unknown_outcome(context, exc)
                if resolution is UnknownOutcomeResolution.COMMITTED:
                    _record_terminal_audit(
                        repository,
                        context=context,
                        effective_config_hash=effective_config_hash,
                        status=DatasetStatus.SUCCEEDED,
                    )
                    _update_reprocess_status(
                        repository, active_request, ReprocessRequestStatus.SUCCEEDED
                    )
                    return RecoveryRunResult(
                        value=None,
                        dataset_run_id=dataset_run_id,
                        root_dataset_run_id=root_id,
                        attempts=offset + 1,
                        resolved_unknown_outcome=resolution,
                    )
                if resolution is UnknownOutcomeResolution.UNRESOLVED:
                    _record_terminal_audit(
                        repository,
                        context=context,
                        effective_config_hash=effective_config_hash,
                        status=DatasetStatus.FAILED,
                        error_code="UNKNOWN_COMMIT_UNRESOLVED",
                        error_message=classification.message,
                        retryable=False,
                    )
                    _update_reprocess_status(
                        repository, active_request, ReprocessRequestStatus.FAILED
                    )
                    raise UnknownOutcomeUnresolvedError(
                        "target commit outcome remains unresolved; refusing blind retry"
                    ) from exc

                classification = FailureClassification(
                    disposition=FailureDisposition.RETRYABLE,
                    error_code="UNKNOWN_COMMIT_NOT_COMMITTED",
                    message=classification.message,
                )

            can_retry = (
                classification.disposition is FailureDisposition.RETRYABLE
                and offset + 1 < policy.max_attempts
            )
            _record_terminal_audit(
                repository,
                context=context,
                effective_config_hash=effective_config_hash,
                status=DatasetStatus.FAILED,
                error_code=classification.error_code,
                error_message=classification.message,
                retryable=can_retry,
            )
            if not can_retry:
                _update_reprocess_status(
                    repository, active_request, ReprocessRequestStatus.FAILED
                )
                if classification.disposition is FailureDisposition.RETRYABLE:
                    raise RecoveryExhaustedError(
                        f"retry attempts exhausted for {dataset_id}",
                        last_error=exc,
                    ) from exc
                raise

            backoff_fn(policy.delay_after_attempt(attempt))
            previous_id = dataset_run_id
            continue

        _record_terminal_audit(
            repository,
            context=context,
            effective_config_hash=effective_config_hash,
            status=DatasetStatus.SUCCEEDED,
        )
        _update_reprocess_status(
            repository, active_request, ReprocessRequestStatus.SUCCEEDED
        )
        return RecoveryRunResult(
            value=value,
            dataset_run_id=dataset_run_id,
            root_dataset_run_id=root_id,
            attempts=offset + 1,
        )

    assert last_error is not None
    raise RecoveryExhaustedError(
        f"retry attempts exhausted for {dataset_id}",
        last_error=last_error,
    )


__all__ = [
    "AttemptContext",
    "FailureClassification",
    "FailureDisposition",
    "PermanentExecutionError",
    "RecoveryExhaustedError",
    "RecoveryRunResult",
    "RetryPolicy",
    "RetryableExecutionError",
    "UnknownCommitOutcomeError",
    "UnknownOutcomeUnresolvedError",
    "classify_failure",
    "execute_with_retry",
]
