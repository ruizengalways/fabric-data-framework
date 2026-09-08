"""APPEND reconciliation helpers."""

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
from fabric_data_framework.quality.reconciliation_engine import evaluate_reconciliation_policy


def reconcile_append(
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    policy: ReconciliationPolicy,
    accounting: RowAccounting,
    inserted: int,
    replayed: int,
    duplicate_incoming: int,
    observations: Sequence[ReconciliationObservation] = (),
    force_fail: bool = False,
) -> ReconciliationResult:
    """Prove that every accepted APPEND row is inserted or idempotently accounted."""

    accounted = inserted + replayed + duplicate_incoming
    forced_ok = not force_fail
    metrics = (
        ReconciliationMetric(
            name="append_accepted_accounted",
            expected=accounting.rows_accepted,
            actual=accounted,
            passed=accounted == accounting.rows_accepted,
        ),
        ReconciliationMetric(
            name="append_forced_gate",
            expected="PASS",
            actual="PASS" if forced_ok else "FAIL",
            passed=forced_ok,
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


__all__ = ["reconcile_append"]
