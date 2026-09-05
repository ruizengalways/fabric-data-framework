from uuid import uuid4

from fabric_data_framework.contracts.dispatch import (
    DatasetDispatchOutcome,
    PipelineDispatchResult,
)
from fabric_data_framework.metadata.config import DatasetStatus, PipelineStatus
from fabric_data_framework.recovery.pipeline import (
    RecoveryAction,
    RecoveryCategory,
    build_pipeline_recovery_plan,
    recommend_dataset_recovery,
)


def _outcome(status, *, code=None, retryable=None):
    return DatasetDispatchOutcome(
        dataset_run_id=uuid4(),
        status=status,
        error_code=code,
        error_message=code or status.value,
        retryable=retryable,
    )


def test_only_explicit_transient_failure_is_safe_for_automatic_retry():
    transient = recommend_dataset_recovery(
        "crm.customer",
        _outcome(DatasetStatus.FAILED, code="HTTP_503", retryable=True),
    )
    assert transient.category is RecoveryCategory.TRANSIENT_PROVIDER
    assert transient.action is RecoveryAction.RETRY
    assert transient.safe_for_automatic_retry is True

    unknown = recommend_dataset_recovery(
        "crm.order",
        _outcome(
            DatasetStatus.FAILED,
            code="UNKNOWN_COMMIT_UNRESOLVED",
            retryable=True,
        ),
    )
    assert unknown.category is RecoveryCategory.UNKNOWN_COMMIT
    assert unknown.action is RecoveryAction.RECONCILE_UNKNOWN_OUTCOME
    assert unknown.safe_for_automatic_retry is False


def test_dq_reconciliation_and_dependency_failures_require_targeted_repair():
    threshold = recommend_dataset_recovery(
        "crm.customer",
        _outcome(
            DatasetStatus.FAILED,
            code="DATA_QUALITY_QUARANTINE_THRESHOLD_EXCEEDED",
        ),
    )
    assert threshold.action is RecoveryAction.FIX_DATA_AND_REPLAY

    reconciliation = recommend_dataset_recovery(
        "crm.balance",
        _outcome(DatasetStatus.FAILED, code="RECONCILIATION_FAILED"),
    )
    assert reconciliation.action is RecoveryAction.INVESTIGATE_RECONCILIATION

    blocked = recommend_dataset_recovery(
        "crm.child",
        _outcome(DatasetStatus.BLOCKED, code="BLOCKED_DEPENDENCY"),
    )
    assert blocked.action is RecoveryAction.RETRY_AFTER_DEPENDENCY


def test_pipeline_recovery_plan_separates_safe_auto_retry_from_operator_work():
    pipeline_run_id = uuid4()
    result = PipelineDispatchResult(
        pipeline_run_id=pipeline_run_id,
        status=PipelineStatus.FAILED,
        selected_dataset_ids=("ok", "transient", "dq", "blocked"),
        outcomes=(
            ("ok", _outcome(DatasetStatus.SUCCEEDED)),
            (
                "transient",
                _outcome(DatasetStatus.FAILED, code="HTTP_503", retryable=True),
            ),
            (
                "dq",
                _outcome(
                    DatasetStatus.FAILED,
                    code="DATA_QUALITY_QUARANTINE_THRESHOLD_EXCEEDED",
                ),
            ),
            (
                "blocked",
                _outcome(DatasetStatus.BLOCKED, code="BLOCKED_DEPENDENCY"),
            ),
        ),
        max_concurrency=4,
    )

    plan = build_pipeline_recovery_plan(result)
    assert plan.pipeline_run_id == pipeline_run_id
    assert plan.safe_auto_retry_dataset_ids == ("transient",)
    assert plan.operator_action_dataset_ids == ("dq", "blocked")
