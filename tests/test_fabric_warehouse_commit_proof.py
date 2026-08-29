from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select

from fabric_data_framework.contracts.recovery import UnknownOutcomeResolution
from fabric_data_framework.recovery.fabric_warehouse import (
    FabricWarehouseAbsenceEvidence,
    FabricWarehouseMarkerStore,
    FabricWarehouseMutationEvidence,
    FabricWarehouseSecondaryCorrelation,
    FabricWarehouseTargetCommitProbe,
    build_fabric_warehouse_operation_marker_table,
)
from fabric_data_framework.recovery.target_probe import TargetCommitProbeRequest
from fabric_data_framework.target_operations import (
    TargetOperationIntent,
    TargetOperationStatus,
)


def _intent() -> TargetOperationIntent:
    return TargetOperationIntent(
        dataset_id="sales.order",
        operation_kind="MERGE",
        target_reference="warehouse.dbo.sales_order",
        effective_config_hash="a" * 64,
        input_fingerprint="b" * 64,
    )


def _probe_request(intent: TargetOperationIntent) -> TargetCommitProbeRequest:
    return TargetCommitProbeRequest(
        operation_key=intent.operation_key,
        dataset_id=intent.dataset_id,
        operation_kind=intent.operation_kind,
        target_reference=intent.target_reference,
        effective_config_hash=intent.effective_config_hash,
        input_fingerprint=intent.input_fingerprint,
        current_status=TargetOperationStatus.UNKNOWN,
        current_version=2,
        owner_dataset_run_id=uuid4(),
        owner_attempt=1,
    )


def _target_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'warehouse.db'}")
    metadata = MetaData()
    target = Table(
        "sales_order",
        metadata,
        Column("order_id", Integer, nullable=False),
        Column("value", String(100), nullable=False),
    )
    marker = build_fabric_warehouse_operation_marker_table(metadata, schema=None)
    metadata.create_all(engine)
    return engine, target, FabricWarehouseMarkerStore(engine, marker)


def test_marker_store_requires_explicitly_deployed_target_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'missing.db'}")
    marker = build_fabric_warehouse_operation_marker_table(MetaData(), schema=None)

    with pytest.raises(RuntimeError, match="marker table is not deployed"):
        FabricWarehouseMarkerStore(engine, marker)


def test_target_mutation_and_marker_commit_atomically_and_reentry_does_not_reexecute(tmp_path):
    engine, target, store = _target_store(tmp_path)
    intent = _intent()
    dataset_run_id = uuid4()
    calls = []

    def mutate(connection, observed_intent):
        calls.append(observed_intent.operation_key)
        connection.execute(target.insert().values(order_id=1, value="committed"))
        return FabricWarehouseMutationEvidence(
            native_operation_id="statement-123",
            query_label="FDF_TARGET_SALES_ORDER",
            detail="merge completed before marker insert in same transaction",
        )

    first = store.execute_atomic(
        intent=intent,
        dataset_run_id=dataset_run_id,
        attempt=1,
        mutation=mutate,
    )
    second = store.execute_atomic(
        intent=intent,
        dataset_run_id=uuid4(),
        attempt=2,
        mutation=mutate,
    )

    assert first.executed is True
    assert second.executed is False
    assert first.marker.operation_key == intent.operation_key
    assert first.marker.native_operation_id == "statement-123"
    assert second.marker.operation_key == intent.operation_key
    assert calls == [intent.operation_key]
    with engine.connect() as connection:
        rows = connection.execute(select(target)).mappings().all()
    assert [dict(row) for row in rows] == [{"order_id": 1, "value": "committed"}]
    assert len(store.read_markers(intent.operation_key)) == 1


def test_mutation_failure_rolls_back_target_change_and_never_commits_marker(tmp_path):
    engine, target, store = _target_store(tmp_path)
    intent = _intent()

    def mutate(connection, _):
        connection.execute(target.insert().values(order_id=1, value="must_rollback"))
        raise RuntimeError("target mutation failed")

    with pytest.raises(RuntimeError, match="target mutation failed"):
        store.execute_atomic(
            intent=intent,
            dataset_run_id=uuid4(),
            attempt=1,
            mutation=mutate,
        )

    with engine.connect() as connection:
        target_count = len(connection.execute(select(target)).all())
    assert target_count == 0
    assert store.read_markers(intent.operation_key) == ()


