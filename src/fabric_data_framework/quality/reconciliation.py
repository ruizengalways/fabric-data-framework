"""Reusable reconciliation gates for reference/integration executions."""

from __future__ import annotations

from typing import Mapping, Sequence
from uuid import UUID

from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationMetric,
    ReconciliationResult,
    ReconciliationStatus,
)
from fabric_data_framework.apply.scd2 import assert_one_current_row


def reconcile_scd2_batch(
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    policy_name: str,
    accounting: RowAccounting,
    proposed_rows: Sequence[Mapping],
    business_key: tuple[str, ...],
    force_fail: bool = False,
) -> ReconciliationResult:
    metrics: list[ReconciliationMetric] = [
        ReconciliationMetric(
            name="source_accounting",
            expected=accounting.rows_read,
            actual=accounting.rows_accepted + accounting.rows_quarantined + accounting.rows_filtered,
            passed=(
                accounting.rows_read
                == accounting.rows_accepted + accounting.rows_quarantined + accounting.rows_filtered
            ),
        )
    ]

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

    passed = all(metric.passed for metric in metrics)
    return ReconciliationResult(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy_name=policy_name,
        status=ReconciliationStatus.PASS if passed else ReconciliationStatus.FAIL,
        metrics=tuple(metrics),
        blocks_state_advance=True,
    )
