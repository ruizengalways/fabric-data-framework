from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.config import RunMode
from fabric_data_framework.control_plane.io import (
    QuarantineReplayMarkerConflict,
    read_quarantine_batches,
    record_quarantine_batch,
)
from fabric_data_framework.contracts.recovery import ReprocessRequest
from fabric_data_framework.contracts.replay import (
    QuarantineBatchEvidence,
    QuarantineReplayPayload,
)
from fabric_data_framework.recovery import (
    QuarantineReplayError,
    QuarantineReplayGateError,
    QuarantineReplayMutationOutcome,
    QuarantineReplayPayloadError,
    execute_quarantine_replay,
    prepare_quarantine_replay,
)
from fabric_data_framework.runtime import StateCommitGate


DATASET_ID = "erp.order"


class MemoryPayloadProvider:
    def __init__(self, payloads: dict[UUID, QuarantineReplayPayload]):
        self.payloads = payloads
        self.calls: list[UUID] = []

    def load_payload(self, batch: QuarantineBatchEvidence) -> QuarantineReplayPayload:
        self.calls.append(batch.quarantine_id)
        return self.payloads[batch.quarantine_id]


def _batch(
    *,
    dataset_id: str = DATASET_ID,
    dataset_run_id: UUID | None = None,
    row_count: int = 2,
    source_reference: str | None = None,
) -> QuarantineBatchEvidence:
    quarantine_id = uuid4()
    return QuarantineBatchEvidence(
        quarantine_id=quarantine_id,
        dataset_run_id=dataset_run_id or uuid4(),
        dataset_id=dataset_id,
        scope="ROW",
        row_count=row_count,
        reason_code="DQ_INVALID",
        reason_detail="reference validation failure",
        source_reference=source_reference or f"lakehouse://quarantine/{quarantine_id}",
        created_at=datetime(2026, 8, 29, 1, tzinfo=timezone.utc),
    )


def _payload(batch: QuarantineBatchEvidence, rows=None) -> QuarantineReplayPayload:
    actual_rows = rows if rows is not None else tuple(
        {"id": index + 1, "fixed": True} for index in range(batch.row_count)
    )
    assert batch.source_reference is not None
    return QuarantineReplayPayload(
        quarantine_id=batch.quarantine_id,
        dataset_id=batch.dataset_id,
        source_reference=batch.source_reference,
        rows=tuple(actual_rows),
        payload_version="v1",
    )


def _request(*batches: QuarantineBatchEvidence) -> ReprocessRequest:
    return ReprocessRequest(
        dataset_id=DATASET_ID,
        run_mode=RunMode.REPLAY,
        reason="replay corrected quarantined rows",
        requested_by="operator",
        range_json={"quarantine_ids": [str(batch.quarantine_id) for batch in batches]},
    )


def _green_gate() -> StateCommitGate:
    return StateCommitGate(
        target_committed=True,
        reconciliation_required=True,
        reconciliation_passed=True,
    )


