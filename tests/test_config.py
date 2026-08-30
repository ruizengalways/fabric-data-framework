from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    OverrideConflictError,
    OverrideField,
    ReconciliationPolicy,
    RuntimeOverride,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
    resolve_effective_config,
)


def customer_config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="crm.customer",
        source=SourceConfig(system="crm", object="dbo.Customer", connection_ref="crm_ro"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.SCD2,
            business_key=("customer_id",),
            merge_key=("customer_id",),
            watermark=WatermarkConfig(column="modified_at", tie_breaker=("customer_id",)),
            event_time_column="modified_at",
            tracked_columns=("name", "address", "segment"),
        ),
        orchestration=OrchestrationPolicy(
            execution_group="crm_daily",
            criticality=Criticality.HIGH,
        ),
        quality=DataQualityPolicy(
            policy_name="customer_standard",
            quarantine_policy="reject_bad_rows",
        ),
        reconciliation=ReconciliationPolicy(policy_name="standard_count_and_key"),
    )


def test_valid_watermark_scd2_config_is_immutable_and_hashed():
    config = customer_config()
    assert len(config.config_hash) == 64
    with pytest.raises(ValidationError):
        config.enabled = False


def test_watermark_requires_tie_breaker_or_overlap_window():
    with pytest.raises(ValidationError, match="tie_breaker or a positive overlap"):
        LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.REPLACE,
            watermark=WatermarkConfig(column="modified_at"),
        )


def test_stateful_apply_requires_merge_key():
    with pytest.raises(ValidationError, match="requires merge_key"):
        LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.UPSERT,
        )


def test_non_watermark_capture_rejects_watermark_config():
    with pytest.raises(ValidationError, match="only valid for WATERMARK"):
        LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
            watermark=WatermarkConfig(column="modified_at", overlap_window_seconds=60),
        )


def test_semantic_field_cannot_be_used_as_runtime_override():
    with pytest.raises(ValidationError):
        RuntimeOverride(
            dataset_id="crm.customer",
            field="load.merge_key",
            value=1,
            reason="not allowed",
            requested_by="operator",
        )


def test_effective_config_applies_operational_override_and_changes_hash():
    config = customer_config()
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    override = RuntimeOverride(
        dataset_id=config.dataset_id,
        field=OverrideField.MAX_CONCURRENCY,
        value=2,
        reason="protect source during incident",
        requested_by="oncall",
        valid_from=now - timedelta(minutes=5),
        valid_to=now + timedelta(hours=1),
    )
    effective = resolve_effective_config(config, (override,), as_of=now)
    assert effective.config.orchestration.max_concurrency == 2
    assert effective.base_config_hash == config.config_hash
    assert effective.effective_config_hash != effective.base_config_hash
    assert effective.applied_override_ids == (override.override_id,)


def test_expired_override_is_ignored():
    config = customer_config()
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    override = RuntimeOverride(
        dataset_id=config.dataset_id,
        field=OverrideField.ENABLED,
        value=False,
        reason="past maintenance",
        requested_by="oncall",
        valid_from=now - timedelta(hours=2),
        valid_to=now - timedelta(hours=1),
    )
    effective = resolve_effective_config(config, (override,), as_of=now)
    assert effective.config.enabled is True
    assert effective.effective_config_hash == effective.base_config_hash
    assert not effective.applied_override_ids


def test_conflicting_same_precedence_overrides_fail_resolution():
    config = customer_config()
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    common = dict(
        dataset_id=config.dataset_id,
        field=OverrideField.RETRY_COUNT,
        reason="incident",
        requested_by="oncall",
        valid_from=now - timedelta(minutes=1),
        valid_to=now + timedelta(hours=1),
        precedence=10,
    )
    one = RuntimeOverride(value=1, **common)
    two = RuntimeOverride(value=3, **common)
    with pytest.raises(OverrideConflictError):
        resolve_effective_config(config, (one, two), as_of=now)


def test_higher_precedence_override_wins():
    config = customer_config()
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    low = RuntimeOverride(
        dataset_id=config.dataset_id,
        field=OverrideField.RETRY_COUNT,
        value=1,
        reason="general limit",
        requested_by="ops",
        valid_from=now - timedelta(hours=1),
        precedence=1,
    )
    high = RuntimeOverride(
        dataset_id=config.dataset_id,
        field=OverrideField.RETRY_COUNT,
        value=5,
        reason="approved incident exception",
        requested_by="incident_manager",
        valid_from=now - timedelta(minutes=5),
        precedence=50,
    )
    effective = resolve_effective_config(config, (low, high), as_of=now)
    assert effective.config.orchestration.retry_count == 5
    assert effective.applied_override_ids == (high.override_id,)
