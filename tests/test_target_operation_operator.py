from uuid import uuid4

from sqlalchemy import create_engine

from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.contracts.target_operation import (
    TargetOperationSpec,
    TargetOperationStatus,
)
from fabric_data_framework.delivery import materialize_semantic_metadata
from fabric_data_framework.operator import get_dataset_operational_snapshot
from fabric_data_framework.target_operation_io import RelationalTargetOperationJournal


def test_operator_snapshot_exposes_latest_target_operation(tmp_path):
    config = DatasetConfig(
        dataset_id="erp.customer",
        source=SourceConfig(system="erp", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.SCD1,
            merge_key=("customer_id",),
        ),
        orchestration=OrchestrationPolicy(execution_group="erp"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    materialize_semantic_metadata(
        engine,
        configs=(config,),
        domain="erp",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )
    spec = TargetOperationSpec(
        dataset_id=config.dataset_id,
        run_mode=RunMode.NORMAL,
        apply_strategy=ApplyStrategy.SCD1,
        target_reference="silver.customer",
        effective_config_hash=config.config_hash,
        mutation_scope_hash="b" * 64,
    )
    run_id = uuid4()
    journal = RelationalTargetOperationJournal(engine)
    prepared = journal.reserve(spec, dataset_run_id=run_id)
    started = journal.transition(
        operation_key=spec.operation_key,
        expected_version=prepared.version,
        status=TargetOperationStatus.IN_PROGRESS,
        dataset_run_id=run_id,
    )
    journal.transition(
        operation_key=spec.operation_key,
        expected_version=started.version,
        status=TargetOperationStatus.COMMIT_UNKNOWN,
        dataset_run_id=run_id,
        outcome_reference="warehouse-query:pending",
        error_code="DRIVER_TIMEOUT",
    )

    snapshot = get_dataset_operational_snapshot(engine, config.dataset_id)

    assert snapshot.latest_target_operation is not None
    assert snapshot.latest_target_operation.operation_key == spec.operation_key
    assert snapshot.latest_target_operation.status is TargetOperationStatus.COMMIT_UNKNOWN
    assert snapshot.latest_target_operation.apply_strategy is ApplyStrategy.SCD1
    assert snapshot.latest_target_operation.last_dataset_run_id == run_id
    assert snapshot.latest_target_operation.attempts_started == 1
    assert snapshot.latest_target_operation.outcome_reference == "warehouse-query:pending"
    assert snapshot.latest_target_operation.last_error_code == "DRIVER_TIMEOUT"
    assert snapshot.latest_target_operation.version == 3
