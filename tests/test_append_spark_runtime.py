from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.adapters.fabric.append import (
    FabricSparkDeltaAppendRuntime,
    SparkAppendError,
    SparkDeltaAppendRequest,
)
from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.contracts.dispatch import DatasetDispatchRequest
from fabric_data_framework.contracts.schema import LogicalType, SchemaContract, SchemaField
from fabric_data_framework.control_plane.schema import apply_baseline_schema
from fabric_data_framework.execution.backends.fabric_spark_append import (
    FabricSparkAppendExecutor,
    SparkAppendBatch,
)
from fabric_data_framework.execution.backends.fabric_spark_dataset import (
    build_fabric_spark_executor_resolver,
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


class FakeFrame:
    def __init__(self, rows=(), *, query: str = ""):
        self.rows = list(rows)
        self.query = query

    def collect(self):
        if self.query and "COUNT(*)" not in self.query and "LIMIT 1" not in self.query:
            raise AssertionError(f"unbounded collect attempted: {self.query}")
        return list(self.rows)

    def createOrReplaceTempView(self, name: str) -> None:
        raise AssertionError("APPEND runtime must stage through Spark SQL, not Python frames")


class FakeReader:
    def format(self, value: str):
        return self

    def option(self, key: str, value: object):
        return self

    def table(self, name: str):
        raise AssertionError("APPEND runtime must not read target rows into Python")


class FakeCatalog:
    def __init__(self, spark):
        self.spark = spark

    def tableExists(self, name: str) -> bool:
        return self.spark.target_exists


class FakeSpark:
    def __init__(self):
        self.target_exists = True
        self.incoming_rows = 3
        self.stage_rows = 2
        self.replayed = 1
        self.incoming_conflict = False
        self.target_conflict = False
        self.target_duplicate = False
        self.verify_missing = False
        self.queries: list[str] = []
        self._catalog = FakeCatalog(self)
        self._reader = FakeReader()

    @property
    def catalog(self):
        return self._catalog

    @property
    def read(self):
        return self._reader

    def sql(self, query: str):
        self.queries.append(query)
        if "fdf:append_incoming_count" in query:
            return FakeFrame(((self.incoming_rows,),), query=query)
        if "fdf:append_stage_count" in query:
            return FakeFrame(((self.stage_rows,),), query=query)
        if "fdf:append_replay_count" in query:
            return FakeFrame(((self.replayed,),), query=query)
        if "fdf:append_incoming_conflict" in query:
            return FakeFrame(((1,),) if self.incoming_conflict else (), query=query)
        if "fdf:append_target_conflict" in query:
            return FakeFrame(((1,),) if self.target_conflict else (), query=query)
        if "fdf:append_target_duplicate" in query:
            return FakeFrame(((1,),) if self.target_duplicate else (), query=query)
        if "fdf:append_verify_missing" in query:
            return FakeFrame(((1,),) if self.verify_missing else (), query=query)
        return FakeFrame((), query="")


class FakeRepository:
    def __init__(self):
        self.dataset_runs = []
        self.reconciliations = []

    def record_dataset_run(self, audit):
        self.dataset_runs.append(audit)

    def record_reconciliation(self, result):
        self.reconciliations.append(result)


def _request() -> SparkDeltaAppendRequest:
    return SparkDeltaAppendRequest(
        dataset_id="orders.events",
        dataset_run_id=uuid4(),
        incoming_relation="staging.orders_events",
        target_table="silver.orders_events",
        append_identity=("event_id",),
        business_columns=("event_id", "value"),
        expected_incoming_rows=3,
    )


def _config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="orders.events",
        source=SourceConfig(system="orders", object="staging.orders_events"),
        target=TargetConfig(layer="silver", object="orders_events"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.APPEND,
            append_identity=("event_id",),
        ),
        orchestration=OrchestrationPolicy(
            execution_group="orders",
            criticality=Criticality.HIGH,
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="default"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
        schema_contract=SchemaContract(
            fields=(
                SchemaField(name="event_id", logical_type=LogicalType.STRING, nullable=False),
                SchemaField(name="value", logical_type=LogicalType.INT64),
            )
        ),
    )


def test_distributed_append_uses_scalar_guards_and_delta_merge_without_target_collect(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'append.db'}")
    apply_baseline_schema(engine)
    spark = FakeSpark()
    evidence = FabricSparkDeltaAppendRuntime(spark).execute(
        control_plane_engine=engine,
        request=_request(),
    )

    assert evidence.incoming_rows == 3
    assert evidence.unique_incoming == 2
    assert evidence.duplicate_incoming == 1
    assert evidence.replayed == 1
    assert evidence.inserted == 1
    assert evidence.mutations.inserted == 1
    assert any("MERGE INTO `silver`.`orders_events`" in query for query in spark.queries)
    assert any("LEFT ANTI JOIN" in query for query in spark.queries)
    assert not any("toPandas" in query for query in spark.queries)


def test_distributed_append_conflict_fails_before_target_mutation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'conflict.db'}")
    apply_baseline_schema(engine)
    spark = FakeSpark()
    spark.incoming_conflict = True

    with pytest.raises(SparkAppendError, match="incoming batch reuses"):
        FabricSparkDeltaAppendRuntime(spark).execute(
            control_plane_engine=engine,
            request=_request(),
        )

    assert not any("fdf:append_merge" in query for query in spark.queries)


