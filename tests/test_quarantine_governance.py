from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.control_plane.io import (
    read_quarantine_batches,
    record_quarantine_batch,
)
from fabric_data_framework.control_plane.quarantine_governance import (
    QuarantineGovernanceError,
    QuarantineTransitionConflict,
    get_quarantine_case,
    read_quarantine_manual_correction,
    read_quarantine_review_events,
    record_quarantine_review_event,
    resolve_quarantine_with_manual_correction,
)
from fabric_data_framework.contracts.quarantine import (
    QuarantineManualCorrection,
    QuarantineResolution,
    QuarantineReviewEvent,
    QuarantineStatus,
)
from fabric_data_framework.contracts.recovery import ReprocessRequest
from fabric_data_framework.contracts.replay import (
    QuarantineBatchEvidence,
    QuarantineReplayPayload,
)
from fabric_data_framework.contracts.runtime import StateCommitGate
from fabric_data_framework.metadata.config import RunMode
from fabric_data_framework.recovery.replay import (
    QuarantineReplayMutationOutcome,
    QuarantineReplayPayloadError,
    execute_quarantine_replay,
    prepare_quarantine_replay,
)


DATASET_ID = "health.patient"


class MemoryPayloadProvider:
    def __init__(self, payload: QuarantineReplayPayload):
        self.payload = payload

    def load_payload(self, batch: QuarantineBatchEvidence) -> QuarantineReplayPayload:
        assert batch.quarantine_id == self.payload.quarantine_id
        return self.payload


def _batch() -> QuarantineBatchEvidence:
    quarantine_id = uuid4()
    return QuarantineBatchEvidence(
        quarantine_id=quarantine_id,
        dataset_run_id=uuid4(),
        dataset_id=DATASET_ID,
        scope="ROW",
        row_count=1,
        reason_code="INVALID_BIRTH_DATE",
        reason_detail="birth date was outside accepted range",
        source_reference=f"lakehouse://quarantine/{quarantine_id}/original.parquet",
        created_at=datetime(2026, 9, 8, 1, tzinfo=timezone.utc),
    )


def _begin_review(batch: QuarantineBatchEvidence) -> None:
    record_quarantine_review_event(
        ENGINE,
        QuarantineReviewEvent(
            quarantine_id=batch.quarantine_id,
            dataset_id=batch.dataset_id,
            from_status=QuarantineStatus.OPEN,
            to_status=QuarantineStatus.UNDER_REVIEW,
            actor="data.steward@example.test",
            reason="investigate invalid birth date",
            ticket_reference="INC-100",
        ),
    )


def _request(batch: QuarantineBatchEvidence) -> ReprocessRequest:
    return ReprocessRequest(
        dataset_id=batch.dataset_id,
        run_mode=RunMode.REPLAY,
        reason="replay approved manual correction",
        requested_by="operator",
        range_json={"quarantine_ids": [str(batch.quarantine_id)]},
    )


def _green_gate() -> StateCommitGate:
    return StateCommitGate(
        target_committed=True,
        reconciliation_required=True,
        reconciliation_passed=True,
    )


ENGINE = None


@pytest.fixture(autouse=True)
def fresh_engine(tmp_path):
    global ENGINE
    ENGINE = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    yield
    ENGINE.dispose()
    ENGINE = None


