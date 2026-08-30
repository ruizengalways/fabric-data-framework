from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
)
from fabric_data_framework.control_plane.schema import (
    capture_receipt,
    cdc_checkpoint,
    dataset_attempt_lineage,
    dataset_run,
    pipeline_run,
    quarantine_batch,
    reconciliation_result,
    reprocess_request,
    schema_change,
    watermark,
)
from fabric_data_framework.deployment.delivery import materialize_semantic_metadata
from fabric_data_framework.control_plane.operator import (
    get_dataset_operational_snapshot,
    list_dataset_operational_snapshots,
)


BASE = datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc)


def _watermark_config(dataset_id: str = "erp.order") -> DatasetConfig:
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(system="erp", object="dbo.Order", connection_ref="erp_ro"),
        target=TargetConfig(layer="silver", object=dataset_id.replace(".", "_")),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.UPSERT,
            merge_key=("order_id",),
            watermark=WatermarkConfig(column="modified_at", tie_breaker=("order_id",)),
            event_time_column="modified_at",
        ),
        orchestration=OrchestrationPolicy(execution_group="erp_incremental"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
    )


def _cdc_config(dataset_id: str = "erp.order_cdc") -> DatasetConfig:
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(system="erp", object="dbo.OrderCDC", connection_ref="erp_ro"),
        target=TargetConfig(layer="silver", object=dataset_id.replace(".", "_")),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.CDC,
            apply_strategy=ApplyStrategy.UPSERT,
            merge_key=("order_id",),
        ),
        orchestration=OrchestrationPolicy(execution_group="erp_cdc"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
    )


def _engine(tmp_path, *configs: DatasetConfig):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    materialize_semantic_metadata(
        engine,
        configs=configs,
        domain="orders",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )
    return engine


def _insert_pipeline(connection, pipeline_id, *, started_at=BASE):
    connection.execute(
        pipeline_run.insert().values(
            pipeline_run_id=str(pipeline_id),
            environment="DEV",
            domain="orders",
            status="SUCCESS",
            run_mode="NORMAL",
            domain_git_sha="a" * 40,
            framework_version="0.4.0",
            config_bundle_hash="b" * 64,
            deployment_id=None,
            started_at=started_at,
            completed_at=started_at + timedelta(minutes=1),
        )
    )


def _insert_dataset_run(
    connection,
    *,
    run_id,
    pipeline_id,
    dataset_id,
    attempt,
    status,
    started_at,
    error_code=None,
):
    connection.execute(
        dataset_run.insert().values(
            dataset_run_id=str(run_id),
            pipeline_run_id=str(pipeline_id),
            dataset_id=dataset_id,
            attempt=attempt,
            status=status,
            effective_config_hash="c" * 64,
            rows_read=10,
            rows_accepted=9,
            rows_quarantined=1,
            rows_filtered=0,
            rows_inserted=7,
            rows_updated=2,
            rows_deleted=0,
            error_code=error_code,
            error_message="boom" if error_code else None,
            retryable=True if error_code else None,
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=30),
        )
    )


def test_operator_snapshot_requires_deployed_dataset(tmp_path):
    engine = _engine(tmp_path, _watermark_config())

    with pytest.raises(KeyError, match="dataset not deployed"):
        get_dataset_operational_snapshot(engine, "erp.missing")

    with pytest.raises(ValueError, match="reprocess_limit"):
        get_dataset_operational_snapshot(engine, "erp.order", reprocess_limit=0)


def test_operator_snapshot_is_safe_when_runtime_evidence_is_empty(tmp_path):
    engine = _engine(tmp_path, _watermark_config())

    snapshot = get_dataset_operational_snapshot(engine, "erp.order")

    assert snapshot.dataset_id == "erp.order"
    assert snapshot.latest_run is None
    assert snapshot.latest_capture is None
    assert snapshot.watermark is None
    assert snapshot.cdc_checkpoint is None
    assert snapshot.latest_reconciliation is None
    assert snapshot.latest_schema_change is None
    assert snapshot.quarantine_backlog.open_batches == 0
    assert snapshot.quarantine_backlog.open_rows == 0
    assert snapshot.active_reprocess_requests == ()


