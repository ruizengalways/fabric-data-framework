from __future__ import annotations

import pytest

from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceSpec,
    run_integration_evidence,
    validate_integration_evidence_manifest,
)
from fabric_data_framework.evidence.integration_runner import (
    ApprovedIntegrationRunnerConfig,
    build_approved_integration_run_plan,
)


FRAMEWORK_SHA = "a" * 64
INPUTS_SHA = "b" * 64


def _candidate_spec() -> IntegrationEvidenceSpec:
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="framework-certification",
        framework_version="0.4.0",
        framework_artifact_sha256=FRAMEWORK_SHA,
        integration_inputs_hash=INPUTS_SHA,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="delta.reference",
                kind=IntegrationEvidenceCheckKind.DELTA_CDF_PROVIDER,
                required=False,
            ),
        ),
    )


def _runner_config() -> ApprovedIntegrationRunnerConfig:
    return ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="framework-certification",
        framework_version="0.4.0",
        framework_artifact_sha256=FRAMEWORK_SHA,
        integration_inputs_hash=INPUTS_SHA,
    )


def test_candidate_runner_requires_exact_framework_and_integration_input_identities():
    spec = _candidate_spec()
    config = _runner_config()
    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ={},
        selected_check_ids=("delta.reference",),
        allow_mutating_checks=True,
    )

    assert plan.framework_artifact_sha256 == FRAMEWORK_SHA
    assert plan.integration_inputs_hash == INPUTS_SHA

    for changed, message in (
        ({"framework_artifact_sha256": "c" * 64}, "framework artifact"),
        ({"integration_inputs_hash": "d" * 64}, "integration inputs"),
    ):
        bad = config.model_copy(update=changed)
        with pytest.raises(ValueError, match=message):
            build_approved_integration_run_plan(
                bad,
                spec,
                environ={},
                selected_check_ids=("delta.reference",),
                allow_mutating_checks=True,
            )


def test_manifest_hash_and_validation_include_both_explicit_identities():
    spec = _candidate_spec()
    manifest = run_integration_evidence(spec, runners={})

    assert manifest.framework_artifact_sha256 == FRAMEWORK_SHA
    assert manifest.integration_inputs_hash == INPUTS_SHA
    validate_integration_evidence_manifest(spec, manifest)

    changed_artifact = manifest.model_copy(update={"framework_artifact_sha256": "c" * 64})
    with pytest.raises(ValueError, match="framework artifact SHA256 mismatch"):
        validate_integration_evidence_manifest(spec, changed_artifact)

    changed_inputs = manifest.model_copy(update={"integration_inputs_hash": "d" * 64})
    with pytest.raises(ValueError, match="integration inputs hash mismatch"):
        validate_integration_evidence_manifest(spec, changed_inputs)


def test_legacy_single_hash_fields_are_not_part_of_current_models():
    spec_fields = IntegrationEvidenceSpec.model_fields
    runner_fields = ApprovedIntegrationRunnerConfig.model_fields

    assert "release_hash" not in spec_fields
    assert "domain_release_hash" not in spec_fields
    assert "release_hash" not in runner_fields
    assert "domain_release_hash" not in runner_fields
    assert "framework_artifact_sha256" in spec_fields
    assert "integration_inputs_hash" in spec_fields
    assert "framework_artifact_sha256" in runner_fields
    assert "integration_inputs_hash" in runner_fields
