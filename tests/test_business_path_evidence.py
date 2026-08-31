from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fabric_data_framework.adapters.fabric.rest import FabricJobStatus
from fabric_data_framework.deployment.contracts import ReleaseBundleIdentity, ReleaseManifest
from fabric_data_framework.evidence.approved_pipeline_runner import ApprovedPipelineEvidenceReport
from fabric_data_framework.evidence.business_path_evidence import (
    ApprovedBusinessPathScenario,
    BusinessPathGate,
    BusinessPathObservationPhase,
    BusinessPathRunEvidence,
    BusinessPathStateObservation,
    evaluate_business_path_evidence,
    load_approved_business_path_scenario,
)
from fabric_data_framework.evidence.release_readiness import (
    ReleaseReadinessGateKind,
    ReleaseReadinessStatus,
)
from fabric_data_framework.metadata.config import DatasetStatus


NOW = datetime(2026, 8, 31, 0, 0, tzinfo=timezone.utc)
A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
E = "e" * 64
F = "f" * 64


def _scenario(
    gate: BusinessPathGate,
    *,
    expected_failure_error_code: str | None = None,
) -> ApprovedBusinessPathScenario:
    return ApprovedBusinessPathScenario(
        gate_id=gate,
        dataset_id="health.patient",
        observer_extension="health.business_path_observer_v1",
        extension_artifact_name="health-business-path-observer.whl",
        scenario_artifact_name=f"{gate.value}.json",
        expected_success_target_sha256=B,
        expected_success_target_row_count=2,
        expected_success_progress_sha256=C,
        expected_success_history_sha256=E
        if gate is BusinessPathGate.WATERMARK_SCD2
        else None,
        expected_failure_error_code=expected_failure_error_code,
        parameters={"fixture": gate.value},
    )


def _observation(
    phase: BusinessPathObservationPhase,
    *,
    target: str,
    count: int,
    progress: str,
    history: str | None = None,
    one_current: bool | None = None,
    reference: str | None = None,
) -> BusinessPathStateObservation:
    return BusinessPathStateObservation(
        dataset_id="health.patient",
        phase=phase,
        target_semantic_sha256=target,
        target_row_count=count,
        progress_semantic_sha256=progress,
        history_semantic_sha256=history,
        one_current_row_per_business_key=one_current,
        evidence_references=(
            reference or f"fabric-state://health.patient/{phase.value.lower()}",
        ),
    )


def _report(
    *,
    remote: FabricJobStatus = FabricJobStatus.COMPLETED,
    framework: DatasetStatus = DatasetStatus.SUCCEEDED,
    retryable: bool | None = None,
    error_code: str | None = None,
    plan_hash: str = F,
    reference: str = "fabric-job://approved/pipeline",
) -> ApprovedPipelineEvidenceReport:
    return ApprovedPipelineEvidenceReport(
        check_id="fabric.pipeline",
        dataset_id="health.patient",
        framework_pipeline_run_id=uuid4(),
        dataset_run_id=uuid4(),
        workspace_id=uuid4(),
        item_id=uuid4(),
        native_job_instance_id=uuid4(),
        root_activity_id=uuid4(),
        remote_status=remote,
        framework_status=framework,
        retryable=retryable,
        error_code=error_code,
        execution_plan_hash=plan_hash,
        evidence_references=(reference,),
    )


def _before(*, scd2: bool = False) -> BusinessPathStateObservation:
    return _observation(
        BusinessPathObservationPhase.BEFORE,
        target=A,
        count=1,
        progress=D,
        history=A if scd2 else None,
        one_current=True if scd2 else None,
    )


def _success_final(*, scd2: bool = False) -> BusinessPathStateObservation:
    return _observation(
        BusinessPathObservationPhase.AFTER_FINAL_ATTEMPT,
        target=B,
        count=2,
        progress=C,
        history=E if scd2 else None,
        one_current=True if scd2 else None,
    )


