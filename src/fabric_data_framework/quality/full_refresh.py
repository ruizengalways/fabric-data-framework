"""Reconciliation gates for FULL -> REPLACE publication candidates."""

from __future__ import annotations

from uuid import UUID

from ..capture.full import FullSnapshotEvidence
from ..operations import (
    ReconciliationMetric,
    ReconciliationResult,
    ReconciliationStatus,
    RowAccounting,
)


def reconcile_full_replace(
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    policy_name: str,
    accounting: RowAccounting,
    candidate_row_count: int,
    evidence: FullSnapshotEvidence,
    force_fail: bool = False,
) -> ReconciliationResult:
    metrics = [
        ReconciliationMetric(
            name="source_row_count_accounted",
            expected=evidence.source_row_count,
            actual=accounting.rows_read,
            passed=evidence.source_row_count == accounting.rows_read,
        ),
        ReconciliationMetric(
            name="candidate_matches_accepted_rows",
            expected=accounting.rows_accepted,
            actual=candidate_row_count,
            passed=accounting.rows_accepted == candidate_row_count,
        ),
        ReconciliationMetric(
            name="snapshot_complete",
            expected=1,
            actual=1 if evidence.complete else 0,
            passed=evidence.complete,
        ),
    ]
    if force_fail:
        metrics.append(
            ReconciliationMetric(
                name="forced_failure",
                expected=1,
                actual=0,
                passed=False,
            )
        )

    status = (
        ReconciliationStatus.PASS
        if all(metric.passed for metric in metrics)
        else ReconciliationStatus.FAIL
    )
    return ReconciliationResult(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy_name=policy_name,
        status=status,
        metrics=tuple(metrics),
        blocks_state_advance=True,
    )