def test_review_lifecycle_is_append_only_and_stale_transition_fails_closed():
    batch = _batch()
    record_quarantine_batch(ENGINE, batch)

    assert get_quarantine_case(ENGINE, batch.quarantine_id).status is QuarantineStatus.OPEN

    first = QuarantineReviewEvent(
        quarantine_id=batch.quarantine_id,
        dataset_id=batch.dataset_id,
        from_status=QuarantineStatus.OPEN,
        to_status=QuarantineStatus.UNDER_REVIEW,
        actor="reviewer-a",
        reason="start review",
    )
    case = record_quarantine_review_event(ENGINE, first)
    assert case.status is QuarantineStatus.UNDER_REVIEW

    with pytest.raises(QuarantineTransitionConflict, match="current status is UNDER_REVIEW"):
        record_quarantine_review_event(
            ENGINE,
            QuarantineReviewEvent(
                quarantine_id=batch.quarantine_id,
                dataset_id=batch.dataset_id,
                from_status=QuarantineStatus.OPEN,
                to_status=QuarantineStatus.WAIVED,
                resolution=QuarantineResolution.ACCEPTED_EXCEPTION,
                actor="reviewer-b",
                reason="stale competing decision",
            ),
        )

    final = QuarantineReviewEvent(
        quarantine_id=batch.quarantine_id,
        dataset_id=batch.dataset_id,
        from_status=QuarantineStatus.UNDER_REVIEW,
        to_status=QuarantineStatus.WAIVED,
        resolution=QuarantineResolution.ACCEPTED_EXCEPTION,
        actor="reviewer-a",
        reason="business-approved exception",
        ticket_reference="CHG-200",
    )
    case = record_quarantine_review_event(ENGINE, final)
    assert case.status is QuarantineStatus.WAIVED
    assert case.resolution is QuarantineResolution.ACCEPTED_EXCEPTION
    assert [item.event_id for item in read_quarantine_review_events(ENGINE, batch.quarantine_id)] == [
        first.event_id,
        final.event_id,
    ]

    with pytest.raises(QuarantineGovernanceError, match="invalid quarantine transition"):
        record_quarantine_review_event(
            ENGINE,
            QuarantineReviewEvent(
                quarantine_id=batch.quarantine_id,
                dataset_id=batch.dataset_id,
                from_status=QuarantineStatus.WAIVED,
                to_status=QuarantineStatus.UNDER_REVIEW,
                actor="reviewer-c",
                reason="attempt to reopen terminal case",
            ),
        )


def test_manual_correction_is_atomic_governed_reference_and_never_mutates_original():
    batch = _batch()
    record_quarantine_batch(ENGINE, batch)
    _begin_review(batch)
    assert batch.source_reference is not None

    correction = QuarantineManualCorrection(
        quarantine_id=batch.quarantine_id,
        dataset_id=batch.dataset_id,
        original_source_reference=batch.source_reference,
        correction_reference=f"lakehouse://quarantine-corrections/{batch.quarantine_id}/v1.parquet",
        correction_payload_sha256="a" * 64,
        corrected_by="data.steward@example.test",
        reason="confirmed birth date from authoritative case record",
        ticket_reference="INC-100",
    )
    event = QuarantineReviewEvent(
        quarantine_id=batch.quarantine_id,
        dataset_id=batch.dataset_id,
        from_status=QuarantineStatus.UNDER_REVIEW,
        to_status=QuarantineStatus.RESOLVED,
        resolution=QuarantineResolution.MANUAL_CORRECTION,
        correction_id=correction.correction_id,
        actor="data.owner@example.test",
        reason="approve exact correction payload",
        ticket_reference="INC-100",
    )

    case = resolve_quarantine_with_manual_correction(
        ENGINE,
        correction=correction,
        event=event,
    )
    assert case.status is QuarantineStatus.RESOLVED
    assert case.resolution is QuarantineResolution.MANUAL_CORRECTION
    assert case.correction_id == correction.correction_id

    stored_correction = read_quarantine_manual_correction(ENGINE, correction.correction_id)
    assert stored_correction.model_dump(exclude={"created_at"}) == correction.model_dump(
        exclude={"created_at"}
    )
    assert stored_correction.created_at.replace(tzinfo=timezone.utc) == correction.created_at

    stored_original = read_quarantine_batches(ENGINE, (batch.quarantine_id,))[0]
    assert stored_original.source_reference == batch.source_reference
    assert stored_original.reason_code == batch.reason_code
    assert stored_original.replayed_by_dataset_run_id is None


