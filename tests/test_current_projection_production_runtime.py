from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete

from fabric_data_framework.adapters.fabric.current_projection import (
    FabricSparkDeltaCurrentProjectionRuntime,
)
from fabric_data_framework.contracts.current_projection import (
    CurrentProjectionConfig,
    CurrentProjectionMode,
)
from fabric_data_framework.contracts.dispatch import DatasetDispatchRequest
from fabric_data_framework.contracts.schema import LogicalType, SchemaContract, SchemaField
from fabric_data_framework.control_plane.current_projection_transition import (
    ProjectionTransitionStatus,
    read_projection_transition_events,
)
from fabric_data_framework.control_plane.dataset_lease import (
    acquire_dataset_lease,
    read_dataset_lease,
)
from fabric_data_framework.control_plane.dataset_lease_recovery import (
    DatasetLeaseRecoveryConflict,
    read_dataset_lease_recovery_events,
    recover_abandoned_dataset_lease,
)
from fabric_data_framework.control_plane.io import read_cdc_checkpoint
from fabric_data_framework.control_plane.schema import (
    CONTROL_PLANE_SCHEMA_VERSION,
    apply_baseline_schema,
    current_projection_transition_event,
    current_schema_version,
    dataset_lease_recovery_event,
    schema_migration_history,
    table_names,
)
from fabric_data_framework.execution.backends.fabric_spark import (
    FabricSparkCurrentProjectionExecutor,
)
from fabric_data_framework.execution.plan_compiler import compile_execution_plan
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)
from fabric_data_framework.recovery.current_projection import (
    FabricSparkProjectionTransitionCoordinator,
)


class FakeFrame:
    def __init__(self, rows=(), spark=None):
        self.rows = list(rows)
        self.spark = spark

    def collect(self):
        return list(self.rows)

    def createOrReplaceTempView(self, name: str) -> None:
        if self.spark is not None:
            self.spark.temp_views.append(name)


class FakeReader:
    def __init__(self, spark):
        self.spark = spark
        self.options = {}
        self.format_name = None

    def format(self, value: str):
        self.format_name = value
        return self

    def option(self, key: str, value: object):
        self.options[key] = value
        return self

    def table(self, name: str):
        if self.spark.fail_cdf:
            raise RuntimeError("CDF retention gap")
        self.spark.cdf_reads.append((name, dict(self.options)))
        return FakeFrame((), self.spark)


class FakeCatalog:
    def __init__(self, spark):
        self.spark = spark

    def tableExists(self, name: str) -> bool:
        return self.spark.target_exists


class FakeSpark:
    def __init__(self, *, latest=5, target_exists=True):
        self.latest = latest
        self.target_exists = target_exists
        self.fail_cdf = False
        self.queries = []
        self.temp_views = []
        self.cdf_reads = []
        self._reader = FakeReader(self)
        self._catalog = FakeCatalog(self)

    @property
    def read(self):
        self._reader = FakeReader(self)
        return self._reader

    @property
    def catalog(self):
        return self._catalog

    def sql(self, query: str):
        self.queries.append(query)
        if "DESCRIBE HISTORY" in query:
            return FakeFrame(((self.latest,),), self)
        if "fdf:affected_count" in query:
            return FakeFrame(((1,),), self)
        if "fdf:insert_count" in query:
            return FakeFrame(((1,),), self)
        if "fdf:delete_count" in query:
            return FakeFrame(((0,),), self)
        if "fdf:update_count" in query:
            return FakeFrame(((0,),), self)
        if "fdf:rebuild_count" in query:
            return FakeFrame(((2,),), self)
        if any(
            marker in query
            for marker in (
                "fdf:history_duplicate_current",
                "fdf:target_duplicate_key",
                "fdf:verify",
                "fdf:rebuild_duplicate_current",
            )
        ):
            return FakeFrame((), self)
        if "IS NULL" in query and "LIMIT 1" in query:
            return FakeFrame((), self)
        return FakeFrame((), self)


class FakeRepository:
    def __init__(self):
        self.dataset_runs = []

    def record_dataset_run(self, audit):
        self.dataset_runs.append(audit)


def _schema():
    return SchemaContract(
        fields=(
            SchemaField(name="customer_id", logical_type=LogicalType.STRING, nullable=False),
            SchemaField(name="email", logical_type=LogicalType.STRING),
        )
    )