@pytest.mark.parametrize(
    ("gate", "kind"),
    (
        (BusinessPathGate.FULL_REPLACE, ReleaseReadinessGateKind.FULL_REPLACE),
        (BusinessPathGate.WATERMARK_SCD1, ReleaseReadinessGateKind.WATERMARK_SCD1),
        (BusinessPathGate.WATERMARK_SCD2, ReleaseReadinessGateKind.WATERMARK_SCD2),
    ),
)
def test_single_attempt_live_paths_require_completed_framework_success_and_expected_state(gate, kind):
    scenario = _scenario(gate)
    run = BusinessPathRunEvidence(
        scenario_hash=scenario.scenario_hash,
        before=_before(scd2=gate is BusinessPathGate.WATERMARK_SCD2),
        after_final_attempt=_success_final(
            scd2=gate is BusinessPathGate.WATERMARK_SCD2
        ),
        pipeline_reports=(_report(),),
    )

    proof = evaluate_business_path_evidence(scenario, run)

    assert proof.gate_id == gate.value
    assert proof.kind is kind
    assert proof.status is ReleaseReadinessStatus.PASS
    assert "fabric-job://approved/pipeline" in proof.evidence_references


def test_scd2_requires_expected_history_and_one_current_row_invariant():
    with pytest.raises(ValueError, match="expected history"):
        ApprovedBusinessPathScenario(
            gate_id=BusinessPathGate.WATERMARK_SCD2,
            dataset_id="health.patient",
            observer_extension="health.observer",
            extension_artifact_name="observer.whl",
            scenario_artifact_name="scd2.json",
            expected_success_target_sha256=B,
            expected_success_target_row_count=2,
            expected_success_progress_sha256=C,
        )

    scenario = _scenario(BusinessPathGate.WATERMARK_SCD2)
    bad_final = _observation(
        BusinessPathObservationPhase.AFTER_FINAL_ATTEMPT,
        target=B,
        count=2,
        progress=C,
        history=E,
        one_current=False,
    )
    with pytest.raises(ValueError, match="one-current-row"):
        evaluate_business_path_evidence(
            scenario,
            BusinessPathRunEvidence(
                scenario_hash=scenario.scenario_hash,
                before=_before(scd2=True),
                after_final_attempt=bad_final,
                pipeline_reports=(_report(),),
            ),
        )


def test_success_path_rejects_provider_or_framework_false_positive_and_noop_fixture():
    scenario = _scenario(BusinessPathGate.FULL_REPLACE)
    for report in (
        _report(remote=FabricJobStatus.FAILED, framework=DatasetStatus.SUCCEEDED),
        _report(remote=FabricJobStatus.COMPLETED, framework=DatasetStatus.FAILED),
    ):
        with pytest.raises(ValueError):
            evaluate_business_path_evidence(
                scenario,
                BusinessPathRunEvidence(
                    scenario_hash=scenario.scenario_hash,
                    before=_before(),
                    after_final_attempt=_success_final(),
                    pipeline_reports=(report,),
                ),
            )

    noop_scenario = ApprovedBusinessPathScenario(
        gate_id=BusinessPathGate.FULL_REPLACE,
        dataset_id="health.patient",
        observer_extension="health.observer",
        extension_artifact_name="observer.whl",
        scenario_artifact_name="full.json",
        expected_success_target_sha256=A,
        expected_success_target_row_count=1,
        expected_success_progress_sha256=D,
    )
    with pytest.raises(ValueError, match="did not change semantic state"):
        evaluate_business_path_evidence(
            noop_scenario,
            BusinessPathRunEvidence(
                scenario_hash=noop_scenario.scenario_hash,
                before=_before(),
                after_final_attempt=_observation(
                    BusinessPathObservationPhase.AFTER_FINAL_ATTEMPT,
                    target=A,
                    count=1,
                    progress=D,
                ),
                pipeline_reports=(_report(),),
            ),
        )


def test_retry_idempotency_requires_failed_unchanged_attempt_then_success():
    scenario = _scenario(
        BusinessPathGate.RETRY_IDEMPOTENCY,
        expected_failure_error_code="TRANSIENT_SOURCE_FAILURE",
    )
    first_state = _observation(
        BusinessPathObservationPhase.AFTER_FIRST_ATTEMPT,
        target=A,
        count=1,
        progress=D,
    )
    run = BusinessPathRunEvidence(
        scenario_hash=scenario.scenario_hash,
        before=_before(),
        after_first_attempt=first_state,
        after_final_attempt=_success_final(),
        pipeline_reports=(
            _report(
                remote=FabricJobStatus.FAILED,
                framework=DatasetStatus.FAILED,
                retryable=True,
                error_code="TRANSIENT_SOURCE_FAILURE",
                reference="fabric-job://retry/attempt-1",
            ),
            _report(reference="fabric-job://retry/attempt-2"),
        ),
    )

    proof = evaluate_business_path_evidence(scenario, run)

    assert proof.status is ReleaseReadinessStatus.PASS
    assert proof.kind is ReleaseReadinessGateKind.RETRY_IDEMPOTENCY
    assert "fabric-job://retry/attempt-1" in proof.evidence_references
    assert "fabric-job://retry/attempt-2" in proof.evidence_references


