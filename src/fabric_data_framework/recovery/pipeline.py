"""Pipeline-level failure diagnosis and safe recovery recommendations.

This module does not execute recovery. It turns terminal dataset outcomes into a
conservative operator/system plan that composes existing audited recovery primitives:
``execute_with_retry``, ``ReprocessRequest``, quarantine replay, bounded backfill and
full rebuild. Unknown/ambiguous writes, DQ failures and reconciliation failures are
never converted into blind automatic retries.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import Field

from ..contracts.base import FrozenModel
from ..contracts.dispatch import DatasetDispatchOutcome, PipelineDispatchResult
from ..metadata.config import DatasetStatus


class RecoveryCategory(str, Enum):
    TRANSIENT_PROVIDER = "TRANSIENT_PROVIDER"
    DATA_QUALITY = "DATA_QUALITY"
    RECONCILIATION = "RECONCILIATION"
    DEPENDENCY = "DEPENDENCY"
    UNKNOWN_COMMIT = "UNKNOWN_COMMIT"
    CONFIGURATION = "CONFIGURATION"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class RecoveryAction(str, Enum):
    NONE = "NONE"
    RETRY = "RETRY"
    FIX_DATA_AND_RETRY = "FIX_DATA_AND_RETRY"
    FIX_DATA_AND_REPLAY = "FIX_DATA_AND_REPLAY"
    INVESTIGATE_RECONCILIATION = "INVESTIGATE_RECONCILIATION"
    RETRY_AFTER_DEPENDENCY = "RETRY_AFTER_DEPENDENCY"
    RECONCILE_UNKNOWN_OUTCOME = "RECONCILE_UNKNOWN_OUTCOME"
    FIX_CONFIGURATION = "FIX_CONFIGURATION"
    MANUAL_INVESTIGATION = "MANUAL_INVESTIGATION"


class DatasetRecoveryRecommendation(FrozenModel):
    dataset_id: str = Field(min_length=1)
    dataset_run_id: UUID
    category: RecoveryCategory
    action: RecoveryAction
    retryable: bool
    error_code: str | None = None
    reason: str = Field(min_length=1)

    @property
    def safe_for_automatic_retry(self) -> bool:
        return self.action is RecoveryAction.RETRY and self.retryable


class PipelineRecoveryPlan(FrozenModel):
    pipeline_run_id: UUID
    recommendations: tuple[DatasetRecoveryRecommendation, ...]

    @property
    def safe_auto_retry_dataset_ids(self) -> tuple[str, ...]:
        return tuple(
            item.dataset_id
            for item in self.recommendations
            if item.safe_for_automatic_retry
        )

    @property
    def operator_action_dataset_ids(self) -> tuple[str, ...]:
        return tuple(
            item.dataset_id
            for item in self.recommendations
            if item.action not in {RecoveryAction.NONE, RecoveryAction.RETRY}
        )


_UNKNOWN_COMMIT_PREFIXES = (
    "UNKNOWN_COMMIT",
    "TARGET_OPERATION_UNKNOWN",
    "AMBIGUOUS_COMMIT",
)
_CONFIGURATION_CODES = {
    "ORCHESTRATION_INTEGRITY_ERROR",
    "ORCHESTRATION_NO_PROGRESS",
    "INVALID_READY_WAVE_RESULT",
    "FABRIC_PIPELINE_RESULT_MISMATCH",
    "FABRIC_PIPELINE_RESULT_NON_TERMINAL",
}


def recommend_dataset_recovery(
    dataset_id: str,
    outcome: DatasetDispatchOutcome,
) -> DatasetRecoveryRecommendation:
    """Classify one terminal outcome without overclaiming retry safety."""

    code = outcome.error_code or ""
    if outcome.status is DatasetStatus.SUCCEEDED:
        return DatasetRecoveryRecommendation(
            dataset_id=dataset_id,
            dataset_run_id=outcome.dataset_run_id,
            category=RecoveryCategory.UNKNOWN,
            action=RecoveryAction.NONE,
            retryable=False,
            error_code=outcome.error_code,
            reason="dataset already succeeded; no recovery action required",
        )

    if code.startswith(_UNKNOWN_COMMIT_PREFIXES) or "UNKNOWN_COMMIT" in code:
        return DatasetRecoveryRecommendation(
            dataset_id=dataset_id,
            dataset_run_id=outcome.dataset_run_id,
            category=RecoveryCategory.UNKNOWN_COMMIT,
            action=RecoveryAction.RECONCILE_UNKNOWN_OUTCOME,
            retryable=False,
            error_code=outcome.error_code,
            reason=(
                "target mutation outcome is uncertain; reconcile durable target/operation "
                "evidence before any retry to avoid duplicate writes"
            ),
        )

    if code == "DATA_QUALITY_QUARANTINE_THRESHOLD_EXCEEDED":
        return DatasetRecoveryRecommendation(
            dataset_id=dataset_id,
            dataset_run_id=outcome.dataset_run_id,
            category=RecoveryCategory.DATA_QUALITY,
            action=RecoveryAction.FIX_DATA_AND_REPLAY,
            retryable=False,
            error_code=outcome.error_code,
            reason=(
                "quarantined rows exceeded the governed DQ budget; fix source/rule logic, "
                "then replay retained quarantine payload through an audited REPLAY request"
            ),
        )

    if code == "DATA_QUALITY_FAILED_QUARANTINE_DISABLED":
        return DatasetRecoveryRecommendation(
            dataset_id=dataset_id,
            dataset_run_id=outcome.dataset_run_id,
            category=RecoveryCategory.DATA_QUALITY,
            action=RecoveryAction.FIX_DATA_AND_RETRY,
            retryable=False,
            error_code=outcome.error_code,
            reason=(
                "DQ failed while quarantine was disabled; fix the source/rule/configuration "
                "and run an audited RETRY rather than blindly retrying unchanged input"
            ),
        )

    if code == "RECONCILIATION_FAILED":
        return DatasetRecoveryRecommendation(
            dataset_id=dataset_id,
            dataset_run_id=outcome.dataset_run_id,
            category=RecoveryCategory.RECONCILIATION,
            action=RecoveryAction.INVESTIGATE_RECONCILIATION,
            retryable=False,
            error_code=outcome.error_code,
            reason=(
                "required reconciliation blocked state advance; determine whether source, "
                "target, mapping, or reconciliation policy is wrong before reprocessing"
            ),
        )

    if code == "BLOCKED_DEPENDENCY" or outcome.status is DatasetStatus.BLOCKED:
        return DatasetRecoveryRecommendation(
            dataset_id=dataset_id,
            dataset_run_id=outcome.dataset_run_id,
            category=RecoveryCategory.DEPENDENCY,
            action=RecoveryAction.RETRY_AFTER_DEPENDENCY,
            retryable=False,
            error_code=outcome.error_code,
            reason=(
                "dataset did not execute because an upstream dependency failed; recover the "
                "upstream dataset first, then rerun only the affected dependency chain"
            ),
        )

    if outcome.status is DatasetStatus.CANCELLED:
        return DatasetRecoveryRecommendation(
            dataset_id=dataset_id,
            dataset_run_id=outcome.dataset_run_id,
            category=RecoveryCategory.CANCELLED,
            action=RecoveryAction.MANUAL_INVESTIGATION,
            retryable=False,
            error_code=outcome.error_code,
            reason=(
                "cancelled execution may have partial provider-side effects; confirm target and "
                "checkpoint state before deciding whether retry is safe"
            ),
        )

    if code in _CONFIGURATION_CODES or "CONFIG" in code or "BINDING" in code:
        return DatasetRecoveryRecommendation(
            dataset_id=dataset_id,
            dataset_run_id=outcome.dataset_run_id,
            category=RecoveryCategory.CONFIGURATION,
            action=RecoveryAction.FIX_CONFIGURATION,
            retryable=False,
            error_code=outcome.error_code,
            reason="fix released metadata/binding/configuration and redeploy before retry",
        )

    if outcome.retryable is True:
        return DatasetRecoveryRecommendation(
            dataset_id=dataset_id,
            dataset_run_id=outcome.dataset_run_id,
            category=RecoveryCategory.TRANSIENT_PROVIDER,
            action=RecoveryAction.RETRY,
            retryable=True,
            error_code=outcome.error_code,
            reason=(
                "failure is explicitly classified retryable; use bounded retry with backoff, "
                "attempt lineage and idempotent/operation-journal semantics"
            ),
        )

    return DatasetRecoveryRecommendation(
        dataset_id=dataset_id,
        dataset_run_id=outcome.dataset_run_id,
        category=RecoveryCategory.UNKNOWN,
        action=RecoveryAction.MANUAL_INVESTIGATION,
        retryable=False,
        error_code=outcome.error_code,
        reason=(
            "failure is not explicitly proven safe to retry; inspect dataset/step audit, provider "
            "correlation and state before creating a reprocess request"
        ),
    )


def build_pipeline_recovery_plan(result: PipelineDispatchResult) -> PipelineRecoveryPlan:
    return PipelineRecoveryPlan(
        pipeline_run_id=result.pipeline_run_id,
        recommendations=tuple(
            recommend_dataset_recovery(dataset_id, outcome)
            for dataset_id, outcome in result.outcomes
        ),
    )


__all__ = [
    "DatasetRecoveryRecommendation",
    "PipelineRecoveryPlan",
    "RecoveryAction",
    "RecoveryCategory",
    "build_pipeline_recovery_plan",
    "recommend_dataset_recovery",
]
