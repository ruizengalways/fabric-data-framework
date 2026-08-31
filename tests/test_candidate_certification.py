from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from fabric_data_framework.evidence.candidate_certification import (
    certify_release_candidate,
    materialize_candidate_integration_spec,
)
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceManifest,
    IntegrationEvidenceStatus,
    load_integration_evidence_spec,
)
from fabric_data_framework.evidence.release_readiness import (
    ReleaseReadinessGateKind,
    ReleaseReadinessProofBundle,
    ReleaseReadinessProofResult,
    ReleaseReadinessStatus,
    load_release_readiness_spec,
)


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = "a" * 40
ARTIFACT = "b" * 64
DOMAIN_RELEASE = "e" * 64
AT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
ID = UUID("11111111-1111-1111-1111-111111111111")


def _template():
    return load_integration_evidence_spec(
        ROOT / "release/0.4.0/integration-evidence-template.json"
    )


def _readiness_spec():
    return load_release_readiness_spec(ROOT / "release/0.4.0/readiness-spec.json")


def _proofs(
    *,
    secret_reference: bool = False,
    domain_release_hash: str | None = DOMAIN_RELEASE,
) -> ReleaseReadinessProofBundle:
    kinds = {
        "source.tests": ReleaseReadinessGateKind.SOURCE_VERIFICATION,
        "wheel.integrity": ReleaseReadinessGateKind.WHEEL_INTEGRITY,
        "customer.compatibility": ReleaseReadinessGateKind.CUSTOMER_COMPATIBILITY,
        "full.replace": ReleaseReadinessGateKind.FULL_REPLACE,
        "watermark.scd1": ReleaseReadinessGateKind.WATERMARK_SCD1,
        "watermark.scd2": ReleaseReadinessGateKind.WATERMARK_SCD2,
        "retry.idempotency": ReleaseReadinessGateKind.RETRY_IDEMPOTENCY,
        "reconciliation.fail_closed": ReleaseReadinessGateKind.RECONCILIATION_FAIL_CLOSED,
    }
    return ReleaseReadinessProofBundle(
        framework_version="0.4.0",
        candidate_git_sha=CANDIDATE,
        artifact_sha256=ARTIFACT,
        domain_release_hash=domain_release_hash,
        results=tuple(
            ReleaseReadinessProofResult(
                gate_id=gate_id,
                kind=kind,
                status=ReleaseReadinessStatus.PASS,
                evidence_references=(
                    "https://evidence.example.invalid/run/1?token=secret"
                    if secret_reference and gate_id == "source.tests"
                    else f"github-actions://candidate/{gate_id}/1",
                ),
            )
            for gate_id, kind in kinds.items()
        ),
    )


def _integration_manifest(
    *,
    fail_check: str | None = None,
    release_hash: str = ARTIFACT,
    domain_release_hash: str | None = DOMAIN_RELEASE,
):
    spec = materialize_candidate_integration_spec(
        _template(),
        environment="DEV",
        domain="customer",
        artifact_sha256=release_hash,
        domain_release_hash=domain_release_hash,
    )
    results = []
    for check in spec.checks:
        status = (
            IntegrationEvidenceStatus.FAIL
            if check.check_id == fail_check
            else (
                IntegrationEvidenceStatus.NOT_RUN
                if check.check_id == "kafka.live"
                else IntegrationEvidenceStatus.PASS
            )
        )
        kwargs: dict[str, object] = {
            "check_id": check.check_id,
            "kind": check.kind,
            "status": status,
            "started_at": AT,
            "completed_at": AT,
        }
        if status is IntegrationEvidenceStatus.PASS:
            kwargs["evidence_references"] = (
                f"github-actions://live-evidence/{check.check_id}/1",
            )
            if check.check_id == "fabric.item.read":
                kwargs.update(workspace_id=ID, item_id=ID)
            elif check.check_id == "fabric.pipeline":
                kwargs.update(
                    framework_pipeline_run_id=ID,
                    workspace_id=ID,
                    item_id=ID,
                    native_job_instance_id=ID,
                    root_activity_id=ID,
                )
            elif check.check_id in {"fabric.copy", "fabric.spark"}:
                kwargs.update(
                    dataset_run_id=ID,
                    workspace_id=ID,
                    item_id=ID,
                    native_job_instance_id=ID,
                    root_activity_id=ID,
                )
            elif check.check_id == "warehouse.commit":
                kwargs["operation_key"] = "c" * 64
            elif check.check_id == "warehouse.ambiguous_commit":
                kwargs.update(operation_key="d" * 64, dataset_run_id=ID)
        results.append(IntegrationEvidenceCheckResult(**kwargs))
    return IntegrationEvidenceManifest(
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        domain_release_hash=spec.domain_release_hash,
        started_at=AT,
        completed_at=AT,
        checks=spec.checks,
        results=tuple(results),
    )


