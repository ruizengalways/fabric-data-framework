from uuid import uuid4

import pytest

from fabric_data_framework.metadata.config import RunMode
from fabric_data_framework.contracts.rebuild import (
    FullRebuildStateReplacement,
    RebuildProgressKind,
    RebuildScope,
)
from fabric_data_framework.contracts.recovery import ReprocessRequest
from fabric_data_framework.recovery.rebuild import (
    FullRebuildError,
    FullRebuildGateError,
    FullRebuildMutationOutcome,
    FullRebuildStateVersionConflict,
    InMemoryFullRebuildStateAdapter,
    execute_full_rebuild,
)
from fabric_data_framework.contracts.runtime import StateCommitGate


DATASET_ID = "erp.order"


def _request(scope: RebuildScope = RebuildScope.AUTHORITATIVE_RESET) -> ReprocessRequest:
    return ReprocessRequest(
        dataset_id=DATASET_ID,
        run_mode=RunMode.FULL_REBUILD,
        reason="approved authoritative reconstruction",
        requested_by="operator",
        range_json={
            "rebuild_scope": scope.value,
            "authoritative_reset": True,
        },
    )


def _green_gate() -> StateCommitGate:
    return StateCommitGate(
        target_committed=True,
        reconciliation_required=True,
        reconciliation_passed=True,
    )


def _replacement(
    kind: RebuildProgressKind = RebuildProgressKind.WATERMARK,
    *,
    marker: int = 100,
) -> FullRebuildStateReplacement:
    return FullRebuildStateReplacement(
        progress_kind=kind,
        progress_payload={"marker": marker},
        dataset_state={"generation": marker},
        source_boundary_reference=f"source-boundary-{marker}",
    )


def _outcome(
    *,
    scope: RebuildScope,
    replacement: FullRebuildStateReplacement | None,
    value="rebuilt",
    completed=True,
    gate: StateCommitGate | None = None,
) -> FullRebuildMutationOutcome:
    return FullRebuildMutationOutcome(
        value=value,
        completed_scope=scope,
        authoritative_rebuild_completed=completed,
        gate=gate or _green_gate(),
        state_replacement=replacement,
    )


def test_full_rebuild_requires_full_rebuild_request():
    adapter = InMemoryFullRebuildStateAdapter()
    retry_request = ReprocessRequest(
        dataset_id=DATASET_ID,
        run_mode=RunMode.RETRY,
        reason="not a rebuild",
        requested_by="operator",
        original_dataset_run_id=uuid4(),
    )

    with pytest.raises(FullRebuildError, match="requires a FULL_REBUILD request"):
        execute_full_rebuild(
            request=retry_request,
            dataset_run_id=uuid4(),
            state_adapter=adapter,
            execute_rebuild=lambda _context: _outcome(
                scope=RebuildScope.AUTHORITATIVE_RESET,
                replacement=_replacement(),
            ),
        )


def test_target_only_rebuild_preserves_capture_state_exactly():
    adapter = InMemoryFullRebuildStateAdapter()
    before = adapter.seed_state(DATASET_ID, _replacement(marker=10))
    request = _request(RebuildScope.TARGET_ONLY)

    result = execute_full_rebuild(
        request=request,
        dataset_run_id=uuid4(),
        state_adapter=adapter,
        execute_rebuild=lambda context: _outcome(
            scope=context.rebuild_scope,
            replacement=context.before_state.replacement,
            value="silver-v2",
        ),
    )

    assert result.rebuild_scope is RebuildScope.TARGET_ONLY
    assert result.value == "silver-v2"
    assert result.state.replacement == before.replacement
    assert result.state.version == before.version + 1


def test_target_only_rejects_capture_state_change():
    adapter = InMemoryFullRebuildStateAdapter()
    before = adapter.seed_state(DATASET_ID, _replacement(marker=10))

    with pytest.raises(FullRebuildGateError, match="preserve capture/runtime state exactly"):
        execute_full_rebuild(
            request=_request(RebuildScope.TARGET_ONLY),
            dataset_run_id=uuid4(),
            state_adapter=adapter,
            execute_rebuild=lambda context: _outcome(
                scope=context.rebuild_scope,
                replacement=_replacement(marker=20),
            ),
        )

    assert adapter.read_state(DATASET_ID) == before


