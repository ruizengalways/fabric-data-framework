from __future__ import annotations

from collections import deque
from uuid import UUID, uuid4

from fabric_data_framework.recovery.fabric_warehouse_session_absence import (
    FabricWarehouseSessionBinding,
    FabricWarehouseSessionState,
    FabricWarehouseSessionTerminationAbsenceCertifier,
    capture_fabric_warehouse_session_binding,
)
from fabric_data_framework.recovery.target_probe import TargetCommitProbeRequest
from fabric_data_framework.contracts.target_operation import TargetOperationStatus


CONNECTION_ID = UUID("11111111-2222-3333-4444-555555555555")
OPERATION_KEY = "a" * 64


class FakeAuthority:
    def __init__(self, observations, *, terminate_error: Exception | None = None):
        self.observations = deque(observations)
        self.terminate_error = terminate_error
        self.terminated: list[FabricWarehouseSessionBinding] = []

    def observe(self, binding):
        value = self.observations.popleft()
        if isinstance(value, Exception):
            raise value
        return value

    def terminate(self, binding):
        self.terminated.append(binding)
        if self.terminate_error is not None:
            raise self.terminate_error


class FakeMarkerStore:
    def __init__(self, marker_reads):
        self.marker_reads = deque(marker_reads)
        self.read_operation_keys: list[str] = []

    def read_markers(self, operation_key):
        self.read_operation_keys.append(operation_key)
        value = self.marker_reads.popleft()
        if isinstance(value, Exception):
            raise value
        return value

    def marker_reference(self, operation_key):
        return f"fabric-warehouse-marker:dbo.marker:{operation_key}"


class FakeMappings:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


class FakeResult:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return FakeMappings(self.row)


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.statements = []

    def execute(self, statement, parameters=None):
        self.statements.append((str(statement), parameters))
        return FakeResult(self.row)


def _binding():
    return FabricWarehouseSessionBinding(
        session_id=81,
        connection_id=CONNECTION_ID,
    )


def _open_state(*, transaction_count=1, session_id=81, connection_id=CONNECTION_ID):
    return FabricWarehouseSessionState(
        session_id=session_id,
        connection_id=connection_id,
        open_transaction_count=transaction_count,
    )


def _request():
    return TargetCommitProbeRequest(
        operation_key=OPERATION_KEY,
        dataset_id="sales.order",
        operation_kind="EVIDENCE_MERGE",
        target_reference="warehouse.dbo.sales_order",
        effective_config_hash="b" * 64,
        input_fingerprint="c" * 64,
        current_status=TargetOperationStatus.UNKNOWN,
        current_version=2,
        owner_dataset_run_id=uuid4(),
        owner_attempt=1,
    )


def test_capture_session_binding_uses_exact_connection_and_session_identity():
    connection = FakeConnection(
        {
            "connection_id": str(CONNECTION_ID),
            "session_id": 81,
        }
    )

    binding = capture_fabric_warehouse_session_binding(connection)

    assert binding == _binding()
    sql = connection.statements[0][0]
    assert "sys.dm_exec_connections" in sql
    assert "@@SPID" in sql


def test_absence_certifier_requires_open_transaction_kill_disappearance_and_second_marker_absence():
    binding = _binding()
    authority = FakeAuthority([_open_state(), None])
    marker_store = FakeMarkerStore([()])
    certifier = FabricWarehouseSessionTerminationAbsenceCertifier(
        binding=binding,
        authority=authority,
        marker_store=marker_store,
    )

    evidence = certifier.certify_absence(_request())

    assert evidence.safe_to_retry is True
    assert evidence.evidence_reference == binding.evidence_reference
    assert authority.terminated == [binding]
    assert marker_store.read_operation_keys == [OPERATION_KEY]
    assert "post-termination target marker remains absent" in (evidence.detail or "")


def test_session_disappearance_before_termination_is_unresolved_and_never_killed():
    binding = _binding()
    authority = FakeAuthority([None])
    marker_store = FakeMarkerStore([()])
    certifier = FabricWarehouseSessionTerminationAbsenceCertifier(
        binding=binding,
        authority=authority,
        marker_store=marker_store,
    )

    evidence = certifier.certify_absence(_request())

    assert evidence.safe_to_retry is False
    assert authority.terminated == []
    assert marker_store.read_operation_keys == []
    assert "cannot distinguish commit from rollback" in (evidence.detail or "")


