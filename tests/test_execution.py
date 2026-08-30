from datetime import datetime, timezone

from fabric_data_framework.config import (
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
from fabric_data_framework.execution import execute_watermark_scd2
from fabric_data_framework.quality import RowRule
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.apply.scd2 import InMemorySCD2Target, IS_CURRENT


def dt(hour: int):
    return datetime(2026, 8, 1, hour, tzinfo=timezone.utc)


def config():
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
            tracked_columns=("name", "segment"),
        ),
        orchestration=OrchestrationPolicy(execution_group="crm_daily", criticality=Criticality.HIGH),
        quality=DataQualityPolicy(policy_name="customer", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="count_and_key"),
    )


def test_reference_executor_quarantines_row_and_commits_valid_target_and_watermark():
    cp = InMemoryControlPlane()
    cp.deploy_dataset(config())
    target = InMemorySCD2Target()
    rules = (RowRule("EMAIL_VALID", "email must contain @", lambda row: "@" in str(row.get("email", ""))),)

    result = execute_watermark_scd2(
        repository=cp,
        target=target,
        dataset_id="crm.customer",
        source_rows=[
            {"customer_id": "C001", "name": "Alice", "segment": "A", "email": "alice@example.com", "modified_at": dt(10)},
            {"customer_id": "C002", "name": "Bad", "segment": "A", "email": "invalid", "modified_at": dt(11)},
        ],
        rules=rules,
        mapper=lambda row: dict(row),
    )
    assert result.status.value == "SUCCEEDED"
    assert len(result.bronze) == 2
    assert len(result.quarantined) == 1
    assert len(result.target_rows) == 1
    assert result.target_rows[0][IS_CURRENT] is True
    assert result.watermark_after.value == dt(11)
    assert len(cp.quarantine_batches) == 1


def test_failed_reconciliation_commits_neither_target_nor_watermark():
    cp = InMemoryControlPlane()
    cp.deploy_dataset(config())
    target = InMemorySCD2Target()
    source = [{"customer_id": "C001", "name": "Alice", "segment": "A", "modified_at": dt(10)}]

    first = execute_watermark_scd2(
        repository=cp,
        target=target,
        dataset_id="crm.customer",
        source_rows=source,
        rules=(),
        mapper=lambda row: dict(row),
    )
    before_target = target.read()
    before_watermark = cp.get_watermark("crm.customer")

    failed = execute_watermark_scd2(
        repository=cp,
        target=target,
        dataset_id="crm.customer",
        source_rows=source + [
            {"customer_id": "C002", "name": "Bob", "segment": "B", "modified_at": dt(12)}
        ],
        rules=(),
        mapper=lambda row: dict(row),
        force_reconciliation_failure=True,
    )
    assert failed.status.value == "FAILED"
    assert target.read() == before_target
    assert cp.get_watermark("crm.customer") == before_watermark
    assert first.watermark_after == before_watermark