def test_materialized_integration_spec_binds_runtime_identity_without_mutating_template():
    template = _template()
    assert template.release_hash is None
    assert template.domain_release_hash is None

    bound = materialize_candidate_integration_spec(
        template,
        environment="UAT",
        domain="health",
        artifact_sha256=ARTIFACT,
        domain_release_hash=DOMAIN_RELEASE,
    )

    assert bound.environment.value == "UAT"
    assert bound.domain == "health"
    assert bound.release_hash == ARTIFACT
    assert bound.domain_release_hash == DOMAIN_RELEASE
    assert template.release_hash is None
    assert template.domain_release_hash is None
    assert [item.check_id for item in bound.checks] == [
        item.check_id for item in template.checks
    ]


def test_candidate_certification_requires_all_required_readiness_and_integration_gates_pass():
    report = certify_release_candidate(
        _readiness_spec(),
        _template(),
        candidate_git_sha=CANDIDATE,
        artifact_sha256=ARTIFACT,
        environment="DEV",
        domain="customer",
        proofs=_proofs(),
        integration_evidence=_integration_manifest(),
    )

    assert report.release_ready is True
    assert report.blockers == ()
    assert report.domain_release_hash == DOMAIN_RELEASE
    assert all(
        (not result.required) or result.status is ReleaseReadinessStatus.PASS
        for result in report.results
    )


def test_candidate_certification_rejects_noncertified_required_integration_manifest():
    with pytest.raises(ValueError):
        certify_release_candidate(
            _readiness_spec(),
            _template(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256=ARTIFACT,
            environment="DEV",
            domain="customer",
            proofs=_proofs(),
            integration_evidence=_integration_manifest(fail_check="fabric.spark"),
        )


def test_candidate_certification_rejects_integration_evidence_for_other_wheel():
    other_hash = "f" * 64
    with pytest.raises(ValueError, match="release hash|does not match"):
        certify_release_candidate(
            _readiness_spec(),
            _template(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256=ARTIFACT,
            environment="DEV",
            domain="customer",
            proofs=_proofs(),
            integration_evidence=_integration_manifest(release_hash=other_hash),
        )


def test_candidate_certification_rejects_missing_or_mismatched_domain_release_identity():
    with pytest.raises(ValueError, match="proof must bind exact domain_release_hash"):
        certify_release_candidate(
            _readiness_spec(),
            _template(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256=ARTIFACT,
            environment="DEV",
            domain="customer",
            proofs=_proofs(domain_release_hash=None),
            integration_evidence=_integration_manifest(),
        )

    with pytest.raises(ValueError, match="integration evidence must bind exact domain_release_hash"):
        certify_release_candidate(
            _readiness_spec(),
            _template(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256=ARTIFACT,
            environment="DEV",
            domain="customer",
            proofs=_proofs(),
            integration_evidence=_integration_manifest(domain_release_hash=None),
        )

    with pytest.raises(ValueError, match="proof/integration domain release hash mismatch"):
        certify_release_candidate(
            _readiness_spec(),
            _template(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256=ARTIFACT,
            environment="DEV",
            domain="customer",
            proofs=_proofs(),
            integration_evidence=_integration_manifest(domain_release_hash="d" * 64),
        )


def test_candidate_certification_rejects_secret_like_release_proof_reference():
    with pytest.raises(ValueError, match="credential material"):
        certify_release_candidate(
            _readiness_spec(),
            _template(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256=ARTIFACT,
            environment="DEV",
            domain="customer",
            proofs=_proofs(secret_reference=True),
            integration_evidence=_integration_manifest(),
        )
