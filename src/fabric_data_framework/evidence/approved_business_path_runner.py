"""Approved exact-release runner for representative live business-path readiness gates.

The runner reuses the existing approved Fabric Pipeline runner for every attempt. It
separates mutating fixture preparation (driver extension), read-only semantic state
observation (observer extension), provider/framework execution evidence, and final
framework-owned gate evaluation. Neither extension can return a readiness PASS value.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.deployment.contracts import ReleaseManifest
from fabric_data_framework.evidence.approved_pipeline_runner import (
    ApprovedPipelineEvidenceReport,
    execute_approved_pipeline,
)
from fabric_data_framework.evidence.business_path_driver import (
    ApprovedBusinessPathDriverConfig,
    BusinessPathDriverPhase,
    BusinessPathDriverReceipt,
    BusinessPathDriverRequest,
    validate_driver_receipt,
)
from fabric_data_framework.evidence.business_path_evidence import (
    ApprovedBusinessPathScenario,
    BusinessPathGate,
    BusinessPathObservationPhase,
    BusinessPathObservationRequest,
    BusinessPathRunEvidence,
    BusinessPathStateObservation,
    evaluate_business_path_evidence,
)
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
)
from fabric_data_framework.evidence.integration_runner import ApprovedIntegrationRunnerConfig
from fabric_data_framework.evidence.release_readiness import (
    ReleaseReadinessProofBundle,
    ReleaseReadinessProofResult,
)
from fabric_data_framework.evidence.safety import assert_safe_retained_text
from fabric_data_framework.extensions import ExtensionKind, ExtensionRegistry
from fabric_data_framework.metadata.config import DatasetConfig


class ApprovedBusinessPathExecutionReport(FrozenModel):
    """Credential-free retained report for one evaluated representative live path."""

    framework_version: str = Field(min_length=1, max_length=64)
    candidate_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    domain: str = Field(min_length=1, max_length=128)
    gate_id: BusinessPathGate
    dataset_id: str = Field(min_length=1, max_length=256)
    scenario_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    driver_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    driver_receipts: tuple[BusinessPathDriverReceipt, ...]
    run_evidence: BusinessPathRunEvidence
    proof: ReleaseReadinessProofResult

    @model_validator(mode="after")
    def validate_report(self) -> "ApprovedBusinessPathExecutionReport":
        if self.proof.gate_id != self.gate_id.value:
            raise ValueError("business path execution report proof gate mismatch")
        if self.run_evidence.before.dataset_id != self.dataset_id:
            raise ValueError("business path execution report dataset mismatch")
        if self.run_evidence.scenario_hash != self.scenario_hash:
            raise ValueError("business path execution report scenario hash mismatch")
        assert_safe_retained_text(self.model_dump_json(), "business path execution report")
        return self

    @property
    def partial_proof_bundle(self) -> ReleaseReadinessProofBundle:
        return ReleaseReadinessProofBundle(
            framework_version=self.framework_version,
            candidate_git_sha=self.candidate_git_sha,
            artifact_sha256=self.artifact_sha256,
            results=(self.proof,),
        )


def _registry_with_business_extensions(
    registry: ExtensionRegistry | None,
    *,
    scenario: ApprovedBusinessPathScenario,
    driver_config: ApprovedBusinessPathDriverConfig,
) -> ExtensionRegistry:
    resolved = registry or ExtensionRegistry()
    if registry is None:
        resolved.discover(ExtensionKind.BUSINESS_PATH_DRIVER)
        resolved.discover(ExtensionKind.BUSINESS_PATH_OBSERVER)
    resolved.factory(ExtensionKind.BUSINESS_PATH_DRIVER, driver_config.driver_extension)
    resolved.factory(ExtensionKind.BUSINESS_PATH_OBSERVER, scenario.observer_extension)
    return resolved


def _drive(
    registry: ExtensionRegistry,
    *,
    scenario: ApprovedBusinessPathScenario,
    driver_config: ApprovedBusinessPathDriverConfig,
    phase: BusinessPathDriverPhase,
) -> BusinessPathDriverReceipt:
    request = BusinessPathDriverRequest(
        gate_id=scenario.gate_id,
        dataset_id=scenario.dataset_id,
        scenario_hash=scenario.scenario_hash,
        phase=phase,
        parameters=driver_config.parameters,
    )
    driver = registry.factory(
        ExtensionKind.BUSINESS_PATH_DRIVER,
        driver_config.driver_extension,
    )
    receipt = driver(request)
    if not isinstance(receipt, BusinessPathDriverReceipt):
        raise TypeError("business path driver must return BusinessPathDriverReceipt")
    validate_driver_receipt(request, receipt)
    return receipt


def _observe(
    registry: ExtensionRegistry,
    *,
    scenario: ApprovedBusinessPathScenario,
    phase: BusinessPathObservationPhase,
    dataset_run_id: str | None,
) -> BusinessPathStateObservation:
    request = BusinessPathObservationRequest(
        gate_id=scenario.gate_id,
        dataset_id=scenario.dataset_id,
        phase=phase,
        dataset_run_id=dataset_run_id,
        parameters=scenario.parameters,
    )
    observer = registry.factory(
        ExtensionKind.BUSINESS_PATH_OBSERVER,
        scenario.observer_extension,
    )
    observation = observer(request)
    if not isinstance(observation, BusinessPathStateObservation):
        raise TypeError("business path observer must return BusinessPathStateObservation")
    if observation.dataset_id != request.dataset_id:
        raise ValueError("business path observer returned wrong dataset_id")
    if observation.phase is not request.phase:
        raise ValueError("business path observer returned wrong phase")
    return observation


def _pipeline_attempt(
    *,
    runner_config: ApprovedIntegrationRunnerConfig,
    integration_spec: IntegrationEvidenceSpec,
    prerequisite_manifest: IntegrationEvidenceManifest,
    release_manifest: ReleaseManifest,
    configs: tuple[DatasetConfig, ...],
    pipeline_check_id: str,
    dataset_id: str,
    environ: Mapping[str, str],
    evidence_references: tuple[str, ...],
    allow_pipeline_execution: bool,
) -> ApprovedPipelineEvidenceReport:
    execution = execute_approved_pipeline(
        config=runner_config,
        spec=integration_spec,
        prerequisite_manifest=prerequisite_manifest,
        release_manifest=release_manifest,
        configs=configs,
        check_id=pipeline_check_id,
        dataset_id=dataset_id,
        environ=environ,
        evidence_references=evidence_references,
        allow_pipeline_execution=allow_pipeline_execution,
    )
    if execution.report is None:
        raise ValueError(
            "approved business path Pipeline attempt did not produce provider/framework report"
        )
    return execution.report


def _with_driver_references(
    proof: ReleaseReadinessProofResult,
    receipts: Iterable[BusinessPathDriverReceipt],
) -> ReleaseReadinessProofResult:
    refs = list(proof.evidence_references)
    for receipt in receipts:
        refs.extend(receipt.evidence_references)
    return proof.model_copy(update={"evidence_references": tuple(dict.fromkeys(refs))})


def execute_approved_business_path(
    *,
    runner_config: ApprovedIntegrationRunnerConfig,
    integration_spec: IntegrationEvidenceSpec,
    prerequisite_manifest: IntegrationEvidenceManifest,
    release_manifest: ReleaseManifest,
    configs: Iterable[DatasetConfig],
    scenario: ApprovedBusinessPathScenario,
    driver_config: ApprovedBusinessPathDriverConfig,
    candidate_git_sha: str,
    artifact_sha256: str,
    pipeline_check_id: str,
    environ: Mapping[str, str],
    evidence_references: Iterable[str],
    allow_pipeline_execution: bool,
    allow_scenario_mutation: bool,
    registry: ExtensionRegistry | None = None,
) -> ApprovedBusinessPathExecutionReport:
    """Execute and evaluate one exact-release representative live business path."""

    if release_manifest.bundle.framework_version != runner_config.framework_version:
        raise ValueError("business path release/framework version mismatch")
    if release_manifest.bundle.release_hash != runner_config.release_hash:
        raise ValueError("business path release hash mismatch")
    if scenario.dataset_id not in {item.dataset_id for item in configs}:
        raise ValueError("business path dataset is absent from exact release config bundle")
    if driver_config.scenario_hash != scenario.scenario_hash:
        raise ValueError("business path driver/scenario hash mismatch")
    if not allow_scenario_mutation:
        raise ValueError("business path scenario mutation is not explicitly authorized")
    if not allow_pipeline_execution:
        raise ValueError("business path Pipeline execution is not explicitly authorized")

    references = tuple(evidence_references)
    if not references:
        raise ValueError("business path execution requires retained evidence references")
    for index, reference in enumerate(references):
        assert_safe_retained_text(reference, f"business path evidence_references[{index}]")

    config_tuple = tuple(configs)
    extension_registry = _registry_with_business_extensions(
        registry,
        scenario=scenario,
        driver_config=driver_config,
    )

    driver_receipts: list[BusinessPathDriverReceipt] = []
    pipeline_reports: list[ApprovedPipelineEvidenceReport] = []
    first_observation: BusinessPathStateObservation | None = None
    proof: ReleaseReadinessProofResult | None = None
    before: BusinessPathStateObservation | None = None
    final: BusinessPathStateObservation | None = None

    try:
        driver_receipts.append(
            _drive(
                extension_registry,
                scenario=scenario,
                driver_config=driver_config,
                phase=BusinessPathDriverPhase.PREPARE_BASELINE,
            )
        )
        before = _observe(
            extension_registry,
            scenario=scenario,
            phase=BusinessPathObservationPhase.BEFORE,
            dataset_run_id=None,
        )

        driver_receipts.append(
            _drive(
                extension_registry,
                scenario=scenario,
                driver_config=driver_config,
                phase=BusinessPathDriverPhase.PREPARE_ATTEMPT_1,
            )
        )
        first_report = _pipeline_attempt(
            runner_config=runner_config,
            integration_spec=integration_spec,
            prerequisite_manifest=prerequisite_manifest,
            release_manifest=release_manifest,
            configs=config_tuple,
            pipeline_check_id=pipeline_check_id,
            dataset_id=scenario.dataset_id,
            environ=environ,
            evidence_references=references,
            allow_pipeline_execution=allow_pipeline_execution,
        )
        pipeline_reports.append(first_report)

        if scenario.gate_id is BusinessPathGate.RETRY_IDEMPOTENCY:
            first_observation = _observe(
                extension_registry,
                scenario=scenario,
                phase=BusinessPathObservationPhase.AFTER_FIRST_ATTEMPT,
                dataset_run_id=str(first_report.dataset_run_id),
            )
            driver_receipts.append(
                _drive(
                    extension_registry,
                    scenario=scenario,
                    driver_config=driver_config,
                    phase=BusinessPathDriverPhase.PREPARE_ATTEMPT_2,
                )
            )
            final_report = _pipeline_attempt(
                runner_config=runner_config,
                integration_spec=integration_spec,
                prerequisite_manifest=prerequisite_manifest,
                release_manifest=release_manifest,
                configs=config_tuple,
                pipeline_check_id=pipeline_check_id,
                dataset_id=scenario.dataset_id,
                environ=environ,
                evidence_references=references,
                allow_pipeline_execution=allow_pipeline_execution,
            )
            pipeline_reports.append(final_report)
        else:
            final_report = first_report

        final = _observe(
            extension_registry,
            scenario=scenario,
            phase=BusinessPathObservationPhase.AFTER_FINAL_ATTEMPT,
            dataset_run_id=str(final_report.dataset_run_id),
        )
        run_evidence = BusinessPathRunEvidence(
            scenario_hash=scenario.scenario_hash,
            before=before,
            after_first_attempt=first_observation,
            after_final_attempt=final,
            pipeline_reports=tuple(pipeline_reports),
        )
        proof = _with_driver_references(
            evaluate_business_path_evidence(scenario, run_evidence),
            driver_receipts,
        )
    finally:
        cleanup_receipt = _drive(
            extension_registry,
            scenario=scenario,
            driver_config=driver_config,
            phase=BusinessPathDriverPhase.CLEANUP,
        )
        driver_receipts.append(cleanup_receipt)

    if before is None or final is None or proof is None:
        raise RuntimeError("business path execution did not reach framework evaluation")

    # Cleanup is part of the retained path contract. Its evidence is attached only
    # after cleanup completed successfully, so a cleanup failure cannot publish PASS.
    proof = _with_driver_references(proof, driver_receipts)
    run_evidence = BusinessPathRunEvidence(
        scenario_hash=scenario.scenario_hash,
        before=before,
        after_first_attempt=first_observation,
        after_final_attempt=final,
        pipeline_reports=tuple(pipeline_reports),
    )
    return ApprovedBusinessPathExecutionReport(
        framework_version=runner_config.framework_version,
        candidate_git_sha=candidate_git_sha,
        artifact_sha256=artifact_sha256,
        domain=runner_config.domain,
        gate_id=scenario.gate_id,
        dataset_id=scenario.dataset_id,
        scenario_hash=scenario.scenario_hash,
        driver_config_hash=driver_config.driver_config_hash,
        driver_receipts=tuple(driver_receipts),
        run_evidence=run_evidence,
        proof=proof,
    )


def write_approved_business_path_execution_report(
    report: ApprovedBusinessPathExecutionReport,
    path: str | Path,
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


def write_business_path_partial_proof_bundle(
    report: ApprovedBusinessPathExecutionReport,
    path: str | Path,
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.partial_proof_bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")


__all__ = [
    "ApprovedBusinessPathExecutionReport",
    "execute_approved_business_path",
    "write_approved_business_path_execution_report",
    "write_business_path_partial_proof_bundle",
]
