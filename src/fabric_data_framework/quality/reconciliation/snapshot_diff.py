"""Completion gate for SNAPSHOT -> SNAPSHOT_DIFF."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationMetric,
    ReconciliationObservation,
    ReconciliationResult,
)
from fabric_data_framework.metadata.config import ReconciliationPolicy
from fabric_data_framework.quality.reconciliation.engine import evaluate_reconciliation_policy


def reconcile_snapshot_diff(
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    policy: ReconciliationPolicy,
    accounting: RowAccounting,
    candidate_row_count: int,
    target_after_count: int,
    observations: Sequence[ReconciliationObservation] = (),
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
    if force_fail:
        metrics = metrics + (
            ReconciliationMetric(
                name="forced_failure",
                expected=0,
                actual=1,
                passed=False,
            ),
        )

    return evaluate_reconciliation_policy(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy=policy,
        accounting=accounting,
        observations=observations,
        base_metrics=metrics,
    )


__all__ = ["reconcile_snapshot_diff"]
