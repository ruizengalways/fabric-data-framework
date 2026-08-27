from uuid import uuid4

import pytest
from pydantic import ValidationError

from fabric_data_framework.operations import (
    QuarantineBatch,
    QuarantineScope,
    ReconciliationMetric,
    ReconciliationResult,
    ReconciliationStatus,
    RowAccounting,
)


def test_row_accounting_prevents_silent_loss():
    balanced = RowAccounting(
        rows_read=100,
        rows_accepted=95,
        rows_quarantined=3,
        rows_filtered=2,
    )
    assert balanced.rows_read == 100

    with pytest.raises(ValidationError, match="row accounting"):
        RowAccounting(
            rows_read=100,
            rows_accepted=95,
            rows_quarantined=1,
            rows_filtered=1,
        )


def test_reconciliation_pass_cannot_hide_failed_metric():
    with pytest.raises(ValidationError, match="failed metrics"):
        ReconciliationResult(
            dataset_run_id=uuid4(),
            dataset_id="crm.customer",
            policy_name="count_and_key",
            status=ReconciliationStatus.PASS,
            metrics=(
                ReconciliationMetric(name="row_count", expected=10, actual=9, passed=False),
            ),
        )


def test_quarantine_has_run_lineage_and_positive_row_count():
    quarantine = QuarantineBatch(
        dataset_run_id=uuid4(),
        dataset_id="crm.customer",
        scope=QuarantineScope.ROW,
        row_count=3,
        reason_code="DQ_EMAIL_INVALID",
    )
    assert quarantine.row_count == 3

    with pytest.raises(ValidationError):
        QuarantineBatch(
            dataset_run_id=uuid4(),
            dataset_id="crm.customer",
            scope=QuarantineScope.BATCH,
            row_count=0,
            reason_code="SCHEMA_BREAK",
        )
