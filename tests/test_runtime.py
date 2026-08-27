from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from fabric_data_framework.config import Criticality, DatasetStatus, PipelineStatus, RunMode
from fabric_data_framework.infrastructure import EnvironmentName
from fabric_data_framework.runtime import (
    DatasetOutcome,
    RuntimeContext,
    StateCommitGate,
    WatermarkPosition,
    WatermarkTransition,
    aggregate_pipeline_status,
)


def test_noncritical_failure_produces_partial_success():
    status = aggregate_pipeline_status(
        [
            DatasetOutcome(
                dataset_id="crm.customer", status=DatasetStatus.SUCCEEDED, criticality=Criticality.CRITICAL
            ),
            DatasetOutcome(
                dataset_id="crm.preference", status=DatasetStatus.FAILED, criticality=Criticality.LOW
            ),
        ]
    )
    assert status is PipelineStatus.PARTIAL_SUCCESS


def test_critical_failure_produces_failed_after_aggregation():
    status = aggregate_pipeline_status(
        [
            DatasetOutcome(
                dataset_id="crm.customer", status=DatasetStatus.FAILED, criticality=Criticality.CRITICAL
            ),
            DatasetOutcome(
                dataset_id="crm.address", status=DatasetStatus.SUCCEEDED, criticality=Criticality.MEDIUM
            ),
        ]
    )
    assert status is PipelineStatus.FAILED


def test_aggregation_rejects_non_final_dataset():
    with pytest.raises(ValueError, match="non-final"):
        aggregate_pipeline_status(
            [DatasetOutcome(dataset_id="x", status=DatasetStatus.RUNNING, criticality=Criticality.LOW)]
        )


def test_watermark_cannot_advance_before_reconciliation_gate():
    with pytest.raises(ValidationError, match="cannot advance"):
        WatermarkTransition(
            before=WatermarkPosition(value="2026-08-27T00:00:00Z", tie_breaker=(10,)),
            after=WatermarkPosition(value="2026-08-28T00:00:00Z", tie_breaker=(20,)),
            gate=StateCommitGate(
                target_committed=True,
                reconciliation_required=True,
                reconciliation_passed=False,
            ),
        )


def test_watermark_can_advance_after_target_and_reconciliation():
    transition = WatermarkTransition(
        before=WatermarkPosition(value="2026-08-27T00:00:00Z", tie_breaker=(10,)),
        after=WatermarkPosition(value="2026-08-28T00:00:00Z", tie_breaker=(20,)),
        gate=StateCommitGate(
            target_committed=True,
            reconciliation_required=True,
            reconciliation_passed=True,
        ),
    )
    assert transition.gate.can_advance_state


def test_runtime_context_is_immutable_and_correlated():
    context = RuntimeContext(
        environment=EnvironmentName.DEV,
        domain="customer",
        dataset_id="crm.customer",
        run_mode=RunMode.NORMAL,
        domain_git_sha="a" * 40,
        framework_version="0.1.0",
        effective_config_hash="b" * 64,
        started_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    assert context.pipeline_run_id != context.dataset_run_id
    with pytest.raises(ValidationError):
        context.attempt = 2
