from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceStatus,
)
from fabric_data_framework.evidence.release_readiness import (
    ReleaseReadinessGateKind,
    ReleaseReadinessGateSpec,
    ReleaseReadinessProofBundle,
    ReleaseReadinessProofResult,
    ReleaseReadinessSpec,
    ReleaseReadinessStatus,
    evaluate_release_readiness,
)


NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
CANDIDATE = "a" * 40
ARTIFACT = "b" * 64


def _spec() -> ReleaseReadinessSpec:
    return ReleaseReadinessSpec(
        framework_version="0.4.0",
        gates=(
            ReleaseReadinessGateSpec(
                gate_id="source.tests",
                kind=ReleaseReadinessGateKind.SOURCE_VERIFICATION,
            ),
            ReleaseReadinessGateSpec(
                gate_id="fabric.pipeline",
                kind=ReleaseReadinessGateKind.FABRIC_PIPELINE,
                integration_check_id="fabric.pipeline",
            ),
            ReleaseReadinessGateSpec(
                gate_id="external.cdc",
                kind=ReleaseReadinessGateKind.EXTERNAL_CDC,
                required=False,
            ),
        ),
    )


def _proofs() -> ReleaseReadinessProofBundle:
    return ReleaseReadinessProofBundle(
        framework_version="0.4.0",
        candidate_git_sha=CANDIDATE,
        artifact_sha256=ARTIFACT,
        results=(
            ReleaseReadinessProofResult(
                gate_id="source.tests",
                kind=ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                status=ReleaseReadinessStatus.PASS,
                evidence_references=("github-actions:framework-ci:123",),
            ),
            ReleaseReadinessProofResult(
                gate_id="external.cdc",
                kind=ReleaseReadinessGateKind.EXTERNAL_CDC,
                status=ReleaseReadinessStatus.OUT_OF_SCOPE,
                detail="Debezium certification excluded from this release scope",
            ),
        ),
    )


def _integration() -> IntegrationEvidenceManifest:
    check = IntegrationEvidenceCheckSpec(
        check_id="fabric.pipeline",
        kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
    )
    result = IntegrationEvidenceCheckResult(
        check_id="fabric.pipeline",
        kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        status=IntegrationEvidenceStatus.PASS,
        started_at=NOW,
        completed_at=NOW,
        framework_pipeline_run_id=uuid4(),
        workspace_id=uuid4(),
        item_id=uuid4(),
        native_job_instance_id=uuid4(),
        root_activity_id=uuid4(),
        evidence_references=("fabric:pipeline:retained",),
    )
    return IntegrationEvidenceManifest(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=ARTIFACT,
        started_at=NOW,
        completed_at=NOW,
        checks=(check,),
        results=(result,),
    )


def test_missing_evidence_blocks_release_without_inference():
    report = evaluate_release_readiness(
        _spec(), candidate_git_sha=CANDIDATE, now=lambda: NOW
    )

    assert report.release_ready is False
    assert report.blockers == ("source.tests", "fabric.pipeline")
    assert [item.status for item in report.results] == [
        ReleaseReadinessStatus.NOT_RUN,
        ReleaseReadinessStatus.NOT_RUN,
        ReleaseReadinessStatus.NOT_RUN,
    ]


def test_retained_proofs_and_exact_artifact_integration_can_make_release_ready():
    report = evaluate_release_readiness(
        _spec(),
        candidate_git_sha=CANDIDATE,
        artifact_sha256=ARTIFACT,
        proofs=_proofs(),
        integration_evidence=_integration(),
        now=lambda: NOW,
    )

    assert report.release_ready is True
    assert report.blockers == ()
    assert report.results[0].status is ReleaseReadinessStatus.PASS
    assert report.results[1].status is ReleaseReadinessStatus.PASS
    assert report.results[2].status is ReleaseReadinessStatus.OUT_OF_SCOPE


def test_proof_bundle_must_match_exact_candidate_sha():
    proofs = _proofs().model_copy(update={"candidate_git_sha": "c" * 40})
    with pytest.raises(ValueError, match="candidate git SHA mismatch"):
        evaluate_release_readiness(
            _spec(), candidate_git_sha=CANDIDATE, proofs=proofs, now=lambda: NOW
        )


def test_live_integration_must_match_exact_artifact_sha256():
    with pytest.raises(ValueError, match="release hash does not match"):
        evaluate_release_readiness(
            _spec(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256="d" * 64,
            integration_evidence=_integration(),
            now=lambda: NOW,
        )


def test_integration_backed_gate_cannot_be_bypassed_by_generic_proof():
    proofs = ReleaseReadinessProofBundle(
        framework_version="0.4.0",
        candidate_git_sha=CANDIDATE,
        results=(
            ReleaseReadinessProofResult(
                gate_id="fabric.pipeline",
                kind=ReleaseReadinessGateKind.FABRIC_PIPELINE,
                status=ReleaseReadinessStatus.PASS,
                evidence_references=("manual:claim",),
            ),
        ),
    )
    with pytest.raises(ValueError, match="cannot be satisfied by proof bundle"):
        evaluate_release_readiness(
            _spec(), candidate_git_sha=CANDIDATE, proofs=proofs, now=lambda: NOW
        )


def test_required_gate_cannot_escape_as_out_of_scope():
    spec = ReleaseReadinessSpec(
        framework_version="0.4.0",
        gates=(
            ReleaseReadinessGateSpec(
                gate_id="source.tests",
                kind=ReleaseReadinessGateKind.SOURCE_VERIFICATION,
            ),
        ),
    )
    proofs = ReleaseReadinessProofBundle(
        framework_version="0.4.0",
        candidate_git_sha=CANDIDATE,
        results=(
            ReleaseReadinessProofResult(
                gate_id="source.tests",
                kind=ReleaseReadinessGateKind.SOURCE_VERIFICATION,
                status=ReleaseReadinessStatus.OUT_OF_SCOPE,
            ),
        ),
    )

    report = evaluate_release_readiness(
        spec, candidate_git_sha=CANDIDATE, proofs=proofs, now=lambda: NOW
    )
    assert report.release_ready is False
    assert report.results[0].status is ReleaseReadinessStatus.FAIL


def test_pass_proof_requires_retained_reference():
    with pytest.raises(ValidationError, match="PASS requires"):
        ReleaseReadinessProofResult(
            gate_id="source.tests",
            kind=ReleaseReadinessGateKind.SOURCE_VERIFICATION,
            status=ReleaseReadinessStatus.PASS,
        )
