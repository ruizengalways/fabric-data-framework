"""Fail-closed evidence contracts for representative live business paths.

The release readiness matrix requires live FULL->REPLACE, WATERMARK->SCD1/SCD2,
retry/idempotency and reconciliation-fail-closed proof. Reference/in-memory apply
engines are not sufficient for those release gates.

This module deliberately separates independently sourced facts:

* :class:`ApprovedPipelineEvidenceReport` is produced by the framework-owned Fabric
  Pipeline runner and contains native provider status plus the durable framework
  DatasetDispatchOutcome.
* :class:`BusinessPathStateObservation` is a bounded customer/provider observation of
  target/progress state before/after execution. The observer cannot choose PASS/FAIL.
* :func:`evaluate_business_path_evidence` applies source-controlled expectations and
  is the only place that projects those facts into a release readiness proof result.
"""

from __future__ import annotations

from enum import Enum
import hashlib
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from fabric_data_framework.adapters.fabric.rest import FabricJobStatus
from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.deployment.contracts import ReleaseManifest
from fabric_data_framework.evidence.approved_pipeline_runner import (
    ApprovedPipelineEvidenceReport,
)
from fabric_data_framework.evidence.release_readiness import (
    ReleaseReadinessGateKind,
    ReleaseReadinessProofResult,
    ReleaseReadinessStatus,
)
from fabric_data_framework.evidence.safety import assert_safe_retained_text
from fabric_data_framework.metadata.config import DatasetStatus, canonical_hash


class BusinessPathGate(str, Enum):
    FULL_REPLACE = "full.replace"
    WATERMARK_SCD1 = "watermark.scd1"
    WATERMARK_SCD2 = "watermark.scd2"
    RETRY_IDEMPOTENCY = "retry.idempotency"
    RECONCILIATION_FAIL_CLOSED = "reconciliation.fail_closed"

    @property
    def readiness_kind(self) -> ReleaseReadinessGateKind:
        return {
            BusinessPathGate.FULL_REPLACE: ReleaseReadinessGateKind.FULL_REPLACE,
            BusinessPathGate.WATERMARK_SCD1: ReleaseReadinessGateKind.WATERMARK_SCD1,
            BusinessPathGate.WATERMARK_SCD2: ReleaseReadinessGateKind.WATERMARK_SCD2,
            BusinessPathGate.RETRY_IDEMPOTENCY: ReleaseReadinessGateKind.RETRY_IDEMPOTENCY,
            BusinessPathGate.RECONCILIATION_FAIL_CLOSED: (
                ReleaseReadinessGateKind.RECONCILIATION_FAIL_CLOSED
            ),
        }[self]


class BusinessPathObservationPhase(str, Enum):
    BEFORE = "BEFORE"
    AFTER_FIRST_ATTEMPT = "AFTER_FIRST_ATTEMPT"
    AFTER_FINAL_ATTEMPT = "AFTER_FINAL_ATTEMPT"


class BusinessPathStateObservation(FrozenModel):
    """Bounded semantic state facts supplied by an exact-release observer extension."""

    dataset_id: str = Field(min_length=1, max_length=256)
    phase: BusinessPathObservationPhase
    target_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_row_count: int = Field(ge=0)
    progress_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    history_semantic_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    one_current_row_per_business_key: bool | None = None
    evidence_references: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_safe_references(self) -> "BusinessPathStateObservation":
        if len(set(self.evidence_references)) != len(self.evidence_references):
            raise ValueError("business path observation evidence references must be unique")
        for index, reference in enumerate(self.evidence_references):
            assert_safe_retained_text(reference, f"evidence_references[{index}]")
        return self

    @property
    def semantic_state_identity(self) -> tuple[object, ...]:
        return (
            self.target_semantic_sha256,
            self.target_row_count,
            self.progress_semantic_sha256,
            self.history_semantic_sha256,
            self.one_current_row_per_business_key,
        )


