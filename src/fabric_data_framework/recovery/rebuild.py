"""Fail-closed FULL_REBUILD coordination.

FULL_REBUILD is intentionally not implemented as "delete target + delete checkpoint".
The rebuild callback receives a stable request identity for idempotent destructive work,
and capture-aware runtime state is cut over only after the rebuilt target is committed
and required reconciliation passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, Generic, TypeVar
from uuid import UUID

from ..config import RunMode
from ..contracts.rebuild import (
    FullRebuildStateAdapter,
    FullRebuildStateReplacement,
    FullRebuildStateSnapshot,
)
from ..contracts.recovery import ReprocessRequest
from ..runtime import StateCommitGate


T = TypeVar("T")


class FullRebuildError(RuntimeError):
    """Base FULL_REBUILD orchestration error."""


class FullRebuildGateError(FullRebuildError):
    """Rebuild cannot cut over runtime state because target evidence is insufficient."""


class FullRebuildStateVersionConflict(FullRebuildError):
    """Runtime state changed after rebuild preparation; fail rather than overwrite it."""


@dataclass(frozen=True)
class FullRebuildContext:
    dataset_id: str
    rebuild_request_id: UUID
    dataset_run_id: UUID
    before_state: FullRebuildStateSnapshot


@dataclass(frozen=True)
class FullRebuildMutationOutcome(Generic[T]):
    value: T
    authoritative_rebuild_completed: bool
    gate: StateCommitGate
    state_replacement: FullRebuildStateReplacement


@dataclass(frozen=True)
class FullRebuildResult(Generic[T]):
    value: T | None
    rebuild_request_id: UUID
    dataset_run_id: UUID
    state: FullRebuildStateSnapshot
    already_rebuilt: bool = False


class InMemoryFullRebuildStateAdapter:
    """Deterministic reference implementation of optimistic rebuild state cutover."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._states: dict[str, FullRebuildStateSnapshot] = {}

    def seed_state(
        self,
        dataset_id: str,
        replacement: FullRebuildStateReplacement | None,
    ) -> FullRebuildStateSnapshot:
        with self._lock:
            current = self._states.get(dataset_id)
            version = current.version + 1 if current is not None else 1
            state = FullRebuildStateSnapshot(
                dataset_id=dataset_id,
                version=version,
                replacement=replacement,
            )
            self._states[dataset_id] = state
            return state

    def read_state(self, dataset_id: str) -> FullRebuildStateSnapshot:
        with self._lock:
            return self._states.get(
                dataset_id,
                FullRebuildStateSnapshot(dataset_id=dataset_id, version=0),
            )

    def commit_rebuild_state(
        self,
        *,
        dataset_id: str,
        expected_version: int,
        rebuild_request_id: UUID,
        dataset_run_id: UUID,
        replacement: FullRebuildStateReplacement,
    ) -> FullRebuildStateSnapshot:
        with self._lock:
            current = self._states.get(
                dataset_id,
                FullRebuildStateSnapshot(dataset_id=dataset_id, version=0),
            )
            if current.last_rebuild_request_id == rebuild_request_id:
                return current
            if current.version != expected_version:
                raise FullRebuildStateVersionConflict(
                    f"FULL_REBUILD state {dataset_id} expected version {expected_version}, "
                    f"current version is {current.version}"
                )
            next_state = FullRebuildStateSnapshot(
                dataset_id=dataset_id,
                version=current.version + 1,
                replacement=replacement,
                last_rebuild_request_id=rebuild_request_id,
                last_rebuild_dataset_run_id=dataset_run_id,
            )
            self._states[dataset_id] = next_state
            return next_state


def prepare_full_rebuild(
    *,
    request: ReprocessRequest,
    dataset_run_id: UUID,
    state_adapter: FullRebuildStateAdapter,
) -> tuple[FullRebuildContext, bool]:
    """Validate destructive intent and snapshot optimistic runtime-state version."""

    if request.run_mode is not RunMode.FULL_REBUILD:
        raise FullRebuildError("FULL_REBUILD execution requires a FULL_REBUILD request")
    if (request.range_json or {}).get("authoritative_reset") is not True:
        raise FullRebuildError("FULL_REBUILD requires explicit authoritative_reset=true")

    before = state_adapter.read_state(request.dataset_id)
    already_rebuilt = before.last_rebuild_request_id == request.reprocess_request_id
    return (
        FullRebuildContext(
            dataset_id=request.dataset_id,
            rebuild_request_id=request.reprocess_request_id,
            dataset_run_id=dataset_run_id,
            before_state=before,
        ),
        already_rebuilt,
    )


def execute_full_rebuild(
    *,
    request: ReprocessRequest,
    dataset_run_id: UUID,
    state_adapter: FullRebuildStateAdapter,
    execute_rebuild: Callable[[FullRebuildContext], FullRebuildMutationOutcome[T]],
) -> FullRebuildResult[T]:
    """Execute an authoritative rebuild then atomically cut over runtime state.

    ``rebuild_request_id`` is stable across retry attempts and MUST be used by a
    physical target adapter as its idempotency/rebuild identity. ``dataset_run_id`` is
    attempt-specific audit evidence only.
    """

    context, already_rebuilt = prepare_full_rebuild(
        request=request,
        dataset_run_id=dataset_run_id,
        state_adapter=state_adapter,
    )
    if already_rebuilt:
        return FullRebuildResult(
            value=None,
            rebuild_request_id=context.rebuild_request_id,
            dataset_run_id=dataset_run_id,
            state=context.before_state,
            already_rebuilt=True,
        )

    outcome = execute_rebuild(context)
    if not outcome.authoritative_rebuild_completed:
        raise FullRebuildGateError(
            "FULL_REBUILD callback did not prove authoritative target reconstruction"
        )
    if not outcome.gate.can_advance_state:
        raise FullRebuildGateError(
            "FULL_REBUILD runtime state cannot cut over before target commit and "
            "required reconciliation"
        )

    state = state_adapter.commit_rebuild_state(
        dataset_id=request.dataset_id,
        expected_version=context.before_state.version,
        rebuild_request_id=request.reprocess_request_id,
        dataset_run_id=dataset_run_id,
        replacement=outcome.state_replacement,
    )
    return FullRebuildResult(
        value=outcome.value,
        rebuild_request_id=request.reprocess_request_id,
        dataset_run_id=dataset_run_id,
        state=state,
    )


__all__ = [
    "FullRebuildContext",
    "FullRebuildError",
    "FullRebuildGateError",
    "FullRebuildMutationOutcome",
    "FullRebuildResult",
    "FullRebuildStateVersionConflict",
    "InMemoryFullRebuildStateAdapter",
    "execute_full_rebuild",
    "prepare_full_rebuild",
]
