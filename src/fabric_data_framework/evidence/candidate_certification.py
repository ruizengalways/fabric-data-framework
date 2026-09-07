"""Exact-candidate certification over retained release and integration evidence."""

from __future__ import annotations

import re

from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    validate_integration_evidence_manifest,
)
from fabric_data_framework.evidence.release_readiness import (
    ReleaseReadinessProofBundle,
    ReleaseReadinessReport,
    ReleaseReadinessSpec,
    evaluate_release_readiness,
)
from fabric_data_framework.evidence.safety import assert_safe_retained_text


def materialize_candidate_integration_spec(
    template: IntegrationEvidenceSpec,
    *,
    environment: EnvironmentName | str,
    domain: str,
    artifact_sha256: str,
    integration_inputs_hash: str,
) -> IntegrationEvidenceSpec:
    """Bind the integration template to exact framework and input-bundle identities."""

    if template.framework_artifact_sha256 is not None:
        raise ValueError("integration evidence template framework_artifact_sha256 must be null")
    if template.integration_inputs_hash is not None:
        raise ValueError("integration evidence template integration_inputs_hash must be null")
    if re.fullmatch(r"[0-9a-f]{64}", artifact_sha256) is None:
        raise ValueError("artifact_sha256 must be a 64-character lowercase SHA256")
    if re.fullmatch(r"[0-9a-f]{64}", integration_inputs_hash) is None:
        raise ValueError("integration_inputs_hash must be a 64-character lowercase SHA256")
    normalized_domain = domain.strip()
    if not normalized_domain:
        raise ValueError("certification domain must be non-empty")
    assert_safe_retained_text(normalized_domain, "certification domain")

    payload = template.model_dump(mode="json")
    payload.update(
        {
            "environment": EnvironmentName(environment).value,
            "domain": normalized_domain,
            "framework_artifact_sha256": artifact_sha256,
            "integration_inputs_hash": integration_inputs_hash,
        }
    )
    return IntegrationEvidenceSpec.model_validate(payload)


def _validate_release_proof_safety(proofs: ReleaseReadinessProofBundle) -> None:
    for result in proofs.results:
        for reference in result.evidence_references:
            assert_safe_retained_text(reference, "release evidence reference")
        if result.detail is not None:
            assert_safe_retained_text(result.detail, "release evidence detail")


def certify_release_candidate(
    readiness_spec: ReleaseReadinessSpec,
    integration_template: IntegrationEvidenceSpec,
    *,
    candidate_git_sha: str,
    artifact_sha256: str,
    environment: EnvironmentName | str,
    domain: str,
    proofs: ReleaseReadinessProofBundle,
    integration_evidence: IntegrationEvidenceManifest,
) -> ReleaseReadinessReport:
    """Require exact integration certification and zero readiness blockers."""

    if proofs.integration_inputs_hash is None:
        raise ValueError("candidate release proof must bind exact integration_inputs_hash")
    if integration_evidence.integration_inputs_hash is None:
        raise ValueError("candidate integration evidence must bind exact integration_inputs_hash")
    if proofs.integration_inputs_hash != integration_evidence.integration_inputs_hash:
        raise ValueError("candidate proof/integration input hash mismatch")

    expected_integration_spec = materialize_candidate_integration_spec(
        integration_template,
        environment=environment,
        domain=domain,
        artifact_sha256=artifact_sha256,
        integration_inputs_hash=proofs.integration_inputs_hash,
    )
    if expected_integration_spec.framework_version != readiness_spec.framework_version:
        raise ValueError(
            "integration template framework version does not match readiness specification"
        )

    _validate_release_proof_safety(proofs)
    validate_integration_evidence_manifest(
        expected_integration_spec,
        integration_evidence,
        require_certified=True,
    )
    report = evaluate_release_readiness(
        readiness_spec,
        candidate_git_sha=candidate_git_sha,
        artifact_sha256=artifact_sha256,
        proofs=proofs,
        integration_evidence=integration_evidence,
    )
    if report.integration_inputs_hash != proofs.integration_inputs_hash:
        raise ValueError("candidate readiness report lost exact integration input identity")
    if not report.release_ready:
        raise ValueError(
            "release candidate is not certified; required gates not PASS: "
            + ", ".join(report.blockers)
        )
    return report


__all__ = ["certify_release_candidate", "materialize_candidate_integration_spec"]