def test_capture_and_target_can_replace_checkpoint_with_same_progress_kind():
    adapter = InMemoryFullRebuildStateAdapter()
    before = adapter.seed_state(DATASET_ID, _replacement(RebuildProgressKind.WATERMARK, marker=10))

    result = execute_full_rebuild(
        request=_request(RebuildScope.CAPTURE_AND_TARGET),
        dataset_run_id=uuid4(),
        state_adapter=adapter,
        execute_rebuild=lambda context: _outcome(
            scope=context.rebuild_scope,
            replacement=_replacement(RebuildProgressKind.WATERMARK, marker=200),
        ),
    )

    assert result.rebuild_scope is RebuildScope.CAPTURE_AND_TARGET
    assert result.state.replacement is not None
    assert result.state.replacement.progress_kind is RebuildProgressKind.WATERMARK
    assert result.state.replacement.progress_payload == {"marker": 200}
    assert result.state.version == before.version + 1


def test_capture_and_target_cannot_change_progress_kind():
    adapter = InMemoryFullRebuildStateAdapter()
    before = adapter.seed_state(DATASET_ID, _replacement(RebuildProgressKind.WATERMARK, marker=10))

    with pytest.raises(FullRebuildGateError, match="cannot change progress kind"):
        execute_full_rebuild(
            request=_request(RebuildScope.CAPTURE_AND_TARGET),
            dataset_run_id=uuid4(),
            state_adapter=adapter,
            execute_rebuild=lambda context: _outcome(
                scope=context.rebuild_scope,
                replacement=_replacement(RebuildProgressKind.CDC, marker=200),
            ),
        )

    assert adapter.read_state(DATASET_ID) == before


def test_authoritative_reset_can_change_progress_kind_after_green_gate():
    adapter = InMemoryFullRebuildStateAdapter()
    before = adapter.seed_state(DATASET_ID, _replacement(RebuildProgressKind.WATERMARK, marker=10))
    request = _request(RebuildScope.AUTHORITATIVE_RESET)
    dataset_run_id = uuid4()
    seen = []

    def rebuild(context):
        seen.append(context)
        assert context.before_state == before
        assert context.rebuild_scope is RebuildScope.AUTHORITATIVE_RESET
        return _outcome(
            scope=context.rebuild_scope,
            replacement=_replacement(RebuildProgressKind.CDC, marker=200),
            value="published-generation-2",
        )

    result = execute_full_rebuild(
        request=request,
        dataset_run_id=dataset_run_id,
        state_adapter=adapter,
        execute_rebuild=rebuild,
    )

    assert result.value == "published-generation-2"
    assert result.already_rebuilt is False
    assert result.rebuild_scope is RebuildScope.AUTHORITATIVE_RESET
    assert result.state.version == before.version + 1
    assert result.state.last_rebuild_request_id == request.reprocess_request_id
    assert result.state.last_rebuild_dataset_run_id == dataset_run_id
    assert result.state.replacement is not None
    assert result.state.replacement.progress_kind is RebuildProgressKind.CDC
    assert len(seen) == 1


def test_completed_scope_must_match_authorized_scope():
    adapter = InMemoryFullRebuildStateAdapter()
    before = adapter.seed_state(DATASET_ID, _replacement(marker=10))

    with pytest.raises(FullRebuildGateError, match="completed scope does not match"):
        execute_full_rebuild(
            request=_request(RebuildScope.TARGET_ONLY),
            dataset_run_id=uuid4(),
            state_adapter=adapter,
            execute_rebuild=lambda context: _outcome(
                scope=RebuildScope.CAPTURE_AND_TARGET,
                replacement=context.before_state.replacement,
            ),
        )

    assert adapter.read_state(DATASET_ID) == before


def test_failed_rebuild_gate_never_cuts_over_old_runtime_state():
    adapter = InMemoryFullRebuildStateAdapter()
    before = adapter.seed_state(DATASET_ID, _replacement(marker=10))

    with pytest.raises(FullRebuildGateError, match="cannot cut over"):
        execute_full_rebuild(
            request=_request(),
            dataset_run_id=uuid4(),
            state_adapter=adapter,
            execute_rebuild=lambda context: _outcome(
                scope=context.rebuild_scope,
                replacement=_replacement(marker=200),
                gate=StateCommitGate(
                    target_committed=True,
                    reconciliation_required=True,
                    reconciliation_passed=False,
                ),
            ),
        )

    assert adapter.read_state(DATASET_ID) == before


