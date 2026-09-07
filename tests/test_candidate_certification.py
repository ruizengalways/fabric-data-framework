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
INPUTS_HASH = "e" * 64
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
    integration_inputs_hash: str = INPUTS_HASH,
) -> ReleaseReadinessProofBundle:
    kinds = {
        "source.tests": ReleaseReadinessGateKind.SOURCE_VERIFICATION,
        "wheel.integrity": ReleaseReadinessGateKind.WHEEL_INTEGRITY,
        "integration.inputs": ReleaseReadinessGateKind.INTEGRATION_INPUTS,
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
        integration_inputs_hash=integration_inputs_hash,
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
    artifact_sha256: str = ARTIFACT,
    integration_inputs_hash: str = INPUTS_HASH,
):
    spec = materialize_candidate_integration_spec(
        _template(),
        environment="DEV",
        domain="framework-certification",
        artifact_sha256=artifact_sha256,
        integration_inputs_hash=integration_inputs_hash,
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
        framework_artifact_sha256=spec.framework_artifact_sha256,
        integration_inputs_hash=spec.integration_inputs_hash,
        started_at=AT,
        completed_at=AT,
        checks=spec.checks,
        results=tuple(results),
    )


def test_materialized_integration_spec_binds_explicit_identities_without_mutating_template():
    template = _template()
    assert template.framework_artifact_sha256 is None
    assert template.integration_inputs_hash is None

    bound = materialize_candidate_integration_spec(
        template,
        environment="UAT",
        domain="framework-certification",
        artifact_sha256=ARTIFACT,
        integration_inputs_hash=INPUTS_HASH,
    )

    assert bound.environment.value == "UAT"
    assert bound.domain == "framework-certification"
    assert bound.framework_artifact_sha256 == ARTIFACT
    assert bound.integration_inputs_hash == INPUTS_HASH
    assert template.framework_artifact_sha256 is None
    assert template.integration_inputs_hash is None
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
        domain="framework-certification",
        proofs=_proofs(),
        integration_evidence=_integration_manifest(),
    )

    assert report.release_ready is True
    assert report.blockers == ()
    assert report.integration_inputs_hash == INPUTS_HASH
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
            domain="framework-certification",
            proofs=_proofs(),
            integration_evidence=_integration_manifest(fail_check="fabric.spark"),
        )


def test_candidate_certification_rejects_integration_evidence_for_other_wheel():
    with pytest.raises(ValueError, match="artifact|SHA256"):
        certify_release_candidate(
            _readiness_spec(),
            _template(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256=ARTIFACT,
            environment="DEV",
            domain="framework-certification",
            proofs=_proofs(),
            integration_evidence=_integration_manifest(artifact_sha256="f" * 64),
        )


def test_candidate_certification_rejects_mismatched_integration_input_identity():
    with pytest.raises(ValueError, match="integration inputs hash mismatch"):
        certify_release_candidate(
            _readiness_spec(),
            _template(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256=ARTIFACT,
            environment="DEV",
            domain="framework-certification",
            proofs=_proofs(),
            integration_evidence=_integration_manifest(integration_inputs_hash="d" * 64),
        )


def test_candidate_certification_rejects_secret_like_release_proof_reference():
    with pytest.raises(ValueError, match="credential material"):
        certify_release_candidate(
            _readiness_spec(),
            _template(),
            candidate_git_sha=CANDIDATE,
            artifact_sha256=ARTIFACT,
            environment="DEV",
            domain="framework-certification",
            proofs=_proofs(secret_reference=True),
            integration_evidence=_integration_manifest(),
        )
