from __future__ import annotations

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
DOMAIN_SHA = "b" * 64


def _candidate_spec() -> IntegrationEvidenceSpec:
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=FRAMEWORK_SHA,
        domain_release_hash=DOMAIN_SHA,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="delta.reference",
                kind=IntegrationEvidenceCheckKind.DELTA_CDF_PROVIDER,
                required=False,
            ),
        ),
    )


def test_candidate_runner_requires_independent_framework_and_domain_hashes():
    spec = _candidate_spec()
    config = ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=DOMAIN_SHA,
        framework_artifact_sha256=FRAMEWORK_SHA,
    )
    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ={},
        selected_check_ids=("delta.reference",),
        allow_mutating_checks=True,
    )
    assert plan.release_hash == DOMAIN_SHA
    assert plan.framework_artifact_sha256 == FRAMEWORK_SHA

    for changed, message in (
        ({"framework_artifact_sha256": "c" * 64}, "framework artifact"),
        ({"release_hash": "d" * 64}, "domain release"),
        ({"framework_artifact_sha256": None}, "requires framework_artifact_sha256"),
    ):
        bad = config.model_copy(update=changed)
        try:
            build_approved_integration_run_plan(
                bad,
                spec,
                environ={},
                selected_check_ids=("delta.reference",),
                allow_mutating_checks=True,
            )
        except ValueError as exc:
            assert message in str(exc)
        else:
            raise AssertionError("mismatched candidate identities must fail closed")


def test_manifest_hash_and_validation_include_domain_release_identity():
    spec = _candidate_spec()
    manifest = run_integration_evidence(spec, runners={})
    assert manifest.release_hash == FRAMEWORK_SHA
    assert manifest.domain_release_hash == DOMAIN_SHA
    validate_integration_evidence_manifest(spec, manifest)

    changed = manifest.model_copy(update={"domain_release_hash": "c" * 64})
    try:
        validate_integration_evidence_manifest(spec, changed)
    except ValueError as exc:
        assert "domain release hash" in str(exc)
    else:
        raise AssertionError("domain release identity mismatch must fail closed")


def test_legacy_single_hash_runner_remains_supported_only_without_domain_hash():
    legacy = IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=DOMAIN_SHA,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="delta.reference",
                kind=IntegrationEvidenceCheckKind.DELTA_CDF_PROVIDER,
                required=False,
            ),
        ),
    )
    config = ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=DOMAIN_SHA,
    )
    plan = build_approved_integration_run_plan(
        config,
        legacy,
        environ={},
        selected_check_ids=("delta.reference",),
        allow_mutating_checks=True,
    )
    assert plan.framework_artifact_sha256 is None
