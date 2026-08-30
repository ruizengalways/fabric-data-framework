"""Completion gate for SNAPSHOT -> SNAPSHOT_DIFF."""

from __future__ import annotations

from uuid import UUID

from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationMetric,
    ReconciliationResult,
    ReconciliationStatus,
)


def reconcile_snapshot_diff(
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    policy_name: str,
    accounting: RowAccounting,
    candidate_row_count: int,
    target_after_count: int,
    force_fail: bool = False,
) -> ReconciliationResult:
    metrics = (
        ReconciliationMetric(
            name="accepted_candidate_count",
            expected=accounting.rows_accepted,
            actual=candidate_row_count,
            passed=accounting.rows_accepted == candidate_row_count,
        ),
        ReconciliationMetric(
            name="target_after_nonnegative",
            expected=1,
            actual=1 if target_after_count >= 0 else 0,
            passed=target_after_count >= 0,
        ),
    )
    passed = all(metric.passed for metric in metrics) and not force_fail
    return ReconciliationResult(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy_name=policy_name,
        status=ReconciliationStatus.PASS if passed else ReconciliationStatus.FAIL,
        metrics=metrics
        if not force_fail
        else metrics
        + (
            ReconciliationMetric(
                name="forced_failure",
                expected=0,
                actual=1,
                passed=False,
            ),
        ),
        blocks_state_advance=True,
    )
