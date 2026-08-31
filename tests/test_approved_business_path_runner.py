from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

import fabric_data_framework.evidence.approved_business_path_runner as runner_module
from fabric_data_framework.adapters.fabric.rest import FabricJobStatus
from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.deployment.contracts import ReleaseBundleIdentity, ReleaseManifest
from fabric_data_framework.evidence.approved_business_path_runner import (
    execute_approved_business_path,
)
from fabric_data_framework.evidence.approved_pipeline_runner import ApprovedPipelineEvidenceReport
from fabric_data_framework.evidence.business_path_driver import (
    ApprovedBusinessPathDriverConfig,
    BusinessPathDriverPhase,
    BusinessPathDriverReceipt,
)
from fabric_data_framework.evidence.business_path_evidence import (
    ApprovedBusinessPathScenario,
    BusinessPathGate,
    BusinessPathObservationPhase,
    BusinessPathStateObservation,
)
from fabric_data_framework.evidence.integration_runner import ApprovedIntegrationRunnerConfig
from fabric_data_framework.extensions import ExtensionKind, ExtensionRegistry
from fabric_data_framework.metadata.config import DatasetStatus


NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)
CANDIDATE_SHA = "1" * 40
WHEEL_SHA = "2" * 64
BEFORE = "a" * 64
FINAL = "b" * 64
PROGRESS_BEFORE = "c" * 64
PROGRESS_FINAL = "d" * 64
HISTORY_FINAL = "e" * 64
PLAN_HASH = "f" * 64
DATASET_ID = "health.patient"


def _release() -> ReleaseManifest:
    return ReleaseManifest(
        domain="customer",
        bundle=ReleaseBundleIdentity(
            domain_release_version="0.4.0-dev",
            domain_git_sha="3" * 40,
            framework_version="0.4.0",
            config_bundle_hash="4" * 64,
            config_schema_version=1,
            control_plane_schema_version=1,
            fabric_item_manifest_version="v1",
            build_id="business-path-runner-test",
        ),
        generated_at=NOW,
        artifact_sha256={
            "observer.whl": "5" * 64,
            "driver.whl": "6" * 64,
            "scenario.json": "7" * 64,
            "driver.json": "8" * 64,
        },
    )


def _runner_config(release: ReleaseManifest) -> ApprovedIntegrationRunnerConfig:
    return ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=release.bundle.release_hash,
    )


def _scenario(gate: BusinessPathGate) -> ApprovedBusinessPathScenario:
    return ApprovedBusinessPathScenario(
        gate_id=gate,
        dataset_id=DATASET_ID,
        observer_extension="health.observer",
        extension_artifact_name="observer.whl",
        scenario_artifact_name="scenario.json",
        expected_success_target_sha256=FINAL,
        expected_success_target_row_count=2,
        expected_success_progress_sha256=PROGRESS_FINAL,
        expected_success_history_sha256=(
            HISTORY_FINAL if gate is BusinessPathGate.WATERMARK_SCD2 else None
        ),
        expected_failure_error_code=(
            "TRANSIENT_SOURCE_FAILURE"
            if gate is BusinessPathGate.RETRY_IDEMPOTENCY
            else "RECONCILIATION_FAILED"
            if gate is BusinessPathGate.RECONCILIATION_FAIL_CLOSED
            else None
        ),
    )


def _driver_config(scenario: ApprovedBusinessPathScenario) -> ApprovedBusinessPathDriverConfig:
    return ApprovedBusinessPathDriverConfig(
        scenario_hash=scenario.scenario_hash,
        driver_extension="health.driver",
        extension_artifact_name="driver.whl",
        driver_config_artifact_name="driver.json",
    )


def _report(
    *,
    remote: FabricJobStatus = FabricJobStatus.COMPLETED,
    framework: DatasetStatus = DatasetStatus.SUCCEEDED,
    retryable: bool | None = None,
    error_code: str | None = None,
) -> ApprovedPipelineEvidenceReport:
    return ApprovedPipelineEvidenceReport(
        check_id="fabric.pipeline",
        dataset_id=DATASET_ID,
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
        execution_plan_hash=PLAN_HASH,
        evidence_references=("fabric-job://business-path",),
    )