class ApprovedBusinessPathScenario(FrozenModel):
    """Source-controlled expectation for one representative exact-release path."""

    gate_id: BusinessPathGate
    dataset_id: str = Field(min_length=1, max_length=256)
    observer_extension: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    extension_artifact_name: str = Field(min_length=1, max_length=512)
    scenario_artifact_name: str = Field(min_length=1, max_length=512)
    expected_success_target_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_success_target_row_count: int = Field(ge=0)
    expected_success_progress_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_success_history_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    expected_failure_error_code: str | None = Field(default=None, max_length=1024)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_gate_specific_expectations(self) -> "ApprovedBusinessPathScenario":
        if self.gate_id is BusinessPathGate.WATERMARK_SCD2:
            if self.expected_success_history_sha256 is None:
                raise ValueError("WATERMARK_SCD2 scenario requires expected history SHA256")
        elif self.expected_success_history_sha256 is not None:
            raise ValueError("expected history SHA256 is only valid for WATERMARK_SCD2")

        needs_failure = self.gate_id in {
            BusinessPathGate.RETRY_IDEMPOTENCY,
            BusinessPathGate.RECONCILIATION_FAIL_CLOSED,
        }
        if needs_failure and self.expected_failure_error_code is None:
            raise ValueError(f"{self.gate_id.value} scenario requires expected failure error_code")
        if not needs_failure and self.expected_failure_error_code is not None:
            raise ValueError(
                "expected failure error_code is only valid for retry/reconciliation scenarios"
            )
        if self.expected_failure_error_code is not None:
            assert_safe_retained_text(
                self.expected_failure_error_code,
                "business path expected failure error_code",
            )
        assert_safe_retained_text(self.model_dump_json(), "business path scenario")
        return self

    @property
    def scenario_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class BusinessPathRunEvidence(FrozenModel):
    """Independently sourced facts consumed by the business-path evaluator."""

    scenario_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    before: BusinessPathStateObservation
    after_first_attempt: BusinessPathStateObservation | None = None
    after_final_attempt: BusinessPathStateObservation
    pipeline_reports: tuple[ApprovedPipelineEvidenceReport, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_membership(self) -> "BusinessPathRunEvidence":
        dataset_ids = {self.before.dataset_id, self.after_final_attempt.dataset_id}
        if self.after_first_attempt is not None:
            dataset_ids.add(self.after_first_attempt.dataset_id)
        dataset_ids.update(report.dataset_id for report in self.pipeline_reports)
        if len(dataset_ids) != 1:
            raise ValueError("business path observations/reports must target one dataset_id")
        if self.before.phase is not BusinessPathObservationPhase.BEFORE:
            raise ValueError("business path before observation must use BEFORE phase")
        if self.after_final_attempt.phase is not BusinessPathObservationPhase.AFTER_FINAL_ATTEMPT:
            raise ValueError("final observation must use AFTER_FINAL_ATTEMPT phase")
        if self.after_first_attempt is not None and (
            self.after_first_attempt.phase
            is not BusinessPathObservationPhase.AFTER_FIRST_ATTEMPT
        ):
            raise ValueError("first-attempt observation must use AFTER_FIRST_ATTEMPT phase")
        plan_hashes = {report.execution_plan_hash for report in self.pipeline_reports}
        if len(plan_hashes) != 1:
            raise ValueError("business path retries must use the same execution plan hash")
        return self


class BusinessPathObservationRequest(FrozenModel):
    """Bounded request supplied to an exact-release observer extension."""

    gate_id: BusinessPathGate
    dataset_id: str = Field(min_length=1, max_length=256)
    phase: BusinessPathObservationPhase
    dataset_run_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


_GATE_REPORT_COUNT = {
    BusinessPathGate.FULL_REPLACE: 1,
    BusinessPathGate.WATERMARK_SCD1: 1,
    BusinessPathGate.WATERMARK_SCD2: 1,
    BusinessPathGate.RETRY_IDEMPOTENCY: 2,
    BusinessPathGate.RECONCILIATION_FAIL_CLOSED: 1,
}


def _require_report_identity(
    scenario: ApprovedBusinessPathScenario,
    run: BusinessPathRunEvidence,
) -> None:
    if run.scenario_hash != scenario.scenario_hash:
        raise ValueError("business path run scenario hash mismatch")
    if run.before.dataset_id != scenario.dataset_id:
        raise ValueError("business path run dataset_id mismatch")
    expected_count = _GATE_REPORT_COUNT[scenario.gate_id]
    if len(run.pipeline_reports) != expected_count:
        raise ValueError(
            f"{scenario.gate_id.value} requires exactly {expected_count} Pipeline report(s)"
        )
    report_ids = [report.dataset_run_id for report in run.pipeline_reports]
    if len(set(report_ids)) != len(report_ids):
        raise ValueError("business path Pipeline reports must have distinct dataset_run_id values")


def _require_completed_success(report: ApprovedPipelineEvidenceReport) -> None:
    if report.remote_status is not FabricJobStatus.COMPLETED:
        raise ValueError(
            f"business path successful attempt requires Fabric Completed; observed={report.remote_status.value}"
        )
    if report.framework_status is not DatasetStatus.SUCCEEDED:
        raise ValueError(
            "business path successful attempt requires framework SUCCEEDED; "
            f"observed={report.framework_status.value}"
        )


def _require_expected_success_state(
    scenario: ApprovedBusinessPathScenario,
    observation: BusinessPathStateObservation,
) -> None:
    if observation.target_semantic_sha256 != scenario.expected_success_target_sha256:
        raise ValueError("business path final target semantic SHA256 mismatch")
    if observation.target_row_count != scenario.expected_success_target_row_count:
        raise ValueError("business path final target row count mismatch")
    if observation.progress_semantic_sha256 != scenario.expected_success_progress_sha256:
        raise ValueError("business path final progress semantic SHA256 mismatch")
    if scenario.gate_id is BusinessPathGate.WATERMARK_SCD2:
        if observation.history_semantic_sha256 != scenario.expected_success_history_sha256:
            raise ValueError("business path final SCD2 history semantic SHA256 mismatch")
        if observation.one_current_row_per_business_key is not True:
            raise ValueError("business path SCD2 final state violates one-current-row invariant")


def _require_meaningful_success_change(
    before: BusinessPathStateObservation,
    final: BusinessPathStateObservation,
) -> None:
    if final.semantic_state_identity == before.semantic_state_identity:
        raise ValueError("representative live success path did not change semantic state")


def _require_state_unchanged(
    before: BusinessPathStateObservation,
    after: BusinessPathStateObservation,
    *,
    label: str,
) -> None:
    if after.semantic_state_identity != before.semantic_state_identity:
        raise ValueError(f"{label} changed target/progress semantic state")


def _collect_references(run: BusinessPathRunEvidence) -> tuple[str, ...]:
    values: list[str] = []
    for observation in (run.before, run.after_first_attempt, run.after_final_attempt):
        if observation is not None:
            values.extend(observation.evidence_references)
    for report in run.pipeline_reports:
        values.extend(report.evidence_references)
    deduped = tuple(dict.fromkeys(values))
    if not deduped:
        raise ValueError("business path PASS requires retained evidence references")
    return deduped


def evaluate_business_path_evidence(
    scenario: ApprovedBusinessPathScenario,
    run: BusinessPathRunEvidence,
) -> ReleaseReadinessProofResult:
    """Project independently sourced live facts into one release proof result.

    Validation errors are intentional fail-closed behavior. The caller must not convert
    an exception to PASS. A PASS result is returned only after every gate-specific
    invariant below has been satisfied.
    """

    _require_report_identity(scenario, run)

    if scenario.gate_id in {
        BusinessPathGate.FULL_REPLACE,
        BusinessPathGate.WATERMARK_SCD1,
        BusinessPathGate.WATERMARK_SCD2,
    }:
        if run.after_first_attempt is not None:
            raise ValueError("single-attempt business path must not include first-attempt state")
        report = run.pipeline_reports[0]
        _require_completed_success(report)
        _require_expected_success_state(scenario, run.after_final_attempt)
        _require_meaningful_success_change(run.before, run.after_final_attempt)

    elif scenario.gate_id is BusinessPathGate.RETRY_IDEMPOTENCY:
        if run.after_first_attempt is None:
            raise ValueError("retry/idempotency proof requires first-attempt state observation")
        first, final = run.pipeline_reports
        if first.framework_status is not DatasetStatus.FAILED:
            raise ValueError("retry first attempt must be framework FAILED")
        if first.retryable is not True:
            raise ValueError("retry first attempt must be explicitly retryable")
        if first.error_code != scenario.expected_failure_error_code:
            raise ValueError("retry first-attempt error_code does not match scenario")
        _require_state_unchanged(
            run.before,
            run.after_first_attempt,
            label="failed retry attempt",
        )
        _require_completed_success(final)
        _require_expected_success_state(scenario, run.after_final_attempt)
        _require_meaningful_success_change(run.before, run.after_final_attempt)

    else:
        if run.after_first_attempt is not None:
            raise ValueError("reconciliation proof uses one failed final attempt")
        report = run.pipeline_reports[0]
        if report.remote_status is not FabricJobStatus.COMPLETED:
            raise ValueError(
                "reconciliation fail-closed proof requires provider Completed before framework rejection"
            )
        if report.framework_status is not DatasetStatus.FAILED:
            raise ValueError("reconciliation fail-closed proof requires framework FAILED")
        if report.error_code != scenario.expected_failure_error_code:
            raise ValueError("reconciliation failure error_code does not match scenario")
        _require_state_unchanged(
            run.before,
            run.after_final_attempt,
            label="failed reconciliation attempt",
        )
        if scenario.expected_success_target_sha256 == run.before.target_semantic_sha256:
            raise ValueError(
                "reconciliation scenario expected success state must differ from pre-run target"
            )

    return ReleaseReadinessProofResult(
        gate_id=scenario.gate_id.value,
        kind=scenario.gate_id.readiness_kind,
        status=ReleaseReadinessStatus.PASS,
        evidence_references=_collect_references(run),
        detail=(
            "representative live business path satisfied framework-owned provider/outcome/"
            f"state invariants; scenario_hash={scenario.scenario_hash}"
        ),
    )


def load_approved_business_path_scenario(
    path: str | Path,
    *,
    release_manifest: ReleaseManifest,
) -> ApprovedBusinessPathScenario:
    """Load a source-controlled scenario only when its exact artifact is fingerprinted."""

    source = Path(path)
    raw = source.read_bytes()
    scenario = ApprovedBusinessPathScenario.model_validate_json(raw)
    expected_scenario_digest = release_manifest.artifact_sha256.get(
        scenario.scenario_artifact_name
    )
    if expected_scenario_digest is None:
        raise ValueError("business path scenario artifact is absent from exact release manifest")
    observed_digest = hashlib.sha256(raw).hexdigest()
    if observed_digest != expected_scenario_digest:
        raise ValueError("business path scenario artifact SHA256 mismatch")
    if scenario.extension_artifact_name not in release_manifest.artifact_sha256:
        raise ValueError(
            "business path observer extension artifact is not fingerprinted in exact release manifest"
        )
    return scenario


__all__ = [
    "ApprovedBusinessPathScenario",
    "BusinessPathGate",
    "BusinessPathObservationPhase",
    "BusinessPathObservationRequest",
    "BusinessPathRunEvidence",
    "BusinessPathStateObservation",
    "evaluate_business_path_evidence",
    "load_approved_business_path_scenario",
]