def _config(mode: CurrentProjectionMode) -> DatasetConfig:
    return DatasetConfig(
        dataset_id="crm.customer.current",
        source=SourceConfig(system="framework_dataset", object="silver.customer_history"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.PROJECTION,
            apply_strategy=ApplyStrategy.CURRENT_PROJECTION,
            business_key=("customer_id",),
            merge_key=("customer_id",),
            delete_policy="DERIVE_FROM_HISTORY",
        ),
        current_projection=CurrentProjectionConfig(
            authoritative_history_dataset_id="crm.customer_history",
            mode=mode,
        ),
        orchestration=OrchestrationPolicy(
            execution_group="crm",
            criticality=Criticality.HIGH,
            dependencies=("crm.customer_history",),
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="default"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
        schema_contract=_schema(),
    )


def test_control_plane_v8_is_explicit_and_repairs_v7_only_through_migration(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'v8.db'}")
    assert apply_baseline_schema(engine) == 8
    assert CONTROL_PLANE_SCHEMA_VERSION == 8
    assert "dataset_lease_recovery_event" in table_names()
    assert "current_projection_transition_event" in table_names()

    dataset_lease_recovery_event.drop(engine)
    current_projection_transition_event.drop(engine)
    with engine.begin() as connection:
        connection.execute(
            delete(schema_migration_history).where(schema_migration_history.c.version == 8)
        )
    assert current_schema_version(engine) == 7
    assert apply_baseline_schema(engine) == 8
    assert current_schema_version(engine) == 8


def test_latest_schema_claim_with_missing_table_fails_closed(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'drift.db'}")
    apply_baseline_schema(engine)
    dataset_lease_recovery_event.drop(engine)
    with pytest.raises(RuntimeError, match="claims latest"):
        apply_baseline_schema(engine)


def test_abandoned_lease_recovery_requires_deadline_and_exact_proof(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'lease.db'}")
    apply_baseline_schema(engine)
    run_id = uuid4()
    lease = acquire_dataset_lease(
        engine,
        dataset_id="projection.customer",
        lease_owner="worker-1",
        dataset_run_id=run_id,
        review_deadline=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    with pytest.raises(DatasetLeaseRecoveryConflict, match="deadline"):
        recover_abandoned_dataset_lease(
            engine,
            dataset_id=lease.dataset_id,
            expected_lease_owner=lease.lease_owner,
            expected_dataset_run_id=lease.dataset_run_id,
            expected_lease_version=lease.lease_version,
            recovered_by="operator@example.com",
            reason="worker host lost",
            proof_reference="INC-123",
        )

    recovered = recover_abandoned_dataset_lease(
        engine,
        dataset_id=lease.dataset_id,
        expected_lease_owner=lease.lease_owner,
        expected_dataset_run_id=lease.dataset_run_id,
        expected_lease_version=lease.lease_version,
        recovered_by="operator@example.com",
        reason="worker host lost and executor terminated",
        proof_reference="INC-123:host-terminated",
        recovered_at=lease.expires_at + timedelta(seconds=1),
    )
    assert recovered.dataset_run_id == run_id
    assert read_dataset_lease(engine, lease.dataset_id) is None
    assert read_dataset_lease_recovery_events(engine, dataset_id=lease.dataset_id) == (
        recovered,
    )


def test_spark_delta_projection_rebuild_then_incremental_uses_exact_version_and_cdf(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'spark.db'}")
    spark = FakeSpark(latest=5)
    runtime = FabricSparkDeltaCurrentProjectionRuntime(spark)
    first = runtime.rebuild(
        control_plane_engine=engine,
        dataset_id="crm.customer.current",
        dataset_run_id=uuid4(),
        history_table="silver.customer_history",
        target_table="silver.customer",
        business_key=("customer_id",),
        projected_columns=("customer_id", "email"),
        reconcile=lambda evidence: True,
    )
    assert first.upper_processed_version == 5
    assert first.checkpoint_version == 1

    spark.latest = 6
    second = runtime.execute_incremental(
        control_plane_engine=engine,
        dataset_id="crm.customer.current",
        dataset_run_id=uuid4(),
        history_table="silver.customer_history",
        target_table="silver.customer",
        business_key=("customer_id",),
        projected_columns=("customer_id", "email"),
        reconcile=lambda evidence: True,
    )
    assert second.upper_processed_version == 6
    assert second.affected_keys == 1
    assert second.mutations.inserted == 1
    assert second.checkpoint_version == 2
    assert spark.cdf_reads[-1][1]["startingVersion"] == 6
    assert spark.cdf_reads[-1][1]["endingVersion"] == 6
    assert any("VERSION AS OF 6" in query for query in spark.queries)
    assert any("MERGE INTO `silver`.`customer`" in query for query in spark.queries)


def test_spark_delta_projection_cdf_gap_fails_without_checkpoint_advance(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cdf-gap.db'}")
    spark = FakeSpark(latest=5)
    runtime = FabricSparkDeltaCurrentProjectionRuntime(spark)
    runtime.rebuild(
        control_plane_engine=engine,
        dataset_id="crm.customer.current",
        dataset_run_id=uuid4(),
        history_table="silver.customer_history",
        target_table="silver.customer",
        business_key=("customer_id",),
        projected_columns=("customer_id", "email"),
        reconcile=lambda evidence: True,
    )
    before = read_cdc_checkpoint(engine, "crm.customer.current")
    spark.latest = 6
    spark.fail_cdf = True
    with pytest.raises(Exception, match="explicit rebuild"):
        runtime.execute_incremental(
            control_plane_engine=engine,
            dataset_id="crm.customer.current",
            dataset_run_id=uuid4(),
            history_table="silver.customer_history",
            target_table="silver.customer",
            business_key=("customer_id",),
            projected_columns=("customer_id", "email"),
            reconcile=lambda evidence: True,
        )
    after = read_cdc_checkpoint(engine, "crm.customer.current")
    assert before is not None and after is not None
    assert after.version == before.version
    assert after.checkpoint == before.checkpoint


def test_fabric_spark_backend_dispatches_view_projection_and_records_terminal_audit(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'backend.db'}")
    spark = FakeSpark()
    repository = FakeRepository()
    config = _config(CurrentProjectionMode.VIEW)
    effective = resolve_effective_config(config)
    request = DatasetDispatchRequest(
        pipeline_run_id=uuid4(),
        dataset_run_id=uuid4(),
        dataset_id=config.dataset_id,
        run_mode=RunMode.NORMAL,
        effective_config=effective,
        execution_plan=compile_execution_plan(effective, run_mode=RunMode.NORMAL),
    )
    outcome = FabricSparkCurrentProjectionExecutor(
        spark=spark,
        control_plane_engine=engine,
        repository=repository,
    )(request)
    assert outcome.status is DatasetStatus.SUCCEEDED
    assert repository.dataset_runs[-1].status is DatasetStatus.SUCCEEDED
    assert any("CREATE OR REPLACE VIEW" in query for query in spark.queries)


def test_governed_delta_to_view_transition_resets_exact_checkpoint_and_audits(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'transition.db'}")
    spark = FakeSpark(latest=5)
    delta = _config(CurrentProjectionMode.DELTA_PROJECTION)
    view = _config(CurrentProjectionMode.VIEW)
    runtime = FabricSparkDeltaCurrentProjectionRuntime(spark)
    runtime.rebuild(
        control_plane_engine=engine,
        dataset_id=delta.dataset_id,
        dataset_run_id=uuid4(),
        history_table=delta.source.object,
        target_table="silver.customer",
        business_key=delta.load.business_key,
        projected_columns=("customer_id", "email"),
        reconcile=lambda evidence: True,
    )
    assert read_cdc_checkpoint(engine, delta.dataset_id) is not None

    coordinator = FabricSparkProjectionTransitionCoordinator(
        spark=spark,
        control_plane_engine=engine,
    )
    result = coordinator.transition(
        previous=delta,
        desired=view,
        dataset_run_id=uuid4(),
        actor="release-bot",
        reason="switch to non-drifting view",
        ticket_reference="CHG-42",
    )
    assert result.checkpoint_reset is True
    assert read_cdc_checkpoint(engine, delta.dataset_id) is None
    events = read_projection_transition_events(engine, transition_id=result.transition_id)
    assert [event.status for event in events] == [
        ProjectionTransitionStatus.STARTED,
        ProjectionTransitionStatus.COMPLETED,
    ]
    assert any("DROP TABLE IF EXISTS" in query for query in spark.queries)
    assert any("CREATE OR REPLACE VIEW" in query for query in spark.queries)