def _registry(
    scenario: ApprovedBusinessPathScenario,
    *,
    driver_calls: list[BusinessPathDriverPhase],
    fail_cleanup: bool = False,
) -> ExtensionRegistry:
    registry = ExtensionRegistry()

    def driver(request):
        driver_calls.append(request.phase)
        if fail_cleanup and request.phase is BusinessPathDriverPhase.CLEANUP:
            raise RuntimeError("cleanup failed")
        return BusinessPathDriverReceipt(
            gate_id=request.gate_id,
            dataset_id=request.dataset_id,
            scenario_hash=request.scenario_hash,
            phase=request.phase,
            evidence_references=(f"fabric-fixture://{request.phase.value.lower()}",),
        )

    def observer(request):
        if request.phase is BusinessPathObservationPhase.BEFORE:
            target = BEFORE
            count = 1
            progress = PROGRESS_BEFORE
            history = BEFORE if scenario.gate_id is BusinessPathGate.WATERMARK_SCD2 else None
            one_current = True if scenario.gate_id is BusinessPathGate.WATERMARK_SCD2 else None
        elif (
            request.phase is BusinessPathObservationPhase.AFTER_FIRST_ATTEMPT
            or scenario.gate_id is BusinessPathGate.RECONCILIATION_FAIL_CLOSED
        ):
            target = BEFORE
            count = 1
            progress = PROGRESS_BEFORE
            history = None
            one_current = None
        else:
            target = FINAL
            count = 2
            progress = PROGRESS_FINAL
            history = (
                HISTORY_FINAL
                if scenario.gate_id is BusinessPathGate.WATERMARK_SCD2
                else None
            )
            one_current = True if scenario.gate_id is BusinessPathGate.WATERMARK_SCD2 else None
        return BusinessPathStateObservation(
            dataset_id=request.dataset_id,
            phase=request.phase,
            target_semantic_sha256=target,
            target_row_count=count,
            progress_semantic_sha256=progress,
            history_semantic_sha256=history,
            one_current_row_per_business_key=one_current,
            evidence_references=(f"fabric-state://{request.phase.value.lower()}",),
        )

    registry.register(ExtensionKind.BUSINESS_PATH_DRIVER, "health.driver", driver)
    registry.register(ExtensionKind.BUSINESS_PATH_OBSERVER, "health.observer", observer)
    return registry


def _execute(
    monkeypatch,
    gate: BusinessPathGate,
    reports: list[ApprovedPipelineEvidenceReport],
    *,
    allow_pipeline_execution: bool = True,
    allow_scenario_mutation: bool = True,
    fail_cleanup: bool = False,
):
    release = _release()
    scenario = _scenario(gate)
    driver_calls: list[BusinessPathDriverPhase] = []
    queue = list(reports)

    def fake_pipeline_attempt(**kwargs):
        assert kwargs["configs"][0].dataset_id == DATASET_ID
        return queue.pop(0)

    monkeypatch.setattr(runner_module, "_pipeline_attempt", fake_pipeline_attempt)
    result = execute_approved_business_path(
        runner_config=_runner_config(release),
        integration_spec=None,  # consumed only by the monkeypatched approved Pipeline boundary
        prerequisite_manifest=None,
        release_manifest=release,
        configs=(item for item in (SimpleNamespace(dataset_id=DATASET_ID),)),
        scenario=scenario,
        driver_config=_driver_config(scenario),
        candidate_git_sha=CANDIDATE_SHA,
        artifact_sha256=WHEEL_SHA,
        pipeline_check_id="fabric.pipeline",
        environ={},
        evidence_references=("artifact:business-path",),
        allow_pipeline_execution=allow_pipeline_execution,
        allow_scenario_mutation=allow_scenario_mutation,
        registry=_registry(
            scenario,
            driver_calls=driver_calls,
            fail_cleanup=fail_cleanup,
        ),
    )
    assert not queue
    return result, driver_calls


@pytest.mark.parametrize(
    "gate",
    (
        BusinessPathGate.FULL_REPLACE,
        BusinessPathGate.WATERMARK_SCD1,
        BusinessPathGate.WATERMARK_SCD2,
    ),
)
def test_single_attempt_paths_publish_one_exact_partial_proof_and_cleanup(monkeypatch, gate):
    result, calls = _execute(monkeypatch, gate, [_report()])

    assert result.proof.gate_id == gate.value
    assert result.partial_proof_bundle.candidate_git_sha == CANDIDATE_SHA
    assert result.partial_proof_bundle.artifact_sha256 == WHEEL_SHA
    assert len(result.partial_proof_bundle.results) == 1
    assert calls == [
        BusinessPathDriverPhase.PREPARE_BASELINE,
        BusinessPathDriverPhase.PREPARE_ATTEMPT_1,
        BusinessPathDriverPhase.CLEANUP,
    ]
    assert "fabric-fixture://cleanup" in result.proof.evidence_references


