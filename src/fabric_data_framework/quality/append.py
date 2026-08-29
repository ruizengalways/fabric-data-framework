"""APPEND reconciliation helpers."""

from __future__ import annotations

from uuid import UUID

from ..operations import (
    ReconciliationMetric,
    ReconciliationResult,
    ReconciliationStatus,
    RowAccounting,
)


def reconcile_append(
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    policy_name: str,
    accounting: RowAccounting,
    inserted: int,
    replayed: int,
    duplicate_incoming: int,
    force_fail: bool = False,
) -> ReconciliationResult:
    """Prove that every accepted APPEND row is inserted or idempotently accounted."""

    accounted = inserted + replayed + duplicate_incoming
    accepted_match = accounted == accounting.rows_accepted
    forced_ok = not force_fail
    metrics = (
        ReconciliationMetric(
            name="append_accepted_accounted",
            expected=accounting.rows_accepted,
            actual=accounted,
            passed=accepted_match,
        ),
        ReconciliationMetric(
            name="append_forced_gate",
            expected="PASS",
            actual="PASS" if forced_ok else "FAIL",
            passed=forced_ok,
        ),
    )
    return ReconciliationResult(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy_name=policy_name,
        status=(
            ReconciliationStatus.PASS
            if all(metric.passed for metric in metrics)
            else ReconciliationStatus.FAIL
        ),
        metrics=metrics,
        blocks_state_advance=True,
    )


__all__ = ["reconcile_append"]
