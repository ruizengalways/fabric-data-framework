"""Exact-candidate certification over retained release and integration evidence.

This module never executes Fabric and never creates evidence. It validates an exact
candidate's retained proof bundle and IntegrationEvidenceManifest against
source-controlled policy, then delegates final readiness aggregation to the existing
release-readiness evaluator.
"""

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
) -> IntegrationEvidenceSpec:
    """Bind a credential-free integration evidence template to one exact wheel.

    The template owns the approved check membership/kinds/required flags. Runtime
    identity values are supplied only at certification time and are validated by the
    canonical IntegrationEvidenceSpec model.
    """

    if template.release_hash is not None:
        raise ValueError("integration evidence template release_hash must be null")
    if re.fullmatch(r"[0-9a-f]{64}", artifact_sha256) is None:
        raise ValueError("artifact_sha256 must be a 64-character lowercase SHA256")
    normalized_domain = domain.strip()
    if not normalized_domain:
        raise ValueError("certification domain must be non-empty")
    assert_safe_retained_text(normalized_domain, "certification domain")

    payload = template.model_dump(mode="json")
    payload.update(
        {
            "environment": EnvironmentName(environment).value,
            "domain": normalized_domain,
            "release_hash": artifact_sha256,
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
    """Require exact integration certification and zero readiness blockers.

    This is intentionally stricter than generating a normal readiness report. It is
    the reusable boundary used by the candidate-certification workflow before a
    ``release-readiness-certified-<sha>`` artifact may be retained.
    """

    expected_integration_spec = materialize_candidate_integration_spec(
        integration_template,
        environment=environment,
        domain=domain,
        artifact_sha256=artifact_sha256,
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
    if not report.release_ready:
        raise ValueError(
            "release candidate is not certified; required gates not PASS: "
            + ", ".join(report.blockers)
        )
    return report


__all__ = [
    "certify_release_candidate",
    "materialize_candidate_integration_spec",
]