def test_retry_rejects_unsafe_progress_or_target_change_after_failed_attempt():
    scenario = _scenario(
        BusinessPathGate.RETRY_IDEMPOTENCY,
        expected_failure_error_code="TRANSIENT_SOURCE_FAILURE",
    )
    changed_after_failure = _observation(
        BusinessPathObservationPhase.AFTER_FIRST_ATTEMPT,
        target=A,
        count=1,
        progress=C,
    )
    with pytest.raises(ValueError, match="failed retry attempt changed"):
        evaluate_business_path_evidence(
            scenario,
            BusinessPathRunEvidence(
                scenario_hash=scenario.scenario_hash,
                before=_before(),
                after_first_attempt=changed_after_failure,
                after_final_attempt=_success_final(),
                pipeline_reports=(
                    _report(
                        remote=FabricJobStatus.FAILED,
                        framework=DatasetStatus.FAILED,
                        retryable=True,
                        error_code="TRANSIENT_SOURCE_FAILURE",
                    ),
                    _report(),
                ),
            ),
        )


def test_retry_rejects_nonretryable_wrong_error_and_different_execution_plan():
    scenario = _scenario(
        BusinessPathGate.RETRY_IDEMPOTENCY,
        expected_failure_error_code="TRANSIENT_SOURCE_FAILURE",
    )
    first_state = _observation(
        BusinessPathObservationPhase.AFTER_FIRST_ATTEMPT,
        target=A,
        count=1,
        progress=D,
    )

    with pytest.raises(ValueError, match="explicitly retryable"):
        evaluate_business_path_evidence(
            scenario,
            BusinessPathRunEvidence(
                scenario_hash=scenario.scenario_hash,
                before=_before(),
                after_first_attempt=first_state,
                after_final_attempt=_success_final(),
                pipeline_reports=(
                    _report(
                        remote=FabricJobStatus.FAILED,
                        framework=DatasetStatus.FAILED,
                        retryable=False,
                        error_code="TRANSIENT_SOURCE_FAILURE",
                    ),
                    _report(),
                ),
            ),
        )

    with pytest.raises(ValueError, match="same execution plan hash"):
        BusinessPathRunEvidence(
            scenario_hash=scenario.scenario_hash,
            before=_before(),
            after_first_attempt=first_state,
            after_final_attempt=_success_final(),
            pipeline_reports=(
                _report(
                    remote=FabricJobStatus.FAILED,
                    framework=DatasetStatus.FAILED,
                    retryable=True,
                    error_code="TRANSIENT_SOURCE_FAILURE",
                    plan_hash=F,
                ),
                _report(plan_hash=E),
            ),
        )


def test_reconciliation_fail_closed_requires_provider_completed_framework_failed_and_unchanged_state():
    scenario = _scenario(
        BusinessPathGate.RECONCILIATION_FAIL_CLOSED,
        expected_failure_error_code="RECONCILIATION_FAILED",
    )
    unchanged_final = _observation(
        BusinessPathObservationPhase.AFTER_FINAL_ATTEMPT,
        target=A,
        count=1,
        progress=D,
    )
    proof = evaluate_business_path_evidence(
        scenario,
        BusinessPathRunEvidence(
            scenario_hash=scenario.scenario_hash,
            before=_before(),
            after_final_attempt=unchanged_final,
            pipeline_reports=(
                _report(
                    remote=FabricJobStatus.COMPLETED,
                    framework=DatasetStatus.FAILED,
                    error_code="RECONCILIATION_FAILED",
                    reference="fabric-job://reconciliation/completed-but-rejected",
                ),
            ),
        ),
    )

    assert proof.status is ReleaseReadinessStatus.PASS
    assert proof.kind is ReleaseReadinessGateKind.RECONCILIATION_FAIL_CLOSED


