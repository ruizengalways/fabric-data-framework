"""Reconciliation gates for FULL -> REPLACE publication candidates."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from ...capture.full import FullSnapshotEvidence
from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationMetric,
    ReconciliationObservation,
    ReconciliationResult,
)
from fabric_data_framework.metadata.config import ReconciliationPolicy
from fabric_data_framework.quality.reconciliation.engine import evaluate_reconciliation_policy


def reconcile_full_replace(
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    policy: ReconciliationPolicy,
    accounting: RowAccounting,
    candidate_row_count: int,
    evidence: FullSnapshotEvidence,
    observations: Sequence[ReconciliationObservation] = (),
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

    return evaluate_reconciliation_policy(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy=policy,
        accounting=accounting,
        observations=observations,
        base_metrics=metrics,
    )


__all__ = ["reconcile_full_replace"]
