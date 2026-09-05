from datetime import datetime, timezone

from fabric_data_framework.apply.scd2 import InMemorySCD2Target
from fabric_data_framework.contracts.replay import QuarantineBatchEvidence
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.execution import execute_watermark_scd2
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
)
from fabric_data_framework.quality.quarantine_store import JsonFileQuarantineStore
from fabric_data_framework.quality.rules import RowRule


def _dt(hour: int):
    return datetime(2026, 9, 5, hour, tzinfo=timezone.utc)


def _config(*, max_rows=None, max_fraction=None):
    return DatasetConfig(
        dataset_id="crm.customer",
        source=SourceConfig(system="crm", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.SCD2,
            business_key=("customer_id",),
            merge_key=("customer_id",),
            watermark=WatermarkConfig(column="modified_at", tie_breaker=("customer_id",)),
            event_time_column="modified_at",
            tracked_columns=("name",),
        ),
        orchestration=OrchestrationPolicy(
            execution_group="crm_scd2",
            criticality=Criticality.HIGH,
        ),
        quality=DataQualityPolicy(
            policy_name="customer",
            quarantine_policy="row",
            max_quarantine_rows=max_rows,
            max_quarantine_fraction=max_fraction,
        ),
        reconciliation=ReconciliationPolicy(policy_name="count_and_key"),
    )


def _rule():
    return RowRule(
        "EMAIL_VALID",
        "email must contain @",
        lambda row: "@" in str(row.get("email", "")),
    )


def _evidence(batch):
    return QuarantineBatchEvidence(
        quarantine_id=batch.quarantine_id,
        dataset_run_id=batch.dataset_run_id,
        dataset_id=batch.dataset_id,
        scope=batch.scope.value,
        row_count=batch.row_count,
        reason_code=batch.reason_code,
        reason_detail=batch.reason_detail,
        source_reference=batch.source_reference,
        replayed_by_dataset_run_id=batch.replayed_by_dataset_run_id,
        created_at=batch.created_at,
    )


def test_quarantine_threshold_failure_retains_detail_and_blocks_target_and_watermark(tmp_path):
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config(max_rows=0))
    target = InMemorySCD2Target()
    store = JsonFileQuarantineStore(tmp_path / "quarantine")

    result = execute_watermark_scd2(
        repository=repository,
        target=target,
        dataset_id="crm.customer",
        source_rows=[
            {
                "customer_id": "C001",
                "name": "Alice",
                "email": "alice@example.com",
                "modified_at": _dt(10),
            },
            {
                "customer_id": "C002",
                "name": "Bad",
                "email": "invalid",
                "modified_at": _dt(11),
            },
        ],
        rules=(_rule(),),
        mapper=dict,
        quarantine_store=store,
    )

    assert result.status.value == "FAILED"
    assert target.read() == ()
    assert repository.get_watermark("crm.customer") is None
    audit = repository.dataset_runs[-1]
    assert audit.error_code == "DATA_QUALITY_QUARANTINE_THRESHOLD_EXCEEDED"
    assert audit.row_accounting.rows_quarantined == 1
    assert audit.mutations.inserted == 0
    assert len(repository.quarantine_batches) == 1
    batch = repository.quarantine_batches[0]
    assert batch.row_count == 1
    assert batch.source_reference is not None
    payload = store.load_payload(_evidence(batch))
    assert payload.rows[0]["customer_id"] == "C002"


def test_small_quarantine_within_fraction_budget_commits_valid_rows_and_state(tmp_path):
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config(max_rows=2, max_fraction=0.5))
    target = InMemorySCD2Target()
    store = JsonFileQuarantineStore(tmp_path / "quarantine")

    result = execute_watermark_scd2(
        repository=repository,
        target=target,
        dataset_id="crm.customer",
        source_rows=[
            {
                "customer_id": "C001",
                "name": "Alice",
                "email": "alice@example.com",
                "modified_at": _dt(10),
            },
            {
                "customer_id": "C002",
                "name": "Bad",
                "email": "invalid",
                "modified_at": _dt(11),
            },
            {
                "customer_id": "C003",
                "name": "Carol",
                "email": "carol@example.com",
                "modified_at": _dt(12),
            },
        ],
        rules=(_rule(),),
        mapper=dict,
        quarantine_store=store,
    )

    assert result.status.value == "SUCCEEDED"
    assert len(target.read()) == 2
    assert repository.get_watermark("crm.customer").value == _dt(12)
    assert repository.dataset_runs[-1].row_accounting.rows_quarantined == 1
    quarantine_step = next(
        item for item in repository.step_runs if item.step_name == "QUARANTINE"
    )
    assert quarantine_step.details["threshold_breached"] is False
