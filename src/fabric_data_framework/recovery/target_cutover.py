"""Fail-closed blue/green target-version cutover coordination."""

from __future__ import annotations

from threading import RLock

from fabric_data_framework.contracts.target_version import (
    TargetActiveVersionSnapshot,
    TargetCutoverAdapter,
    TargetCutoverGate,
    TargetCutoverRequest,
    TargetCutoverResult,
    TargetVersionSpec,
)


class TargetCutoverError(RuntimeError):
    """Base target cutover error."""


class TargetCutoverGateError(TargetCutoverError):
    """Candidate evidence is insufficient for consumer cutover."""


class TargetCutoverConflict(TargetCutoverError):
    """The active logical target changed concurrently or does not match the request."""


class InMemoryTargetCutoverAdapter:
    """Deterministic reference adapter for logical-target promotion tests."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._states: dict[tuple[str, str, str], TargetActiveVersionSnapshot] = {}

    def seed_active(
        self,
        *,
        dataset_id: str,
        environment: str,
        logical_object: str,
        version: str,
        physical_object: str,
    ) -> TargetActiveVersionSnapshot:
        key = (dataset_id, environment, logical_object)
        with self._lock:
            current = self._states.get(key)
            generation = current.generation + 1 if current is not None else 1
            state = TargetActiveVersionSnapshot(
                dataset_id=dataset_id,
                environment=environment,
                logical_object=logical_object,
                version=version,
                physical_object=physical_object,
                generation=generation,
            )
            self._states[key] = state
            return state

    def read_active(
        self,
        *,
        dataset_id: str,
        environment: str,
        logical_object: str,
    ) -> TargetActiveVersionSnapshot:
        key = (dataset_id, environment, logical_object)
        with self._lock:
            try:
                return self._states[key]
            except KeyError as exc:
                raise TargetCutoverConflict(
                    f"no active target binding for {dataset_id}/{environment}/{logical_object}"
                ) from exc

    def promote(
        self,
        *,
        expected_generation: int,
        request: TargetCutoverRequest,
        candidate: TargetVersionSpec,
    ) -> TargetActiveVersionSnapshot:
        key = (request.dataset_id, request.environment, request.logical_object)
        with self._lock:
            current = self.read_active(
                dataset_id=request.dataset_id,
                environment=request.environment,
                logical_object=request.logical_object,
            )
            if current.last_cutover_request_id == request.cutover_request_id:
                return current
            if current.generation != expected_generation:
                raise TargetCutoverConflict(
                    f"target binding generation changed: expected {expected_generation}, "
                    f"current {current.generation}"
                )
            if current.version != request.from_version:
                raise TargetCutoverConflict(
                    f"active version is {current.version}, expected {request.from_version}"
                )
            next_state = TargetActiveVersionSnapshot(
                dataset_id=current.dataset_id,
                environment=current.environment,
                logical_object=current.logical_object,
                version=candidate.version,
                physical_object=candidate.physical_object,
                generation=current.generation + 1,
                last_cutover_request_id=request.cutover_request_id,
            )
            self._states[key] = next_state
            return next_state


def _validate_candidate(
    *,
    request: TargetCutoverRequest,
    candidate: TargetVersionSpec,
    before: TargetActiveVersionSnapshot,
) -> None:
    if candidate.dataset_id != request.dataset_id:
        raise TargetCutoverConflict("candidate dataset_id does not match cutover request")
    if candidate.logical_object != request.logical_object:
        raise TargetCutoverConflict("candidate logical_object does not match cutover request")
    if candidate.version != request.to_version:
        raise TargetCutoverConflict("candidate version does not match cutover to_version")
    if before.version != request.from_version:
        raise TargetCutoverConflict(
            f"active version is {before.version}, expected {request.from_version}"
        )
    if candidate.physical_object == before.physical_object:
        raise TargetCutoverConflict(
            "blue/green cutover candidate physical object must differ from active object"
        )


def execute_target_cutover(
    *,
    request: TargetCutoverRequest,
    candidate: TargetVersionSpec,
    gate: TargetCutoverGate,
    adapter: TargetCutoverAdapter,
) -> TargetCutoverResult:
    """Promote an already-built candidate only after validation and approval evidence.

    This operation switches the stable logical consumer binding. It never deletes the
    previous physical version; cleanup remains an explicit manual governance action.
    """

    before = adapter.read_active(
        dataset_id=request.dataset_id,
        environment=request.environment,
        logical_object=request.logical_object,
    )

    if before.last_cutover_request_id == request.cutover_request_id:
        if before.version != request.to_version or before.physical_object != candidate.physical_object:
            raise TargetCutoverConflict(
                "cutover request id already applied to a different target version"
            )
        return TargetCutoverResult(
            request_id=request.cutover_request_id,
            before=before,
            after=before,
            candidate=candidate,
            already_promoted=True,
        )

    _validate_candidate(request=request, candidate=candidate, before=before)

    if gate.approval_reference != request.approval_reference:
        raise TargetCutoverGateError(
            "cutover gate approval_reference does not match request approval_reference"
        )
    if not gate.can_promote:
        raise TargetCutoverGateError(
            "target cutover requires candidate build, reconciliation and consumer validation"
        )

    after = adapter.promote(
        expected_generation=before.generation,
        request=request,
        candidate=candidate,
    )
    if (
        after.version != candidate.version
        or after.physical_object != candidate.physical_object
        or after.last_cutover_request_id != request.cutover_request_id
    ):
        raise TargetCutoverConflict(
            "target cutover adapter did not return the requested promoted binding"
        )

    return TargetCutoverResult(
        request_id=request.cutover_request_id,
        before=before,
        after=after,
        candidate=candidate,
    )


__all__ = [
    "InMemoryTargetCutoverAdapter",
    "TargetCutoverConflict",
    "TargetCutoverError",
    "TargetCutoverGateError",
    "execute_target_cutover",
]