def test_rebuild_requires_explicit_completion_evidence():
    adapter = InMemoryFullRebuildStateAdapter()

    with pytest.raises(FullRebuildGateError, match="did not prove authoritative"):
        execute_full_rebuild(
            request=_request(),
            dataset_run_id=uuid4(),
            state_adapter=adapter,
            execute_rebuild=lambda context: _outcome(
                scope=context.rebuild_scope,
                replacement=_replacement(),
                completed=False,
            ),
        )


def test_rebuild_callback_failure_preserves_committed_runtime_state():
    adapter = InMemoryFullRebuildStateAdapter()
    before = adapter.seed_state(DATASET_ID, _replacement(marker=10))

    def fail(_context):
        raise RuntimeError("authoritative source unavailable")

    with pytest.raises(RuntimeError, match="source unavailable"):
        execute_full_rebuild(
            request=_request(),
            dataset_run_id=uuid4(),
            state_adapter=adapter,
            execute_rebuild=fail,
        )

    assert adapter.read_state(DATASET_ID) == before


def test_same_rebuild_request_is_idempotent_across_attempt_specific_dataset_runs():
    adapter = InMemoryFullRebuildStateAdapter()
    request = _request(RebuildScope.CAPTURE_AND_TARGET)
    first_run_id = uuid4()
    callback_request_ids = []

    first = execute_full_rebuild(
        request=request,
        dataset_run_id=first_run_id,
        state_adapter=adapter,
        execute_rebuild=lambda context: (
            callback_request_ids.append(context.rebuild_request_id)
            or _outcome(
                scope=context.rebuild_scope,
                replacement=_replacement(marker=300),
            )
        ),
    )
    assert first.already_rebuilt is False

    calls = 0

    def must_not_rebuild(_context):
        nonlocal calls
        calls += 1
        raise AssertionError("same rebuild request must not destructively execute again")

    second = execute_full_rebuild(
        request=request,
        dataset_run_id=uuid4(),
        state_adapter=adapter,
        execute_rebuild=must_not_rebuild,
    )

    assert second.already_rebuilt is True
    assert second.rebuild_scope is RebuildScope.CAPTURE_AND_TARGET
    assert second.value is None
    assert calls == 0
    assert callback_request_ids == [request.reprocess_request_id]
    assert second.state.last_rebuild_dataset_run_id == first_run_id


def test_runtime_state_version_change_during_rebuild_fails_closed_after_target_work():
    adapter = InMemoryFullRebuildStateAdapter()
    before = adapter.seed_state(DATASET_ID, _replacement(marker=10))

    def rebuild_with_concurrent_state_change(context):
        adapter.seed_state(DATASET_ID, _replacement(marker=50))
        return _outcome(
            scope=context.rebuild_scope,
            replacement=_replacement(marker=100),
            value="target rebuilt",
        )

    with pytest.raises(FullRebuildStateVersionConflict, match="expected version"):
        execute_full_rebuild(
            request=_request(),
            dataset_run_id=uuid4(),
            state_adapter=adapter,
            execute_rebuild=rebuild_with_concurrent_state_change,
        )

    current = adapter.read_state(DATASET_ID)
    assert current.version == before.version + 1
    assert current.replacement == _replacement(marker=50)
    assert current.last_rebuild_request_id is None


def test_authoritative_reset_can_delegate_progress_to_external_owner():
    replacement = FullRebuildStateReplacement(
        progress_kind=RebuildProgressKind.EXTERNAL,
        progress_payload={
            "external_checkpoint_reference": "kafka://crm/customer/group-a@partition0:420"
        },
        dataset_state={"bootstrap_complete": True},
        source_boundary_reference="snapshot-fence-420",
    )
    adapter = InMemoryFullRebuildStateAdapter()

    result = execute_full_rebuild(
        request=_request(RebuildScope.AUTHORITATIVE_RESET),
        dataset_run_id=uuid4(),
        state_adapter=adapter,
        execute_rebuild=lambda context: _outcome(
            scope=context.rebuild_scope,
            replacement=replacement,
        ),
    )

    assert result.state.replacement is not None
    assert result.state.replacement.progress_kind is RebuildProgressKind.EXTERNAL
    assert result.state.replacement.progress_payload["external_checkpoint_reference"].endswith(
        "partition0:420"
    )