def test_committed_marker_is_primary_probe_proof(tmp_path):
    _, target, store = _target_store(tmp_path)
    intent = _intent()

    def mutate(connection, _):
        connection.execute(target.insert().values(order_id=1, value="committed"))
        return FabricWarehouseMutationEvidence(native_operation_id="statement-abc")

    store.execute_atomic(
        intent=intent,
        dataset_run_id=uuid4(),
        attempt=1,
        mutation=mutate,
    )
    evidence = FabricWarehouseTargetCommitProbe(marker_store=store).probe(
        _probe_request(intent)
    )

    assert evidence.resolution is UnknownOutcomeResolution.COMMITTED
    assert evidence.native_operation_id == "statement-abc"
    assert evidence.evidence_reference == store.marker_reference(intent.operation_key)
    assert "committed marker rows=1" in (evidence.detail or "")


def test_marker_absence_is_unresolved_without_independent_absence_proof(tmp_path):
    _, _, store = _target_store(tmp_path)
    intent = _intent()

    evidence = FabricWarehouseTargetCommitProbe(marker_store=store).probe(
        _probe_request(intent)
    )

    assert evidence.resolution is UnknownOutcomeResolution.UNRESOLVED
    assert evidence.evidence_reference is None
    assert "absence alone is not proof" in (evidence.detail or "")


def test_secondary_query_correlation_never_promotes_absent_marker_to_committed(tmp_path):
    _, _, store = _target_store(tmp_path)
    intent = _intent()

    class CorrelationReader:
        def lookup(self, request):
            assert request.operation_key == intent.operation_key
            return (
                FabricWarehouseSecondaryCorrelation(
                    native_operation_id="distributed-statement-123",
                    evidence_reference="queryinsights:distributed-statement-123",
                    detail="completed query history row",
                ),
            )

    evidence = FabricWarehouseTargetCommitProbe(
        marker_store=store,
        secondary_correlation_reader=CorrelationReader(),
    ).probe(_probe_request(intent))

    assert evidence.resolution is UnknownOutcomeResolution.UNRESOLVED
    assert evidence.native_operation_id == "distributed-statement-123"
    assert "secondary_correlations=1" in (evidence.detail or "")


def test_independent_absence_certification_can_resolve_not_committed(tmp_path):
    _, _, store = _target_store(tmp_path)
    intent = _intent()

    class AbsenceCertifier:
        def certify_absence(self, request):
            assert request.operation_key == intent.operation_key
            return FabricWarehouseAbsenceEvidence(
                safe_to_retry=True,
                evidence_reference="warehouse-session-recovery:attempt-42",
                detail="provider session recovery proves prior transaction rolled back",
            )

    evidence = FabricWarehouseTargetCommitProbe(
        marker_store=store,
        absence_certifier=AbsenceCertifier(),
    ).probe(_probe_request(intent))

    assert evidence.resolution is UnknownOutcomeResolution.NOT_COMMITTED
    assert evidence.evidence_reference == "warehouse-session-recovery:attempt-42"


def test_absence_certifier_that_cannot_prove_retry_safety_remains_unresolved(tmp_path):
    _, _, store = _target_store(tmp_path)
    intent = _intent()

    class AbsenceCertifier:
        def certify_absence(self, request):
            return FabricWarehouseAbsenceEvidence(
                safe_to_retry=False,
                evidence_reference="warehouse-session-recovery:inconclusive",
                detail="connection outcome still ambiguous",
            )

    evidence = FabricWarehouseTargetCommitProbe(
        marker_store=store,
        absence_certifier=AbsenceCertifier(),
    ).probe(_probe_request(intent))

    assert evidence.resolution is UnknownOutcomeResolution.UNRESOLVED
    assert evidence.evidence_reference == "warehouse-session-recovery:inconclusive"


def test_marker_timestamp_round_trip_is_utc_aware(tmp_path):
    _, target, store = _target_store(tmp_path)
    intent = _intent()

    result = store.execute_atomic(
        intent=intent,
        dataset_run_id=uuid4(),
        attempt=1,
        mutation=lambda connection, _: (
            connection.execute(target.insert().values(order_id=1, value="committed")),
            FabricWarehouseMutationEvidence(),
        )[1],
    )
    persisted = store.read_markers(intent.operation_key)[0]

    assert result.marker.recorded_at.tzinfo is not None
    assert persisted.recorded_at.tzinfo is not None
    assert persisted.recorded_at.utcoffset() == timezone.utc.utcoffset(
        datetime.now(timezone.utc)
    )