def test_quarantine_replay_loads_external_payload_and_marks_only_after_success(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    first = _batch()
    second = _batch(row_count=1)
    record_quarantine_batch(engine, first)
    record_quarantine_batch(engine, second)
    provider = MemoryPayloadProvider(
        {first.quarantine_id: _payload(first), second.quarantine_id: _payload(second)}
    )
    replay_run_id = uuid4()
    seen = []

    def execute(prepared):
        seen.append(prepared)
        assert prepared.plan.total_rows == 3
        assert [len(payload.rows) for payload in prepared.payloads] == [2, 1]
        return QuarantineReplayMutationOutcome(value="published", gate=_green_gate())

    result = execute_quarantine_replay(
        engine,
        request=_request(first, second),
        replay_dataset_run_id=replay_run_id,
        payload_provider=provider,
        execute_payloads=execute,
    )

    assert result.value == "published"
    assert result.plan.total_rows == 3
    assert result.already_replayed is False
    assert provider.calls == [first.quarantine_id, second.quarantine_id]
    assert len(seen) == 1

    stored = read_quarantine_batches(engine, (first.quarantine_id, second.quarantine_id))
    assert all(item.replayed_by_dataset_run_id == replay_run_id for item in stored)
    assert [item.reason_code for item in stored] == ["DQ_INVALID", "DQ_INVALID"]
    assert [item.source_reference for item in stored] == [
        first.source_reference,
        second.source_reference,
    ]


def test_replay_failure_or_failed_gate_never_marks_original_quarantine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    batch = _batch()
    record_quarantine_batch(engine, batch)
    provider = MemoryPayloadProvider({batch.quarantine_id: _payload(batch)})

    with pytest.raises(RuntimeError, match="target write failed"):
        execute_quarantine_replay(
            engine,
            request=_request(batch),
            replay_dataset_run_id=uuid4(),
            payload_provider=provider,
            execute_payloads=lambda _prepared: (_ for _ in ()).throw(
                RuntimeError("target write failed")
            ),
        )

    stored = read_quarantine_batches(engine, (batch.quarantine_id,))[0]
    assert stored.replayed_by_dataset_run_id is None

    with pytest.raises(QuarantineReplayGateError, match="cannot be marked successful"):
        execute_quarantine_replay(
            engine,
            request=_request(batch),
            replay_dataset_run_id=uuid4(),
            payload_provider=provider,
            execute_payloads=lambda _prepared: QuarantineReplayMutationOutcome(
                value=None,
                gate=StateCommitGate(
                    target_committed=True,
                    reconciliation_required=True,
                    reconciliation_passed=False,
                ),
            ),
        )

    stored = read_quarantine_batches(engine, (batch.quarantine_id,))[0]
    assert stored.replayed_by_dataset_run_id is None


def test_replay_payload_must_match_control_plane_identity_reference_and_row_count(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    batch = _batch(row_count=2)
    record_quarantine_batch(engine, batch)

    wrong_count = _payload(batch, rows=({"id": 1},))
    provider = MemoryPayloadProvider({batch.quarantine_id: wrong_count})
    with pytest.raises(QuarantineReplayPayloadError, match="row count"):
        prepare_quarantine_replay(
            engine,
            request=_request(batch),
            replay_dataset_run_id=uuid4(),
            payload_provider=provider,
        )

    assert batch.source_reference is not None
    wrong_reference = QuarantineReplayPayload(
        quarantine_id=batch.quarantine_id,
        dataset_id=batch.dataset_id,
        source_reference=batch.source_reference + "/other",
        rows=({"id": 1}, {"id": 2}),
    )
    provider = MemoryPayloadProvider({batch.quarantine_id: wrong_reference})
    with pytest.raises(QuarantineReplayPayloadError, match="source reference"):
        prepare_quarantine_replay(
            engine,
            request=_request(batch),
            replay_dataset_run_id=uuid4(),
            payload_provider=provider,
        )


def test_replay_rejects_dataset_mismatch_or_missing_payload_reference_before_mutation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    other = _batch(dataset_id="finance.invoice")
    record_quarantine_batch(engine, other)
    provider = MemoryPayloadProvider({other.quarantine_id: _payload(other)})

    with pytest.raises(QuarantineReplayError, match="belongs to dataset"):
        prepare_quarantine_replay(
            engine,
            request=ReprocessRequest(
                dataset_id=DATASET_ID,
                run_mode=RunMode.REPLAY,
                reason="wrong dataset",
                requested_by="operator",
                range_json={"quarantine_ids": [str(other.quarantine_id)]},
            ),
            replay_dataset_run_id=uuid4(),
            payload_provider=provider,
        )
    assert provider.calls == []

    missing_ref = _batch(source_reference="placeholder")
    missing_ref = missing_ref.model_copy(update={"source_reference": None})
    record_quarantine_batch(engine, missing_ref)
    with pytest.raises(QuarantineReplayError, match="no retained payload"):
        prepare_quarantine_replay(
            engine,
            request=_request(missing_ref),
            replay_dataset_run_id=uuid4(),
            payload_provider=MemoryPayloadProvider({}),
        )


def test_exact_replay_rerun_with_same_dataset_run_id_converges_without_reapplying(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    batch = _batch()
    record_quarantine_batch(engine, batch)
    provider = MemoryPayloadProvider({batch.quarantine_id: _payload(batch)})
    replay_run_id = uuid4()

    first = execute_quarantine_replay(
        engine,
        request=_request(batch),
        replay_dataset_run_id=replay_run_id,
        payload_provider=provider,
        execute_payloads=lambda _prepared: QuarantineReplayMutationOutcome(
            value="first",
            gate=_green_gate(),
        ),
    )
    assert first.already_replayed is False

    calls = 0

    def must_not_execute(_prepared):
        nonlocal calls
        calls += 1
        raise AssertionError("exact replay rerun must not mutate target again")

    second = execute_quarantine_replay(
        engine,
        request=_request(batch),
        replay_dataset_run_id=replay_run_id,
        payload_provider=provider,
        execute_payloads=must_not_execute,
    )
    assert second.already_replayed is True
    assert second.value is None
    assert calls == 0
    assert provider.calls == [batch.quarantine_id]


def test_different_replay_dataset_run_cannot_claim_already_replayed_batch(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    batch = _batch()
    record_quarantine_batch(engine, batch)
    provider = MemoryPayloadProvider({batch.quarantine_id: _payload(batch)})

    execute_quarantine_replay(
        engine,
        request=_request(batch),
        replay_dataset_run_id=uuid4(),
        payload_provider=provider,
        execute_payloads=lambda _prepared: QuarantineReplayMutationOutcome(
            value=None,
            gate=_green_gate(),
        ),
    )

    with pytest.raises(QuarantineReplayMarkerConflict, match="another replay"):
        prepare_quarantine_replay(
            engine,
            request=_request(batch),
            replay_dataset_run_id=uuid4(),
            payload_provider=provider,
        )


def test_replay_can_select_all_quarantine_batches_from_original_dataset_run(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    original_run_id = uuid4()
    first = _batch(dataset_run_id=original_run_id, row_count=1)
    second = _batch(dataset_run_id=original_run_id, row_count=2)
    unrelated = _batch(dataset_run_id=uuid4(), row_count=1)
    for batch in (first, second, unrelated):
        record_quarantine_batch(engine, batch)

    provider = MemoryPayloadProvider(
        {
            first.quarantine_id: _payload(first),
            second.quarantine_id: _payload(second),
            unrelated.quarantine_id: _payload(unrelated),
        }
    )
    request = ReprocessRequest(
        dataset_id=DATASET_ID,
        run_mode=RunMode.REPLAY,
        reason="replay original run quarantines",
        requested_by="operator",
        original_dataset_run_id=original_run_id,
    )

    prepared = prepare_quarantine_replay(
        engine,
        request=request,
        replay_dataset_run_id=uuid4(),
        payload_provider=provider,
    )

    assert set(prepared.plan.quarantine_ids) == {first.quarantine_id, second.quarantine_id}
    assert prepared.plan.total_rows == 3
    assert unrelated.quarantine_id not in provider.calls