def test_operator_snapshot_joins_latest_run_lineage_capture_and_health_evidence(tmp_path):
    engine = _engine(tmp_path, _watermark_config())
    pipeline_id = uuid4()
    first_run = uuid4()
    latest_run = uuid4()
    reprocess_id = uuid4()
    receipt_id = uuid4()
    old_receipt_id = uuid4()
    reconciliation_id = uuid4()
    schema_change_id = uuid4()
    open_quarantine_id = uuid4()
    replayed_quarantine_id = uuid4()

    with engine.begin() as connection:
        _insert_pipeline(connection, pipeline_id)
        _insert_dataset_run(
            connection,
            run_id=first_run,
            pipeline_id=pipeline_id,
            dataset_id="erp.order",
            attempt=1,
            status="FAILED",
            started_at=BASE,
            error_code="TRANSIENT_SOURCE",
        )
        _insert_dataset_run(
            connection,
            run_id=latest_run,
            pipeline_id=pipeline_id,
            dataset_id="erp.order",
            attempt=2,
            status="SUCCEEDED",
            started_at=BASE + timedelta(minutes=2),
        )
        connection.execute(
            reprocess_request.insert().values(
                reprocess_request_id=str(reprocess_id),
                dataset_id="erp.order",
                run_mode="RETRY",
                reason="retry transient source",
                requested_by="oncall",
                original_pipeline_run_id=str(pipeline_id),
                original_dataset_run_id=str(first_run),
                range_json=None,
                status="RUNNING",
                created_at=BASE + timedelta(minutes=1),
                updated_at=None,
            )
        )
        connection.execute(
            dataset_attempt_lineage.insert().values(
                dataset_run_id=str(latest_run),
                dataset_id="erp.order",
                root_dataset_run_id=str(first_run),
                previous_dataset_run_id=str(first_run),
                attempt=2,
                run_mode="RETRY",
                reprocess_request_id=str(reprocess_id),
                created_at=BASE + timedelta(minutes=2),
            )
        )
        for current_receipt_id, current_run, completed_at, native_run in (
            (old_receipt_id, first_run, BASE + timedelta(seconds=20), "copy-old"),
            (receipt_id, latest_run, BASE + timedelta(minutes=2, seconds=20), "copy-new"),
        ):
            connection.execute(
                capture_receipt.insert().values(
                    capture_receipt_id=str(current_receipt_id),
                    dataset_run_id=str(current_run),
                    dataset_id="erp.order",
                    capture_strategy="WATERMARK",
                    execution_engine="FABRIC_COPY_ACTIVITY",
                    progress_owner="FRAMEWORK",
                    native_run_id=native_run,
                    source_reference="erp/orders",
                    landing_reference="bronze/orders",
                    rows_read=10,
                    rows_written=10,
                    source_lower_bound={"modified_at": "2026-08-29T00:00:00Z"},
                    source_upper_bound={"modified_at": "2026-08-29T01:00:00Z"},
                    snapshot_id=None,
                    complete_snapshot=None,
                    external_checkpoint_reference=None,
                    schema_version="3",
                    started_at=completed_at - timedelta(seconds=10),
                    completed_at=completed_at,
                    created_at=completed_at,
                )
            )
        connection.execute(
            watermark.insert().values(
                dataset_id="erp.order",
                committed_value="2026-08-29T01:00:00Z",
                committed_tie_breaker="O-100",
                committed_dataset_run_id=str(latest_run),
                version=4,
                created_at=BASE,
                updated_at=BASE + timedelta(minutes=3),
            )
        )
        connection.execute(
            reconciliation_result.insert().values(
                reconciliation_id=str(reconciliation_id),
                dataset_run_id=str(latest_run),
                dataset_id="erp.order",
                policy_name="standard",
                status="PASS",
                metrics={"source": 10, "target": 10},
                blocks_state_advance=False,
                created_at=BASE + timedelta(minutes=2, seconds=25),
            )
        )
        connection.execute(
            quarantine_batch.insert().values(
                quarantine_id=str(open_quarantine_id),
                dataset_run_id=str(latest_run),
                dataset_id="erp.order",
                scope="ROW",
                row_count=3,
                reason_code="BAD_AMOUNT",
                reason_detail=None,
                source_reference="quarantine/open",
                replayed_by_dataset_run_id=None,
                created_at=BASE + timedelta(minutes=2),
            )
        )
        connection.execute(
            quarantine_batch.insert().values(
                quarantine_id=str(replayed_quarantine_id),
                dataset_run_id=str(first_run),
                dataset_id="erp.order",
                scope="ROW",
                row_count=99,
                reason_code="OLD",
                reason_detail=None,
                source_reference="quarantine/replayed",
                replayed_by_dataset_run_id=str(latest_run),
                created_at=BASE,
            )
        )
        connection.execute(
            schema_change.insert().values(
                schema_change_id=str(schema_change_id),
                dataset_id="erp.order",
                dataset_run_id=str(latest_run),
                observed_fingerprint="d" * 64,
                expected_fingerprint="e" * 64,
                classification="COMPATIBLE",
                details={"changes": ["added nullable currency"]},
                observed_at=BASE + timedelta(minutes=2, seconds=10),
            )
        )

    snapshot = get_dataset_operational_snapshot(engine, "erp.order")

    assert snapshot.latest_run is not None
    assert snapshot.latest_run.dataset_run_id == latest_run
    assert snapshot.latest_run.status == "SUCCEEDED"
    assert snapshot.latest_run.run_mode.value == "RETRY"
    assert snapshot.latest_run.root_dataset_run_id == first_run
    assert snapshot.latest_run.previous_dataset_run_id == first_run
    assert snapshot.latest_capture is not None
    assert snapshot.latest_capture.native_run_id == "copy-new"
    assert snapshot.watermark is not None
    assert snapshot.watermark.version == 4
    assert snapshot.watermark.committed_dataset_run_id == latest_run
    assert snapshot.latest_reconciliation is not None
    assert snapshot.latest_reconciliation.status == "PASS"
    assert snapshot.quarantine_backlog.open_batches == 1
    assert snapshot.quarantine_backlog.open_rows == 3
    assert snapshot.latest_schema_change is not None
    assert snapshot.latest_schema_change.classification == "COMPATIBLE"
    assert [item.reprocess_request_id for item in snapshot.active_reprocess_requests] == [
        reprocess_id
    ]