def test_retry_requires_two_real_attempt_reports_and_intermediate_observation(monkeypatch):
    result, calls = _execute(
        monkeypatch,
        BusinessPathGate.RETRY_IDEMPOTENCY,
        [
            _report(
                remote=FabricJobStatus.FAILED,
                framework=DatasetStatus.FAILED,
                retryable=True,
                error_code="TRANSIENT_SOURCE_FAILURE",
            ),
            _report(),
        ],
    )

    assert len(result.run_evidence.pipeline_reports) == 2
    assert result.run_evidence.after_first_attempt is not None
    assert calls == [
        BusinessPathDriverPhase.PREPARE_BASELINE,
        BusinessPathDriverPhase.PREPARE_ATTEMPT_1,
        BusinessPathDriverPhase.PREPARE_ATTEMPT_2,
        BusinessPathDriverPhase.CLEANUP,
    ]


def test_reconciliation_accepts_completed_provider_but_failed_framework_only_when_state_unchanged(monkeypatch):
    result, _ = _execute(
        monkeypatch,
        BusinessPathGate.RECONCILIATION_FAIL_CLOSED,
        [
            _report(
                remote=FabricJobStatus.COMPLETED,
                framework=DatasetStatus.FAILED,
                error_code="RECONCILIATION_FAILED",
            )
        ],
    )

    report = result.run_evidence.pipeline_reports[0]
    assert report.remote_status is FabricJobStatus.COMPLETED
    assert report.framework_status is DatasetStatus.FAILED
    assert result.run_evidence.before.semantic_state_identity == (
        result.run_evidence.after_final_attempt.semantic_state_identity
    )


def test_explicit_authorization_blocks_before_driver_or_pipeline(monkeypatch):
    release = _release()
    scenario = _scenario(BusinessPathGate.FULL_REPLACE)
    calls: list[BusinessPathDriverPhase] = []

    def must_not_run(**kwargs):
        raise AssertionError("Pipeline must not run before authorization")

    monkeypatch.setattr(runner_module, "_pipeline_attempt", must_not_run)
    for pipeline_allowed, mutation_allowed, expected in (
        (False, True, "Pipeline execution"),
        (True, False, "scenario mutation"),
    ):
        calls.clear()
        with pytest.raises(ValueError, match=expected):
            execute_approved_business_path(
                runner_config=_runner_config(release),
                integration_spec=None,
                prerequisite_manifest=None,
                release_manifest=release,
                configs=(SimpleNamespace(dataset_id=DATASET_ID),),
                scenario=scenario,
                driver_config=_driver_config(scenario),
                candidate_git_sha=CANDIDATE_SHA,
                artifact_sha256=WHEEL_SHA,
                pipeline_check_id="fabric.pipeline",
                environ={},
                evidence_references=("artifact:business-path",),
                allow_pipeline_execution=pipeline_allowed,
                allow_scenario_mutation=mutation_allowed,
                registry=_registry(scenario, driver_calls=calls),
            )
        assert calls == []


def test_cleanup_failure_prevents_returning_pass_artifact(monkeypatch):
    with pytest.raises(RuntimeError, match="cleanup failed"):
        _execute(
            monkeypatch,
            BusinessPathGate.FULL_REPLACE,
            [_report()],
            fail_cleanup=True,
        )


def test_runner_rejects_unfingerprinted_driver_or_observer_before_extensions_run(monkeypatch):
    scenario = _scenario(BusinessPathGate.FULL_REPLACE)
    driver_config = _driver_config(scenario)
    calls: list[BusinessPathDriverPhase] = []
    registry = _registry(scenario, driver_calls=calls)
    base = _release()

    for missing_name, expected in (
        (scenario.extension_artifact_name, "observer extension"),
        (driver_config.extension_artifact_name, "driver extension"),
    ):
        artifacts = dict(base.artifact_sha256)
        artifacts.pop(missing_name)
        release = base.model_copy(update={"artifact_sha256": artifacts})
        config = _runner_config(release)
        with pytest.raises(ValueError, match=expected):
            execute_approved_business_path(
                runner_config=config,
                integration_spec=None,
                prerequisite_manifest=None,
                release_manifest=release,
                configs=(SimpleNamespace(dataset_id=DATASET_ID),),
                scenario=scenario,
                driver_config=driver_config,
                candidate_git_sha=CANDIDATE_SHA,
                artifact_sha256=WHEEL_SHA,
                pipeline_check_id="fabric.pipeline",
                environ={},
                evidence_references=("artifact:business-path",),
                allow_pipeline_execution=True,
                allow_scenario_mutation=True,
                registry=registry,
            )
        assert calls == []
