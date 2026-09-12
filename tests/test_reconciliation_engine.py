from uuid import uuid4

import pytest
from pydantic import ValidationError

from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationMetric,
    ReconciliationObservation,
    ReconciliationSeverity,
    ReconciliationStatus,
)
from fabric_data_framework.metadata.config import (
    ReconciliationAggregate,
    ReconciliationCheck,
    ReconciliationCheckKind,
    ReconciliationPolicy,
)
from fabric_data_framework.quality.reconciliation.engine import evaluate_reconciliation_policy


DATASET_ID = "orders.order"


def _evaluate(policy, *observations, accounting=None, base_metrics=()):
    return evaluate_reconciliation_policy(
        dataset_run_id=uuid4(),
        dataset_id=DATASET_ID,
        policy=policy,
        accounting=accounting or RowAccounting(rows_read=10, rows_accepted=10),
        observations=observations,
        base_metrics=base_metrics,
    )


def test_reconciliation_policy_rejects_duplicate_check_ids_and_invalid_shapes():
    check = ReconciliationCheck(
        check_id="row-count",
        kind=ReconciliationCheckKind.ROW_COUNT_MATCH,
    )
    with pytest.raises(ValidationError, match="check_id values must be unique"):
        ReconciliationPolicy(policy_name="orders", checks=(check, check))

    with pytest.raises(ValidationError, match="UNIQUE_KEY requires"):
        ReconciliationCheck(
            check_id="unique-order",
            kind=ReconciliationCheckKind.UNIQUE_KEY,
            columns=("order_id",),
        )
    with pytest.raises(ValidationError, match="NULL_RATE requires"):
        ReconciliationCheck(
            check_id="null-country",
            kind=ReconciliationCheckKind.NULL_RATE,
            column="country",
        )
    with pytest.raises(ValidationError, match="AGGREGATE_MATCH requires"):
        ReconciliationCheck(
            check_id="amount-total",
            kind=ReconciliationCheckKind.AGGREGATE_MATCH,
            column="amount",
        )
    with pytest.raises(ValidationError, match="CUSTOM reconciliation check requires extension"):
        ReconciliationCheck(
            check_id="business-control",
            kind=ReconciliationCheckKind.CUSTOM,
        )

    for field in ("absolute_tolerance", "relative_tolerance"):
        with pytest.raises(ValidationError, match="finite"):
            ReconciliationCheck(
                check_id="finite-tolerance",
                kind=ReconciliationCheckKind.ROW_COUNT_MATCH,
                **{field: float("inf")},
            )


def test_reconciliation_evidence_rejects_non_finite_values_and_partitions():
    with pytest.raises(ValidationError, match="actual must be finite"):
        ReconciliationObservation(check_id="row-count", actual=float("nan"))
    with pytest.raises(ValidationError, match="partition.*must be finite"):
        ReconciliationObservation(
            check_id="row-count",
            actual=1,
            partition={"business_date": float("inf")},
        )
    with pytest.raises(ValidationError, match="expected must be finite"):
        ReconciliationMetric(
            name="invalid-base-metric",
            expected=float("inf"),
            actual=0,
            passed=True,
        )


def test_numeric_count_and_aggregate_checks_apply_tolerance():
    policy = ReconciliationPolicy(
        policy_name="orders",
        checks=(
            ReconciliationCheck(
                check_id="row-count",
                kind=ReconciliationCheckKind.ROW_COUNT_MATCH,
                absolute_tolerance=1,
            ),
            ReconciliationCheck(
                check_id="amount-total",
                kind=ReconciliationCheckKind.AGGREGATE_MATCH,
                column="amount",
                aggregate=ReconciliationAggregate.SUM,
                relative_tolerance=0.01,
            ),
        ),
    )
    result = _evaluate(
        policy,
        ReconciliationObservation(check_id="row-count", expected=100, actual=99),
        ReconciliationObservation(check_id="amount-total", expected=1000.0, actual=1009.0),
    )

    assert result.status is ReconciliationStatus.PASS
    assert all(metric.passed for metric in result.metrics)


def test_warning_failure_is_retained_but_does_not_block_state():
    policy = ReconciliationPolicy(
        policy_name="orders",
        checks=(
            ReconciliationCheck(
                check_id="optional-comment-null-rate",
                kind=ReconciliationCheckKind.NULL_RATE,
                column="comment",
                max_fraction=0.20,
                severity=ReconciliationSeverity.WARNING,
            ),
        ),
    )
    result = _evaluate(
        policy,
        ReconciliationObservation(
            check_id="optional-comment-null-rate",
            actual=0.25,
        ),
    )

    assert result.status is ReconciliationStatus.WARN
    failed = [metric for metric in result.metrics if not metric.passed]
    assert len(failed) == 1
    assert failed[0].blocking is False
    assert failed[0].severity is ReconciliationSeverity.WARNING