def test_distributed_append_target_conflict_fails_before_merge(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'target-conflict.db'}")
    apply_baseline_schema(engine)
    spark = FakeSpark()
    spark.target_conflict = True

    with pytest.raises(SparkAppendError, match="different business payload"):
        FabricSparkDeltaAppendRuntime(spark).execute(
            control_plane_engine=engine,
            request=_request(),
        )

    assert not any("fdf:append_merge" in query for query in spark.queries)


def test_distributed_append_executor_reconciles_and_records_actual_mutation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'executor.db'}")
    apply_baseline_schema(engine)
    spark = FakeSpark()
    repository = FakeRepository()
    config = _config()
    effective = resolve_effective_config(config)
    request = DatasetDispatchRequest(
        pipeline_run_id=uuid4(),
        dataset_run_id=uuid4(),
        dataset_id=config.dataset_id,
        run_mode=RunMode.NORMAL,
        effective_config=effective,
        execution_plan=compile_execution_plan(effective, run_mode=RunMode.NORMAL),
    )
    batch = SparkAppendBatch(
        incoming_relation="staging.orders_events",
        accounting=RowAccounting(rows_read=3, rows_accepted=3),
    )
    outcome = FabricSparkAppendExecutor(
        spark=spark,
        control_plane_engine=engine,
        repository=repository,
        batch_resolver=lambda _: batch,
    )(request)

    assert outcome.status is DatasetStatus.SUCCEEDED
    assert repository.dataset_runs[-1].mutations.inserted == 1
    assert repository.reconciliations[-1].status.value == "PASS"


def test_fabric_spark_resolver_routes_append_without_in_memory_target_read(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'resolver.db'}")
    apply_baseline_schema(engine)
    spark = FakeSpark()
    repository = FakeRepository()
    config = _config()
    effective = resolve_effective_config(config)
    resolver = build_fabric_spark_executor_resolver(
        spark=spark,
        control_plane_engine=engine,
        repository=repository,
        append_batch_resolver=lambda _: SparkAppendBatch(
            incoming_relation="staging.orders_events",
            accounting=RowAccounting(rows_read=3, rows_accepted=3),
        ),
    )
    request = DatasetDispatchRequest(
        pipeline_run_id=uuid4(),
        dataset_run_id=uuid4(),
        dataset_id=config.dataset_id,
        run_mode=RunMode.NORMAL,
        effective_config=effective,
        execution_plan=compile_execution_plan(effective, run_mode=RunMode.NORMAL),
    )

    outcome = resolver(effective)(request)
    assert outcome.status is DatasetStatus.SUCCEEDED
    assert any("fdf:append_merge" in query for query in spark.queries)
