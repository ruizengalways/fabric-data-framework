"""Fail-closed quarantine replay coordination.

Replay payload retrieval is delegated to a governed-store provider. This module
validates immutable quarantine evidence, validates any approved manual-correction
provenance, executes one idempotent replay attempt and marks the original quarantine
rows only after the target/reconciliation gate passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar
from uuid import UUID

from fabric_data_framework.metadata.config import RunMode
from ..contracts.quarantine import QuarantineResolution, QuarantineStatus
from ..contracts.recovery import ReprocessRequest
from ..contracts.replay import (
    QuarantineBatchEvidence,
    QuarantineReplayPayload,
    QuarantineReplayPayloadProvider,
    QuarantineReplayPlan,
)
from ..control_plane.io import (
    QuarantineReplayMarkerConflict,
    mark_quarantine_replayed,
    read_quarantine_batches,
    read_quarantine_batches_for_run,
)
from ..control_plane.quarantine_governance import (
    get_quarantine_case,
    read_quarantine_manual_correction,
)
from fabric_data_framework.contracts.runtime import StateCommitGate


T = TypeVar("T")


class QuarantineReplayError(RuntimeError):
    """Base replay validation/execution error."""


class QuarantineReplayPayloadError(QuarantineReplayError):
    """Retained payload does not match immutable/approved Control Plane evidence."""


class QuarantineReplayGateError(QuarantineReplayError):
    """Replay target/reconciliation evidence is insufficient to mark success."""


@dataclass(frozen=True)
class PreparedQuarantineReplay:
    plan: QuarantineReplayPlan
    batches: tuple[QuarantineBatchEvidence, ...]
    payloads: tuple[QuarantineReplayPayload, ...]
    already_replayed: bool = False


@dataclass(frozen=True)
class QuarantineReplayMutationOutcome(Generic[T]):
    value: T
    gate: StateCommitGate


@dataclass(frozen=True)
class QuarantineReplayResult(Generic[T]):
    value: T | None
    replay_dataset_run_id: UUID
    plan: QuarantineReplayPlan
    already_replayed: bool = False


def _explicit_quarantine_ids(request: ReprocessRequest) -> tuple[UUID, ...]:
    raw = (request.range_json or {}).get("quarantine_ids")
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)) or not raw:
        raise QuarantineReplayError("REPLAY quarantine_ids must be a non-empty list")

    ids: list[UUID] = []
    for value in raw:
        try:
            ids.append(UUID(str(value)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise QuarantineReplayError(
                f"invalid quarantine id in REPLAY request: {value!r}"
            ) from exc
    if len(set(ids)) != len(ids):
        raise QuarantineReplayError("REPLAY request cannot contain duplicate quarantine ids")
    return tuple(ids)


def _load_batches(
    engine,
    request: ReprocessRequest,
) -> tuple[QuarantineBatchEvidence, ...]:
    explicit_ids = _explicit_quarantine_ids(request)
    if explicit_ids:
        return read_quarantine_batches(engine, explicit_ids)
    if request.original_dataset_run_id is None:
        raise QuarantineReplayError(
            "REPLAY request requires quarantine_ids or original_dataset_run_id"
        )
    return read_quarantine_batches_for_run(
        engine,
        dataset_id=request.dataset_id,
        dataset_run_id=request.original_dataset_run_id,
    )


def _validate_batch_scope(
    batches: tuple[QuarantineBatchEvidence, ...],
    *,
    request: ReprocessRequest,
    replay_dataset_run_id: UUID,
) -> tuple[bool, tuple[str, ...]]:
    if not batches:
        raise QuarantineReplayError("REPLAY scope resolved to zero quarantine batches")

    source_references: list[str] = []
    markers: set[UUID] = set()
    unmarked = 0
    for batch in batches:
        if batch.dataset_id != request.dataset_id:
            raise QuarantineReplayError(
                f"quarantine {batch.quarantine_id} belongs to dataset {batch.dataset_id}, "
                f"not {request.dataset_id}"
            )
        if not batch.source_reference:
            raise QuarantineReplayError(
                f"quarantine {batch.quarantine_id} has no retained payload source_reference"
            )
        source_references.append(batch.source_reference)
        if batch.replayed_by_dataset_run_id is None:
            unmarked += 1
        else:
            markers.add(batch.replayed_by_dataset_run_id)

    if markers:
        if markers == {replay_dataset_run_id} and unmarked == 0:
            return True, tuple(source_references)
        values = ", ".join(sorted(str(value) for value in markers))
        raise QuarantineReplayMarkerConflict(
            "quarantine replay scope is already/partially claimed by another replay "
            f"dataset run: {values}"
        )
    return False, tuple(source_references)


def _validate_payload(
    batch: QuarantineBatchEvidence,
    payload: QuarantineReplayPayload,
) -> None:
    if payload.quarantine_id != batch.quarantine_id:
        raise QuarantineReplayPayloadError(
            f"payload quarantine id {payload.quarantine_id} does not match "
            f"{batch.quarantine_id}"
        )
    if payload.dataset_id != batch.dataset_id:
        raise QuarantineReplayPayloadError(
            f"payload dataset {payload.dataset_id} does not match {batch.dataset_id}"
        )
    if payload.source_reference != batch.source_reference:
        raise QuarantineReplayPayloadError(
            f"payload source reference for {batch.quarantine_id} does not match control plane"
        )
    if len(payload.rows) != batch.row_count:
        raise QuarantineReplayPayloadError(
            f"payload row count for {batch.quarantine_id} is {len(payload.rows)}; "
            f"expected {batch.row_count}"
        )


def _validate_correction_provenance(
    engine,
    batch: QuarantineBatchEvidence,
    payload: QuarantineReplayPayload,
) -> None:
    case = get_quarantine_case(engine, batch.quarantine_id)
    if payload.correction_id is None:
        if (
            case.status is QuarantineStatus.RESOLVED
            and case.resolution is QuarantineResolution.MANUAL_CORRECTION
        ):
            raise QuarantineReplayPayloadError(
                f"quarantine {batch.quarantine_id} was resolved by manual correction; "
                "replay payload must carry the approved correction identity/reference/hash"
            )
        return

    if (
        case.status is not QuarantineStatus.RESOLVED
        or case.resolution is not QuarantineResolution.MANUAL_CORRECTION
        or case.correction_id != payload.correction_id
    ):
        raise QuarantineReplayPayloadError(
            f"quarantine {batch.quarantine_id} correction is not the approved resolved correction"
        )

    correction = read_quarantine_manual_correction(engine, payload.correction_id)
    if correction.quarantine_id != batch.quarantine_id:
        raise QuarantineReplayPayloadError("manual correction quarantine identity mismatch")
    if correction.dataset_id != batch.dataset_id:
        raise QuarantineReplayPayloadError("manual correction dataset identity mismatch")
    if correction.original_source_reference != batch.source_reference:
        raise QuarantineReplayPayloadError(
            "manual correction original source reference does not match quarantine evidence"
        )
    if correction.correction_reference != payload.correction_reference:
        raise QuarantineReplayPayloadError(
            "manual correction payload reference does not match approved correction"
        )
    if correction.correction_payload_sha256 != payload.correction_payload_sha256:
        raise QuarantineReplayPayloadError(
            "manual correction payload hash does not match approved correction"
        )


def prepare_quarantine_replay(
    engine,
    *,
    request: ReprocessRequest,
    replay_dataset_run_id: UUID,
    payload_provider: QuarantineReplayPayloadProvider,
) -> PreparedQuarantineReplay:
    """Resolve immutable replay scope and verify retained/corrected payload before mutation."""

    if request.run_mode is not RunMode.REPLAY:
        raise QuarantineReplayError("quarantine replay requires a REPLAY ReprocessRequest")

    batches = _load_batches(engine, request)
    already_replayed, source_references = _validate_batch_scope(
        batches,
        request=request,
        replay_dataset_run_id=replay_dataset_run_id,
    )
    plan = QuarantineReplayPlan(
        reprocess_request_id=request.reprocess_request_id,
        dataset_id=request.dataset_id,
        quarantine_ids=tuple(batch.quarantine_id for batch in batches),
        source_references=source_references,
        total_rows=sum(batch.row_count for batch in batches),
    )
    if already_replayed:
        return PreparedQuarantineReplay(
            plan=plan,
            batches=batches,
            payloads=(),
            already_replayed=True,
        )

    payloads: list[QuarantineReplayPayload] = []
    for batch in batches:
        payload = payload_provider.load_payload(batch)
        _validate_payload(batch, payload)
        _validate_correction_provenance(engine, batch, payload)
        payloads.append(payload)

    return PreparedQuarantineReplay(
        plan=plan,
        batches=batches,
        payloads=tuple(payloads),
    )


def execute_quarantine_replay(
    engine,
    *,
    request: ReprocessRequest,
    replay_dataset_run_id: UUID,
    payload_provider: QuarantineReplayPayloadProvider,
    execute_payloads: Callable[
        [PreparedQuarantineReplay], QuarantineReplayMutationOutcome[T]
    ],
) -> QuarantineReplayResult[T]:
    """Execute replay and correlate originals only after the semantic state gate.

    The caller should normally invoke this inside ``execute_with_retry`` using that
    attempt's ``dataset_run_id``. The strategy-specific callback owns idempotent target
    apply/reconciliation. Original quarantine evidence/payload and correction evidence
    are never deleted.
    """

    prepared = prepare_quarantine_replay(
        engine,
        request=request,
        replay_dataset_run_id=replay_dataset_run_id,
        payload_provider=payload_provider,
    )
    if prepared.already_replayed:
        return QuarantineReplayResult(
            value=None,
            replay_dataset_run_id=replay_dataset_run_id,
            plan=prepared.plan,
            already_replayed=True,
        )

    outcome = execute_payloads(prepared)
    if not outcome.gate.can_advance_state:
        raise QuarantineReplayGateError(
            "quarantine replay cannot be marked successful before target commit and "
            "required reconciliation"
        )

    mark_quarantine_replayed(
        engine,
        dataset_id=request.dataset_id,
        quarantine_ids=prepared.plan.quarantine_ids,
        replayed_by_dataset_run_id=replay_dataset_run_id,
        gate=outcome.gate,
    )
    return QuarantineReplayResult(
        value=outcome.value,
        replay_dataset_run_id=replay_dataset_run_id,
        plan=prepared.plan,
    )


__all__ = [
    "PreparedQuarantineReplay",
    "QuarantineReplayError",
    "QuarantineReplayGateError",
    "QuarantineReplayMutationOutcome",
    "QuarantineReplayPayloadError",
    "QuarantineReplayResult",
    "execute_quarantine_replay",
    "prepare_quarantine_replay",
]
