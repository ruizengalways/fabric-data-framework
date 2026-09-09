"""Declarative, provider-neutral reconciliation policy evaluation.

Physical SQL/Spark/native adapters collect scalar observations. This module owns the
policy semantics, tolerance, warning/failure classification, and state-gate result.
Keeping collection separate from evaluation lets large datasets reconcile with pushed-
down aggregates instead of materializing business rows in the framework process.
"""

from __future__ import annotations

from collections import defaultdict
from numbers import Real
from typing import Iterable, Sequence
from uuid import UUID

from fabric_data_framework.contracts.audit import RowAccounting
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationMetric,
    ReconciliationObservation,
    ReconciliationResult,
    ReconciliationSeverity,
    ReconciliationStatus,
)
from fabric_data_framework.metadata.config import (
    ReconciliationCheck,
    ReconciliationCheckKind,
    ReconciliationPolicy,
)


class ReconciliationEvaluationError(ValueError):
    """Configured reconciliation evidence is malformed or semantically inconsistent."""


def _blocking(severity: ReconciliationSeverity) -> bool:
    return severity is ReconciliationSeverity.ERROR


def _metric(
    *,
    check: ReconciliationCheck,
    name: str,
    expected: str | int | float | bool,
    actual: str | int | float | bool,
    passed: bool,
    partition: dict | None = None,
) -> ReconciliationMetric:
    return ReconciliationMetric(
        name=name,
        check_id=check.check_id,
        expected=expected,
        actual=actual,
        passed=passed,
        severity=check.severity,
        blocking=_blocking(check.severity),
        partition=partition,
    )


def _error_metric(
    *,
    check_id: str,
    name: str,
    expected: str,
    actual: str,
) -> ReconciliationMetric:
    return ReconciliationMetric(
        name=name,
        check_id=check_id,
        expected=expected,
        actual=actual,
        passed=False,
        severity=ReconciliationSeverity.ERROR,
        blocking=True,
    )