def test_operator_snapshot_exposes_cdc_progress_and_ignores_terminal_reprocess(tmp_path):
    engine = _engine(tmp_path, _cdc_config())
    pipeline_id = uuid4()
    run_id = uuid4()

    with engine.begin() as connection:
        _insert_pipeline(connection, pipeline_id)
        _insert_dataset_run(
            connection,
            run_id=run_id,
            pipeline_id=pipeline_id,
            dataset_id="erp.order_cdc",
            attempt=1,
            status="SUCCEEDED",
            started_at=BASE,
        )
        connection.execute(
            cdc_checkpoint.insert().values(
                dataset_id="erp.order_cdc",
                positions=[{"partition": "p0", "values": [120, 0]}],
                committed_dataset_run_id=str(run_id),
                version=7,
                created_at=BASE,
                updated_at=None,
            )
        )
        connection.execute(
            reprocess_request.insert().values(
                reprocess_request_id=str(uuid4()),
                dataset_id="erp.order_cdc",
                run_mode="FULL_REBUILD",
                reason="completed rebuild",
                requested_by="operator",
                original_pipeline_run_id=None,
                original_dataset_run_id=None,
                range_json={"authoritative_reset": True},
                status="SUCCEEDED",
                created_at=BASE,
                updated_at=BASE + timedelta(minutes=1),
            )
        )

    snapshot = get_dataset_operational_snapshot(engine, "erp.order_cdc")

    assert snapshot.cdc_checkpoint is not None
    assert snapshot.cdc_checkpoint.version == 7
    assert snapshot.cdc_checkpoint.committed_dataset_run_id == run_id
    assert snapshot.watermark is None
    assert snapshot.active_reprocess_requests == ()


def test_operator_overview_is_dataset_id_ordered(tmp_path):
    engine = _engine(
        tmp_path,
        _watermark_config("erp.z_order"),
        _watermark_config("erp.a_order"),
    )

    snapshots = list_dataset_operational_snapshots(engine)

    assert [item.dataset_id for item in snapshots] == ["erp.a_order", "erp.z_order"]
