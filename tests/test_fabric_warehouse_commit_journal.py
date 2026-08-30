from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select

from fabric_data_framework.control_plane.schema import apply_baseline_schema, dataset
from fabric_data_framework.recovery.fabric_warehouse import (
    FabricWarehouseMarkerStore,
    FabricWarehouseMutationEvidence,
    FabricWarehouseTargetCommitProbe,
    build_fabric_warehouse_operation_marker_table,
)
from fabric_data_framework.recovery.target_probe import probe_and_reconcile_target_operation
from fabric_data_framework.control_plane.target_operation_journal import (
    claim_target_operation,
    mark_target_operation_unknown,
)
from fabric_data_framework.contracts.target_operation import (
    TargetOperationAction,
    TargetOperationIntent,
    TargetOperationStatus,
)


def _control_plane():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    apply_baseline_schema(engine)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            dataset.insert().values(
                dataset_id="sales.order",
                domain="sales",
                source_system="erp",
                source_object="sales_order",
                target_layer="gold",
                target_object="sales_order",
                enabled_default=True,
                criticality="CRITICAL",
                execution_group="sales",
                config_schema_version=1,
                config_hash="a" * 64,
                domain_git_sha="b" * 40,
                framework_version="0.4.0",
                created_at=now,
                updated_at=None,
            )
        )
    return engine


def _warehouse(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'warehouse-journal.db'}")
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


def test_committed_warehouse_marker_converges_unknown_framework_operation_to_succeeded(tmp_path):
    control = _control_plane()
    warehouse, target, marker_store = _warehouse(tmp_path)
    intent = TargetOperationIntent(
        dataset_id="sales.order",
        operation_kind="MERGE",
        target_reference="warehouse.dbo.sales_order",
        effective_config_hash="c" * 64,
        input_fingerprint="d" * 64,
    )
    first_run = uuid4()
    claim = claim_target_operation(
        control,
        intent=intent,
        dataset_run_id=first_run,
        attempt=1,
    )
    assert claim.action is TargetOperationAction.EXECUTE

    marker_result = marker_store.execute_atomic(
        intent=intent,
        dataset_run_id=first_run,
        attempt=1,
        mutation=lambda connection, _: (
            connection.execute(target.insert().values(order_id=1, value="committed")),
            FabricWarehouseMutationEvidence(native_operation_id="statement-live-123"),
        )[1],
    )
    assert marker_result.executed is True

    # Simulate loss of the client acknowledgement after the target transaction committed.
    unknown = mark_target_operation_unknown(
        control,
        operation_key=intent.operation_key,
        expected_version=claim.record.version,
        dataset_run_id=first_run,
        attempt=1,
        error_message="connection lost around COMMIT acknowledgement",
    )
    assert unknown.status is TargetOperationStatus.UNKNOWN

    retry_run = uuid4()
    reconciled = probe_and_reconcile_target_operation(
        control,
        operation_key=intent.operation_key,
        dataset_run_id=retry_run,
        attempt=2,
        probe=FabricWarehouseTargetCommitProbe(marker_store=marker_store),
    )

    assert reconciled.record.status is TargetOperationStatus.SUCCEEDED
    assert reconciled.record.outcome_reference == marker_store.marker_reference(
        intent.operation_key
    )
    assert reconciled.evidence.native_operation_id == "statement-live-123"

    blocked_reexecution = claim_target_operation(
        control,
        intent=intent,
        dataset_run_id=uuid4(),
        attempt=3,
    )
    assert blocked_reexecution.action is TargetOperationAction.SKIP_SUCCEEDED

    with warehouse.connect() as connection:
        target_rows = connection.execute(select(target)).mappings().all()
    assert [dict(row) for row in target_rows] == [{"order_id": 1, "value": "committed"}]