def test_error_failure_is_blocking_and_missing_or_unknown_evidence_fails_closed():
    policy = ReconciliationPolicy(
        policy_name="orders",
        checks=(
            ReconciliationCheck(
                check_id="unique-order",
                kind=ReconciliationCheckKind.UNIQUE_KEY,
                columns=("order_id",),
                max_count=0,
            ),
        ),
    )

    duplicate = _evaluate(
        policy,
        ReconciliationObservation(check_id="unique-order", actual=1),
    )
    assert duplicate.status is ReconciliationStatus.FAIL
    assert any(not metric.passed and metric.blocking for metric in duplicate.metrics)

    missing = _evaluate(policy)
    assert missing.status is ReconciliationStatus.FAIL
    assert any(metric.name == "missing_observation:unique-order" for metric in missing.metrics)

    unexpected = _evaluate(
        policy,
        ReconciliationObservation(check_id="unique-order", actual=0),
        ReconciliationObservation(check_id="unconfigured-check", actual=0),
    )
    assert unexpected.status is ReconciliationStatus.FAIL
    assert any(
        metric.name == "unexpected_observation:unconfigured-check"
        for metric in unexpected.metrics
    )


def test_partitioned_checks_require_exact_unique_partition_identity():
    policy = ReconciliationPolicy(
        policy_name="orders",
        checks=(
            ReconciliationCheck(
                check_id="daily-count",
                kind=ReconciliationCheckKind.ROW_COUNT_MATCH,
                partition_by=("business_date",),
            ),
        ),
    )
    good = _evaluate(
        policy,
        ReconciliationObservation(
            check_id="daily-count",
            expected=10,
            actual=10,
            partition={"business_date": "2026-09-07"},
        ),
        ReconciliationObservation(
            check_id="daily-count",
            expected=12,
            actual=12,
            partition={"business_date": "2026-09-08"},
        ),
    )
    assert good.status is ReconciliationStatus.PASS

    wrong_keys = _evaluate(
        policy,
        ReconciliationObservation(
            check_id="daily-count",
            expected=10,
            actual=10,
            partition={"date": "2026-09-07"},
        ),
    )
    assert wrong_keys.status is ReconciliationStatus.FAIL
    assert any(metric.name == "invalid_partition:daily-count" for metric in wrong_keys.metrics)

    duplicate = _evaluate(
        policy,
        ReconciliationObservation(
            check_id="daily-count",
            expected=10,
            actual=10,
            partition={"business_date": "2026-09-07"},
        ),
        ReconciliationObservation(
            check_id="daily-count",
            expected=10,
            actual=10,
            partition={"business_date": "2026-09-07"},
        ),
    )
    assert duplicate.status is ReconciliationStatus.FAIL
    assert any(metric.name == "duplicate_partition:daily-count" for metric in duplicate.metrics)


def test_null_rate_checksum_and_custom_checks_have_explicit_semantics():
    policy = ReconciliationPolicy(
        policy_name="orders",
        checks=(
            ReconciliationCheck(
                check_id="country-null-rate",
                kind=ReconciliationCheckKind.NULL_RATE,
                column="country",
                max_fraction=0.01,
            ),
            ReconciliationCheck(
                check_id="business-hash",
                kind=ReconciliationCheckKind.CHECKSUM_MATCH,
                columns=("order_id", "amount"),
            ),
            ReconciliationCheck(
                check_id="header-line-balance",
                kind=ReconciliationCheckKind.CUSTOM,
                extension="orders.header_line_balance",
            ),
        ),
    )
    result = _evaluate(
        policy,
        ReconciliationObservation(check_id="country-null-rate", actual=0.0),
        ReconciliationObservation(check_id="business-hash", expected="abc", actual="abc"),
        ReconciliationObservation(
            check_id="header-line-balance",
            expected="balanced",
            actual="balanced",
            passed=True,
        ),
    )
    assert result.status is ReconciliationStatus.PASS

    checksum_fail = _evaluate(
        policy,
        ReconciliationObservation(check_id="country-null-rate", actual=0.0),
        ReconciliationObservation(check_id="business-hash", expected="abc", actual="def"),
        ReconciliationObservation(check_id="header-line-balance", passed=True),
    )
    assert checksum_fail.status is ReconciliationStatus.FAIL


def test_strategy_base_metric_and_row_accounting_compose_with_declarative_checks():
    policy = ReconciliationPolicy(policy_name="orders")
    result = _evaluate(
        policy,
        base_metrics=(
            ReconciliationMetric(
                name="one_current_row_per_business_key",
                expected="true",
                actual="false",
                passed=False,
            ),
        ),
    )

    assert result.status is ReconciliationStatus.FAIL
    assert any(metric.name == "row_accounting" for metric in result.metrics)
    assert any(metric.name == "one_current_row_per_business_key" for metric in result.metrics)


def test_nonblocking_policy_records_fail_without_claiming_state_gate_authority():
    policy = ReconciliationPolicy(
        policy_name="observability-only",
        required_for_state_commit=False,
        checks=(
            ReconciliationCheck(
                check_id="row-count",
                kind=ReconciliationCheckKind.ROW_COUNT_MATCH,
            ),
        ),
    )
    result = _evaluate(
        policy,
        ReconciliationObservation(check_id="row-count", expected=100, actual=90),
    )

    assert result.status is ReconciliationStatus.FAIL
    assert result.blocks_state_advance is False


def test_warning_metric_cannot_be_declared_blocking():
    with pytest.raises(ValidationError, match="WARNING reconciliation metric cannot block"):
        ReconciliationMetric(
            name="warning",
            expected=1,
            actual=0,
            passed=False,
            severity=ReconciliationSeverity.WARNING,
            blocking=True,
        )