def _numeric(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    return float(value)


def _within_tolerance(
    expected: float,
    actual: float,
    *,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> bool:
    allowed = absolute_tolerance + relative_tolerance * abs(expected)
    return abs(actual - expected) <= allowed


def _partition_label(check: ReconciliationCheck, observation: ReconciliationObservation) -> str:
    if not check.partition_by:
        return check.check_id
    assert observation.partition is not None
    values = ",".join(f"{key}={observation.partition[key]}" for key in check.partition_by)
    return f"{check.check_id}[{values}]"


def _validate_partition(
    check: ReconciliationCheck,
    observation: ReconciliationObservation,
) -> str | None:
    partition = observation.partition or {}
    expected = set(check.partition_by)
    actual = set(partition)
    if expected != actual:
        return (
            "partition keys do not match policy: "
            f"expected={sorted(expected)}, actual={sorted(actual)}"
        )
    return None


def _evaluate_observation(
    check: ReconciliationCheck,
    observation: ReconciliationObservation,
) -> ReconciliationMetric:
    name = _partition_label(check, observation)
    partition = observation.partition

    if check.kind in {
        ReconciliationCheckKind.ROW_COUNT_MATCH,
        ReconciliationCheckKind.AGGREGATE_MATCH,
    }:
        expected = _numeric(observation.expected)
        actual = _numeric(observation.actual)
        if expected is None or actual is None:
            return _metric(
                check=check,
                name=name,
                expected="numeric source observation",
                actual="missing/non-numeric observation",
                passed=False,
                partition=partition,
            )
        passed = _within_tolerance(
            expected,
            actual,
            absolute_tolerance=check.absolute_tolerance,
            relative_tolerance=check.relative_tolerance,
        )
        return _metric(
            check=check,
            name=name,
            expected=observation.expected,  # type: ignore[arg-type]
            actual=observation.actual,  # type: ignore[arg-type]
            passed=passed,
            partition=partition,
        )

    if check.kind is ReconciliationCheckKind.CHECKSUM_MATCH:
        if observation.expected is None or observation.actual is None:
            return _metric(
                check=check,
                name=name,
                expected="source checksum",
                actual="missing checksum observation",
                passed=False,
                partition=partition,
            )
        return _metric(
            check=check,
            name=name,
            expected=observation.expected,
            actual=observation.actual,
            passed=observation.expected == observation.actual,
            partition=partition,
        )

    if check.kind is ReconciliationCheckKind.UNIQUE_KEY:
        actual = _numeric(observation.actual)
        if actual is None or actual < 0 or not actual.is_integer():
            return _metric(
                check=check,
                name=name,
                expected=f"duplicate_count <= {check.max_count}",
                actual="missing/non-integer duplicate count",
                passed=False,
                partition=partition,
            )
        assert check.max_count is not None
        return _metric(
            check=check,
            name=name,
            expected=check.max_count,
            actual=int(actual),
            passed=int(actual) <= check.max_count,
            partition=partition,
        )

    if check.kind is ReconciliationCheckKind.NULL_RATE:
        actual = _numeric(observation.actual)
        if actual is None or actual < 0 or actual > 1:
            return _metric(
                check=check,
                name=name,
                expected=f"null_fraction <= {check.max_fraction}",
                actual="missing/out-of-range null fraction",
                passed=False,
                partition=partition,
            )
        assert check.max_fraction is not None
        return _metric(
            check=check,
            name=name,
            expected=check.max_fraction,
            actual=actual,
            passed=actual <= check.max_fraction,
            partition=partition,
        )

    if check.kind is ReconciliationCheckKind.CUSTOM:
        if observation.passed is None:
            return _metric(
                check=check,
                name=name,
                expected="custom provider decision",
                actual="missing custom decision",
                passed=False,
                partition=partition,
            )
        return _metric(
            check=check,
            name=name,
            expected=observation.expected if observation.expected is not None else "PASS",
            actual=(
                observation.actual
                if observation.actual is not None
                else ("PASS" if observation.passed else "FAIL")
            ),
            passed=observation.passed,
            partition=partition,
        )

    raise ReconciliationEvaluationError(f"unsupported reconciliation check kind: {check.kind}")


def evaluate_reconciliation_policy(
    *,
    dataset_run_id: UUID,
    dataset_id: str,
    policy: ReconciliationPolicy,
    accounting: RowAccounting | None,
    observations: Sequence[ReconciliationObservation] = (),
    base_metrics: Iterable[ReconciliationMetric] = (),
) -> ReconciliationResult:
    """Evaluate one source-controlled policy over provider-produced observations.

    ``base_metrics`` is the composition point for strategy-specific invariants such as
    SCD2 one-current-row or APPEND identity accounting. Declarative checks add portable
    source/target controls without replacing those strategy semantics.
    """

    metrics: list[ReconciliationMetric] = list(base_metrics)
    if policy.include_row_accounting:
        if accounting is None:
            metrics.append(
                _error_metric(
                    check_id="__row_accounting__",
                    name="row_accounting",
                    expected="RowAccounting evidence",
                    actual="missing",
                )
            )
        else:
            accounted = (
                accounting.rows_accepted
                + accounting.rows_quarantined
                + accounting.rows_filtered
            )
            metrics.append(
                ReconciliationMetric(
                    name="row_accounting",
                    check_id="__row_accounting__",
                    expected=accounting.rows_read,
                    actual=accounted,
                    passed=accounting.rows_read == accounted,
                    severity=ReconciliationSeverity.ERROR,
                    blocking=True,
                )
            )

    by_id: dict[str, list[ReconciliationObservation]] = defaultdict(list)
    configured = {check.check_id: check for check in policy.checks}
    for observation in observations:
        by_id[observation.check_id].append(observation)

    for unknown in sorted(set(by_id) - set(configured)):
        metrics.append(
            _error_metric(
                check_id=unknown,
                name=f"unexpected_observation:{unknown}",
                expected="configured check_id",
                actual="not configured",
            )
        )

    for check in policy.checks:
        check_observations = by_id.get(check.check_id, [])
        if not check_observations:
            metrics.append(
                _error_metric(
                    check_id=check.check_id,
                    name=f"missing_observation:{check.check_id}",
                    expected="at least one observation",
                    actual="missing",
                )
            )
            continue
        if not check.partition_by and len(check_observations) != 1:
            metrics.append(
                _error_metric(
                    check_id=check.check_id,
                    name=f"duplicate_observation:{check.check_id}",
                    expected="exactly one unpartitioned observation",
                    actual=str(len(check_observations)),
                )
            )
            continue

        seen_partitions: set[tuple[tuple[str, object], ...]] = set()
        for observation in check_observations:
            partition_error = _validate_partition(check, observation)
            if partition_error is not None:
                metrics.append(
                    _error_metric(
                        check_id=check.check_id,
                        name=f"invalid_partition:{check.check_id}",
                        expected=str(tuple(check.partition_by)),
                        actual=partition_error,
                    )
                )
                continue
            partition_key = tuple(
                (key, (observation.partition or {})[key]) for key in check.partition_by
            )
            if partition_key in seen_partitions:
                metrics.append(
                    _error_metric(
                        check_id=check.check_id,
                        name=f"duplicate_partition:{check.check_id}",
                        expected="one observation per partition",
                        actual=str(dict(partition_key)),
                    )
                )
                continue
            seen_partitions.add(partition_key)
            metrics.append(_evaluate_observation(check, observation))

    failed = tuple(metric for metric in metrics if not metric.passed)
    if any(metric.blocking for metric in failed):
        status = ReconciliationStatus.FAIL
    elif failed:
        status = ReconciliationStatus.WARN
    else:
        status = ReconciliationStatus.PASS

    return ReconciliationResult(
        dataset_run_id=dataset_run_id,
        dataset_id=dataset_id,
        policy_name=policy.policy_name,
        status=status,
        metrics=tuple(metrics),
        blocks_state_advance=policy.required_for_state_commit,
    )


__all__ = ["ReconciliationEvaluationError", "evaluate_reconciliation_policy"]
