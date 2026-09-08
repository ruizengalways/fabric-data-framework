import pytest

from fabric_data_framework.contracts.target_version import (
    TargetCutoverGate,
    TargetCutoverRequest,
    TargetVersionSpec,
)
from fabric_data_framework.recovery.target_cutover import (
    InMemoryTargetCutoverAdapter,
    TargetCutoverConflict,
    TargetCutoverGateError,
    execute_target_cutover,
)


def _candidate(version: str = "v2", physical: str = "customer_v2") -> TargetVersionSpec:
    return TargetVersionSpec(
        dataset_id="silver.customer",
        layer="silver",
        logical_object="customer",
        physical_object=physical,
        version=version,
    )


def _request() -> TargetCutoverRequest:
    return TargetCutoverRequest(
        dataset_id="silver.customer",
        environment="PROD",
        logical_object="customer",
        from_version="v1",
        to_version="v2",
        requested_by="data-ops",
        reason="UAT approved corrected Silver logic",
        approval_reference="CAB-2026-0908-001",
    )


def _gate(**updates) -> TargetCutoverGate:
    values = {
        "candidate_built": True,
        "reconciliation_passed": True,
        "consumer_validation_passed": True,
        "validation_reference": "uat://customer/v2/pass",
        "approval_reference": "CAB-2026-0908-001",
    }
    values.update(updates)
    return TargetCutoverGate(**values)


def _adapter() -> InMemoryTargetCutoverAdapter:
    adapter = InMemoryTargetCutoverAdapter()
    adapter.seed_active(
        dataset_id="silver.customer",
        environment="PROD",
        logical_object="customer",
        version="v1",
        physical_object="customer_v1",
    )
    return adapter


def test_versioned_target_requires_distinct_logical_and_physical_objects():
    with pytest.raises(ValueError, match="must differ"):
        TargetVersionSpec(
            dataset_id="silver.customer",
            layer="silver",
            logical_object="customer",
            physical_object="customer",
            version="v2",
        )


def test_cutover_requires_all_candidate_reconciliation_and_consumer_validation_gates():
    for field in (
        "candidate_built",
        "reconciliation_passed",
        "consumer_validation_passed",
    ):
        adapter = _adapter()
        with pytest.raises(TargetCutoverGateError, match="requires candidate build"):
            execute_target_cutover(
                request=_request(),
                candidate=_candidate(),
                gate=_gate(**{field: False}),
                adapter=adapter,
            )
        current = adapter.read_active(
            dataset_id="silver.customer",
            environment="PROD",
            logical_object="customer",
        )
        assert current.version == "v1"
        assert current.physical_object == "customer_v1"


def test_cutover_requires_exact_approval_reference():
    adapter = _adapter()
    with pytest.raises(TargetCutoverGateError, match="approval_reference"):
        execute_target_cutover(
            request=_request(),
            candidate=_candidate(),
            gate=_gate(approval_reference="different-approval"),
            adapter=adapter,
        )


def test_cutover_promotes_stable_logical_object_to_v2_without_deleting_v1_identity():
    adapter = _adapter()
    request = _request()
    result = execute_target_cutover(
        request=request,
        candidate=_candidate(),
        gate=_gate(),
        adapter=adapter,
    )

    assert result.already_promoted is False
    assert result.before.version == "v1"
    assert result.before.physical_object == "customer_v1"
    assert result.after.version == "v2"
    assert result.after.physical_object == "customer_v2"
    assert result.after.generation == result.before.generation + 1
    assert result.after.last_cutover_request_id == request.cutover_request_id


def test_same_cutover_request_is_idempotent():
    adapter = _adapter()
    request = _request()
    candidate = _candidate()

    first = execute_target_cutover(
        request=request,
        candidate=candidate,
        gate=_gate(),
        adapter=adapter,
    )
    second = execute_target_cutover(
        request=request,
        candidate=candidate,
        gate=_gate(),
        adapter=adapter,
    )

    assert first.after.version == "v2"
    assert second.already_promoted is True
    assert second.after.version == "v2"
    assert second.after.generation == first.after.generation


def test_cutover_fails_when_active_or_candidate_identity_does_not_match_request():
    adapter = _adapter()
    with pytest.raises(TargetCutoverConflict, match="candidate version"):
        execute_target_cutover(
            request=_request(),
            candidate=_candidate(version="v3", physical="customer_v3"),
            gate=_gate(),
            adapter=adapter,
        )

    request = _request()
    first = execute_target_cutover(
        request=request,
        candidate=_candidate(),
        gate=_gate(),
        adapter=adapter,
    )
    assert first.after.version == "v2"

    with pytest.raises(TargetCutoverConflict, match="active version"):
        execute_target_cutover(
            request=TargetCutoverRequest(
                dataset_id="silver.customer",
                environment="PROD",
                logical_object="customer",
                from_version="v1",
                to_version="v3",
                requested_by="data-ops",
                reason="incorrect stale cutover request",
                approval_reference="CAB-2026-0908-002",
            ),
            candidate=_candidate(version="v3", physical="customer_v3"),
            gate=TargetCutoverGate(
                candidate_built=True,
                reconciliation_passed=True,
                consumer_validation_passed=True,
                validation_reference="uat://customer/v3/pass",
                approval_reference="CAB-2026-0908-002",
            ),
            adapter=adapter,
        )