def test_reconciliation_rejects_provider_failure_framework_success_or_state_advance():
    scenario = _scenario(
        BusinessPathGate.RECONCILIATION_FAIL_CLOSED,
        expected_failure_error_code="RECONCILIATION_FAILED",
    )
    unchanged = _observation(
        BusinessPathObservationPhase.AFTER_FINAL_ATTEMPT,
        target=A,
        count=1,
        progress=D,
    )
    for report in (
        _report(
            remote=FabricJobStatus.FAILED,
            framework=DatasetStatus.FAILED,
            error_code="RECONCILIATION_FAILED",
        ),
        _report(
            remote=FabricJobStatus.COMPLETED,
            framework=DatasetStatus.SUCCEEDED,
            error_code="RECONCILIATION_FAILED",
        ),
    ):
        with pytest.raises(ValueError):
            evaluate_business_path_evidence(
                scenario,
                BusinessPathRunEvidence(
                    scenario_hash=scenario.scenario_hash,
                    before=_before(),
                    after_final_attempt=unchanged,
                    pipeline_reports=(report,),
                ),
            )

    changed = _observation(
        BusinessPathObservationPhase.AFTER_FINAL_ATTEMPT,
        target=B,
        count=2,
        progress=C,
    )
    with pytest.raises(ValueError, match="failed reconciliation attempt changed"):
        evaluate_business_path_evidence(
            scenario,
            BusinessPathRunEvidence(
                scenario_hash=scenario.scenario_hash,
                before=_before(),
                after_final_attempt=changed,
                pipeline_reports=(
                    _report(
                        remote=FabricJobStatus.COMPLETED,
                        framework=DatasetStatus.FAILED,
                        error_code="RECONCILIATION_FAILED",
                    ),
                ),
            ),
        )


def test_scenario_hash_and_dataset_membership_are_exact():
    scenario = _scenario(BusinessPathGate.FULL_REPLACE)
    with pytest.raises(ValueError, match="scenario hash mismatch"):
        evaluate_business_path_evidence(
            scenario,
            BusinessPathRunEvidence(
                scenario_hash=F,
                before=_before(),
                after_final_attempt=_success_final(),
                pipeline_reports=(_report(),),
            ),
        )

    wrong_dataset = _report().model_copy(update={"dataset_id": "other.dataset"})
    with pytest.raises(ValueError, match="one dataset_id"):
        BusinessPathRunEvidence(
            scenario_hash=scenario.scenario_hash,
            before=_before(),
            after_final_attempt=_success_final(),
            pipeline_reports=(wrong_dataset,),
        )


def test_scenario_file_and_observer_extension_must_be_fingerprinted_by_exact_release(tmp_path):
    scenario = _scenario(BusinessPathGate.FULL_REPLACE)
    path = tmp_path / "full.replace.json"
    raw = json.dumps(scenario.model_dump(mode="json"), sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()

    bundle = ReleaseBundleIdentity(
        domain_release_version="0.4.0-dev",
        domain_git_sha="1" * 40,
        framework_version="0.4.0",
        config_bundle_hash="2" * 64,
        config_schema_version=1,
        control_plane_schema_version=1,
        fabric_item_manifest_version="v1",
        build_id="business-path-test",
    )
    manifest = ReleaseManifest(
        domain="customer",
        bundle=bundle,
        generated_at=NOW,
        artifact_sha256={
            scenario.scenario_artifact_name: digest,
            scenario.extension_artifact_name: "3" * 64,
        },
    )

    loaded = load_approved_business_path_scenario(path, release_manifest=manifest)
    assert loaded == scenario

    wrong = manifest.model_copy(
        update={
            "artifact_sha256": {
                scenario.scenario_artifact_name: "4" * 64,
                scenario.extension_artifact_name: "3" * 64,
            }
        }
    )
    with pytest.raises(ValueError, match="scenario artifact SHA256 mismatch"):
        load_approved_business_path_scenario(path, release_manifest=wrong)

    missing_extension = manifest.model_copy(
        update={"artifact_sha256": {scenario.scenario_artifact_name: digest}}
    )
    with pytest.raises(ValueError, match="observer extension artifact"):
        load_approved_business_path_scenario(path, release_manifest=missing_extension)


def test_pipeline_report_and_observation_reject_credential_like_retained_text():
    with pytest.raises(ValueError, match="credential material"):
        _report(reference="https://example.invalid/run?access_token=secret")

    with pytest.raises(ValueError, match="credential material"):
        _observation(
            BusinessPathObservationPhase.BEFORE,
            target=A,
            count=1,
            progress=D,
            reference="authorization: bearer redacted",
        )
