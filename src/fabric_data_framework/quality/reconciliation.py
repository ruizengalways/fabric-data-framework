"""Reusable SCD2 reconciliation gates."""

from __future__ import annotations

from typing import Mapping, Sequence
from uuid import UUID

from fabric_data_framework.apply.scd2 import assert_one_current_row
from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationMetric,
    ReconciliationObservation,
    ReconciliationResult,
)
from fabric_data_framework.metadata.config import ReconciliationPolicy
from fabric_data_framework.quality.reconciliation_engine import evaluate_reconciliation_policy


def reconcile_scd2_batch(
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    policy: ReconciliationPolicy,
    accounting: RowAccounting,
    proposed_rows: Sequence[Mapping],
    business_key: tuple[str, ...],
    observations: Sequence[ReconciliationObservation] = (),
    force_fail: bool = False,
) -> ReconciliationResult:
    metrics: list[ReconciliationMetric] = []

    invariant_passed = True
    try:
        assert_one_current_row(proposed_rows, business_key)
    except ValueError:
        invariant_passed = False
    metrics.append(
        ReconciliationMetric(
            name="one_current_row_per_business_key",
            expected="true",
            actual="true" if invariant_passed else "false",
            passed=invariant_passed,
        )
    )

    if force_fail:
        metrics.append(
            ReconciliationMetric(
                name="forced_test_gate",
                expected="pass",
                actual="fail",
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


__all__ = ["reconcile_scd2_batch"]