def test_manual_correction_replay_requires_exact_approved_reference_and_hash_then_derives_replayed():
    batch = _batch()
    record_quarantine_batch(ENGINE, batch)
    _begin_review(batch)
    assert batch.source_reference is not None

    correction = QuarantineManualCorrection(
        quarantine_id=batch.quarantine_id,
        dataset_id=batch.dataset_id,
        original_source_reference=batch.source_reference,
        correction_reference=f"lakehouse://quarantine-corrections/{batch.quarantine_id}/v1.parquet",
        correction_payload_sha256="b" * 64,
        corrected_by="data.steward@example.test",
        reason="correct birth date",
    )
    resolve_quarantine_with_manual_correction(
        ENGINE,
        correction=correction,
        event=QuarantineReviewEvent(
            quarantine_id=batch.quarantine_id,
            dataset_id=batch.dataset_id,
            from_status=QuarantineStatus.UNDER_REVIEW,
            to_status=QuarantineStatus.RESOLVED,
            resolution=QuarantineResolution.MANUAL_CORRECTION,
            correction_id=correction.correction_id,
            actor="data.owner@example.test",
            reason="approved",
        ),
    )

    unproven = QuarantineReplayPayload(
        quarantine_id=batch.quarantine_id,
        dataset_id=batch.dataset_id,
        source_reference=batch.source_reference,
        rows=({"patient_id": 1, "birth_date": "1999-01-01"},),
    )
    with pytest.raises(QuarantineReplayPayloadError, match="must carry the approved correction"):
        prepare_quarantine_replay(
            ENGINE,
            request=_request(batch),
            replay_dataset_run_id=uuid4(),
            payload_provider=MemoryPayloadProvider(unproven),
        )

    wrong_hash = unproven.model_copy(
        update={
            "correction_id": correction.correction_id,
            "correction_reference": correction.correction_reference,
            "correction_payload_sha256": "c" * 64,
        }
    )
    with pytest.raises(QuarantineReplayPayloadError, match="hash does not match"):
        prepare_quarantine_replay(
            ENGINE,
            request=_request(batch),
            replay_dataset_run_id=uuid4(),
            payload_provider=MemoryPayloadProvider(wrong_hash),
        )

    approved = unproven.model_copy(
        update={
            "correction_id": correction.correction_id,
            "correction_reference": correction.correction_reference,
            "correction_payload_sha256": correction.correction_payload_sha256,
        }
    )
    replay_run_id = uuid4()
    result = execute_quarantine_replay(
        ENGINE,
        request=_request(batch),
        replay_dataset_run_id=replay_run_id,
        payload_provider=MemoryPayloadProvider(approved),
        execute_payloads=lambda prepared: QuarantineReplayMutationOutcome(
            value=prepared.payloads[0].rows[0],
            gate=_green_gate(),
        ),
    )
    assert result.value == {"patient_id": 1, "birth_date": "1999-01-01"}

    case = get_quarantine_case(ENGINE, batch.quarantine_id)
    assert case.status is QuarantineStatus.REPLAYED
    assert case.replayed_by_dataset_run_id == replay_run_id
    assert case.resolution is QuarantineResolution.MANUAL_CORRECTION
    assert case.correction_id == correction.correction_id

    stored_original = read_quarantine_batches(ENGINE, (batch.quarantine_id,))[0]
    assert stored_original.source_reference == batch.source_reference
    assert stored_original.replayed_by_dataset_run_id == replay_run_id


def test_review_contract_rejects_manual_replayed_status_and_resolution_mismatch():
    batch = _batch()
    with pytest.raises(ValueError, match="REPLAYED is derived"):
        QuarantineReviewEvent(
            quarantine_id=batch.quarantine_id,
            dataset_id=batch.dataset_id,
            from_status=QuarantineStatus.OPEN,
            to_status=QuarantineStatus.REPLAYED,
            actor="operator",
            reason="must not be manually marked replayed",
        )

    record_quarantine_batch(ENGINE, batch)
    with pytest.raises(QuarantineGovernanceError, match="not valid for REJECTED"):
        record_quarantine_review_event(
            ENGINE,
            QuarantineReviewEvent(
                quarantine_id=batch.quarantine_id,
                dataset_id=batch.dataset_id,
                from_status=QuarantineStatus.OPEN,
                to_status=QuarantineStatus.REJECTED,
                resolution=QuarantineResolution.SOURCE_CORRECTED,
                actor="operator",
                reason="invalid resolution class",
            ),
        )