def test_session_without_open_transaction_is_unresolved_and_never_killed():
    binding = _binding()
    authority = FakeAuthority([_open_state(transaction_count=0)])
    marker_store = FakeMarkerStore([()])
    certifier = FabricWarehouseSessionTerminationAbsenceCertifier(
        binding=binding,
        authority=authority,
        marker_store=marker_store,
    )

    evidence = certifier.certify_absence(_request())

    assert evidence.safe_to_retry is False
    assert authority.terminated == []
    assert marker_store.read_operation_keys == []
    assert "no observable open transaction" in (evidence.detail or "")


def test_mismatched_connection_identity_is_unresolved_and_never_killed():
    binding = _binding()
    authority = FakeAuthority(
        [_open_state(connection_id=UUID("99999999-2222-3333-4444-555555555555"))]
    )
    marker_store = FakeMarkerStore([()])
    certifier = FabricWarehouseSessionTerminationAbsenceCertifier(
        binding=binding,
        authority=authority,
        marker_store=marker_store,
    )

    evidence = certifier.certify_absence(_request())

    assert evidence.safe_to_retry is False
    assert authority.terminated == []
    assert marker_store.read_operation_keys == []
    assert "does not match retained binding" in (evidence.detail or "")


def test_termination_failure_is_secret_safe_and_never_certifies_retry():
    binding = _binding()
    authority = FakeAuthority(
        [_open_state()],
        terminate_error=RuntimeError("KILL failed password=should-not-persist"),
    )
    marker_store = FakeMarkerStore([()])
    certifier = FabricWarehouseSessionTerminationAbsenceCertifier(
        binding=binding,
        authority=authority,
        marker_store=marker_store,
    )

    evidence = certifier.certify_absence(_request())

    assert evidence.safe_to_retry is False
    rendered = evidence.model_dump_json()
    assert "RuntimeError" in rendered
    assert "should-not-persist" not in rendered
    assert "password=" not in rendered.lower()
    assert marker_store.read_operation_keys == []


def test_post_termination_session_still_visible_blocks_retry():
    binding = _binding()
    authority = FakeAuthority([_open_state(), _open_state()])
    marker_store = FakeMarkerStore([()])
    certifier = FabricWarehouseSessionTerminationAbsenceCertifier(
        binding=binding,
        authority=authority,
        marker_store=marker_store,
    )

    evidence = certifier.certify_absence(_request())

    assert evidence.safe_to_retry is False
    assert authority.terminated == [binding]
    assert marker_store.read_operation_keys == []
    assert "remains observable" in (evidence.detail or "")


def test_marker_appearing_during_termination_race_forbids_not_committed():
    binding = _binding()
    authority = FakeAuthority([_open_state(), None])
    marker = type("Marker", (), {"native_operation_id": "native-42"})()
    marker_store = FakeMarkerStore([(marker,)])
    certifier = FabricWarehouseSessionTerminationAbsenceCertifier(
        binding=binding,
        authority=authority,
        marker_store=marker_store,
    )

    evidence = certifier.certify_absence(_request())

    assert evidence.safe_to_retry is False
    assert evidence.native_operation_id == "native-42"
    assert evidence.evidence_reference.endswith(OPERATION_KEY)
    assert "commit may have won the race" in (evidence.detail or "")


def test_post_termination_marker_read_failure_is_secret_safe_and_unresolved():
    binding = _binding()
    authority = FakeAuthority([_open_state(), None])
    marker_store = FakeMarkerStore(
        [RuntimeError("marker read failed Authorization: Bearer should-not-persist")]
    )
    certifier = FabricWarehouseSessionTerminationAbsenceCertifier(
        binding=binding,
        authority=authority,
        marker_store=marker_store,
    )

    evidence = certifier.certify_absence(_request())

    assert evidence.safe_to_retry is False
    rendered = evidence.model_dump_json()
    assert "RuntimeError" in rendered
    assert "should-not-persist" not in rendered
    assert "Authorization" not in rendered
