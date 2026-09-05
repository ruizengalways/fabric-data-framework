from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    QuarantineDetailMode,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
)
from fabric_data_framework.execution import execute_watermark_scd2
from fabric_data_framework.quality.rules import RowRule
from fabric_data_framework.quality.quarantine_store import JsonFileQuarantineStore
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.apply.scd2 import InMemorySCD2Target, IS_CURRENT


def dt(hour: int):
    return datetime(2026, 8, 1, hour, tzinfo=timezone.utc)


def config(*, dq_enabled=True, quarantine_enabled=True):
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
        quality=DataQualityPolicy(
            policy_name="customer",
            quarantine_policy="row",
            enabled=dq_enabled,
            quarantine_enabled=quarantine_enabled,
            quarantine_detail_mode=QuarantineDetailMode.FULL,
        ),
        reconciliation=ReconciliationPolicy(policy_name="count_and_key"),
    )


def _email_rule():
    return (
        RowRule(
            "EMAIL_VALID",
            "email must contain @",
            lambda row: "@" in str(row.get("email", "")),
        ),
    )


def test_reference_executor_quarantines_row_with_durable_detail_and_commits_valid_rows(tmp_path):
    cp = InMemoryControlPlane()
    cp.deploy_dataset(config())
    target = InMemorySCD2Target()
    store = JsonFileQuarantineStore(tmp_path / "quarantine")

    result = execute_watermark_scd2(
        repository=cp,
        target=target,
        dataset_id="crm.customer",
        source_rows=[
            {"customer_id": "C001", "name": "Alice", "segment": "A", "email": "alice@example.com", "modified_at": dt(10)},
            {"customer_id": "C002", "name": "Bad", "segment": "A", "email": "invalid", "modified_at": dt(11)},
        ],
        rules=_email_rule(),
        mapper=lambda row: dict(row),
        quarantine_store=store,
    )
    assert result.status.value == "SUCCEEDED"
    assert len(result.bronze) == 2
    assert len(result.quarantined) == 1
    assert len(result.target_rows) == 1
    assert result.target_rows[0][IS_CURRENT] is True
    assert result.watermark_after.value == dt(11)
    assert len(cp.quarantine_batches) == 1

    batch = cp.quarantine_batches[0]
    assert batch.row_count == 1
    assert batch.reason_code == "EMAIL_VALID"
    assert batch.source_reference is not None
    parsed = urlparse(batch.source_reference)
    payload = json.loads(Path(unquote(parsed.path)).read_text(encoding="utf-8"))
    assert payload["dataset_id"] == "crm.customer"
    assert payload["row_count"] == 1
    assert payload["rows"][0]["data"]["customer_id"] == "C002"
    assert payload["rows"][0]["data"]["email"] == "invalid"
    assert payload["rows"][0]["data_quality_failures"] == [
        {"rule_code": "EMAIL_VALID", "rule_message": "email must contain @"}
    ]


def test_quarantine_disabled_makes_bad_row_fail_dataset_without_target_or_state_commit():
    cp = InMemoryControlPlane()
    cp.deploy_dataset(config(quarantine_enabled=False))
    target = InMemorySCD2Target()

    result = execute_watermark_scd2(
        repository=cp,
        target=target,
        dataset_id="crm.customer",
        source_rows=[
            {"customer_id": "C001", "name": "Alice", "segment": "A", "email": "alice@example.com", "modified_at": dt(10)},
            {"customer_id": "C002", "name": "Bad", "segment": "A", "email": "invalid", "modified_at": dt(11)},
        ],
        rules=_email_rule(),
        mapper=lambda row: dict(row),
    )

    assert result.status.value == "FAILED"
    assert target.read() == ()
    assert cp.get_watermark("crm.customer") is None
    assert cp.quarantine_batches == []
    audit = cp.dataset_runs[-1]
    assert audit.error_code == "DATA_QUALITY_FAILED_QUARANTINE_DISABLED"
    assert "EMAIL_VALID" in audit.error_message
    assert audit.row_accounting.rows_quarantined == 1


def test_data_quality_disabled_skips_rules_and_does_not_quarantine():
    cp = InMemoryControlPlane()
    cp.deploy_dataset(config(dq_enabled=False))
    target = InMemorySCD2Target()

    result = execute_watermark_scd2(
        repository=cp,
        target=target,
        dataset_id="crm.customer",
        source_rows=[
            {"customer_id": "C002", "name": "Bad", "segment": "A", "email": "invalid", "modified_at": dt(11)},
        ],
        rules=_email_rule(),
        mapper=lambda row: dict(row),
    )

    assert result.status.value == "SUCCEEDED"
    assert len(result.target_rows) == 1
    assert result.quarantined == ()
    assert cp.quarantine_batches == []
    validate_step = next(item for item in cp.step_runs if item.step_name == "VALIDATE")
    assert validate_step.status.value == "SKIPPED"
    assert validate_step.details == {"reason": "data_quality_disabled"}


def test_failed_reconciliation_commits_neither_target_nor_watermark():
    cp = InMemoryControlPlane()
    cfg = config()
    cp.deploy_dataset(cfg)
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
