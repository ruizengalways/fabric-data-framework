from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fabric_data_framework.infrastructure import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    run_integration_evidence,
    validate_integration_evidence_manifest,
)


NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def _spec(*checks):
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        checks=checks
        or (
            IntegrationEvidenceCheckSpec(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            ),
        ),
    )


def _item_pass():
    return IntegrationEvidenceCheckResult(
        check_id="fabric.item.read",
        kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
        status=IntegrationEvidenceStatus.PASS,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        workspace_id=uuid4(),
        item_id=uuid4(),
        evidence_references=("fabric-item-read:dev:verified",),
    )


def _pipeline_pass():
    return IntegrationEvidenceCheckResult(
        check_id="fabric.pipeline",
        kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        status=IntegrationEvidenceStatus.PASS,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=2),
        framework_pipeline_run_id=uuid4(),
        workspace_id=uuid4(),
        item_id=uuid4(),
        native_job_instance_id=uuid4(),
        root_activity_id=uuid4(),
        evidence_references=("control-plane:pipeline-run:retained",),
    )


def test_all_required_pass_results_certify_manifest():
    spec = _spec()
    times = iter(
        [
            NOW,
            NOW,
            NOW + timedelta(seconds=1),
            NOW + timedelta(seconds=2),
        ]
    )

    manifest = run_integration_evidence(
        spec,
        runners={
            "fabric.item.read": _item_pass,
            "fabric.pipeline": _pipeline_pass,
        },
        now=lambda: next(times),
    )

    assert manifest.certified is True
    assert len(manifest.manifest_hash) == 64
    validate_integration_evidence_manifest(spec, manifest, require_certified=True)


def test_missing_required_runner_is_not_run_and_blocks_certification():
    spec = _spec()
    manifest = run_integration_evidence(
        spec,
        runners={"fabric.item.read": _item_pass},
        now=lambda: NOW,
    )

    assert manifest.certified is False
    pipeline = next(item for item in manifest.results if item.check_id == "fabric.pipeline")
    assert pipeline.status is IntegrationEvidenceStatus.NOT_RUN
    with pytest.raises(ValueError, match="fabric.pipeline"):
        validate_integration_evidence_manifest(spec, manifest, require_certified=True)


def test_runner_exception_is_fail_without_copying_sensitive_exception_text():
    spec = _spec(
        IntegrationEvidenceCheckSpec(
            check_id="warehouse.commit",
            kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
        )
    )

    def broken():
        raise RuntimeError(
            "connection failed password=super-secret; Authorization: Bearer abc.def"
        )

    manifest = run_integration_evidence(
        spec,
        runners={"warehouse.commit": broken},
        now=lambda: NOW,
    )

    result = manifest.results[0]
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert result.detail == "integration check runner raised RuntimeError"
    rendered = manifest.model_dump_json()
    assert "super-secret" not in rendered
    assert "Bearer abc.def" not in rendered


def test_pass_result_requires_kind_specific_correlation_and_reference():
    with pytest.raises(ValidationError, match="FABRIC_PIPELINE_RUN PASS requires"):
        IntegrationEvidenceCheckResult(
            check_id="fabric.pipeline",
            kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            status=IntegrationEvidenceStatus.PASS,
        )

    with pytest.raises(ValidationError, match="evidence_references"):
        IntegrationEvidenceCheckResult(
            check_id="warehouse.commit",
            kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
            status=IntegrationEvidenceStatus.PASS,
            operation_key="b" * 64,
        )


def test_secret_like_material_is_rejected_from_retained_references_and_detail():
    with pytest.raises(ValidationError, match="credential material"):
        IntegrationEvidenceCheckResult(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            status=IntegrationEvidenceStatus.FAIL,
            evidence_references=("https://example.test/evidence?sig=secret-signature",),
        )

    with pytest.raises(ValidationError, match="credential material"):
        IntegrationEvidenceCheckResult(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            status=IntegrationEvidenceStatus.FAIL,
            detail="Authorization: Bearer abc.def",
        )

    with pytest.raises(ValidationError, match="credential material"):
        IntegrationEvidenceCheckResult(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            status=IntegrationEvidenceStatus.FAIL,
            evidence_references=("postgresql://user:password@example.test/db",),
        )

    with pytest.raises(ValidationError, match="user-info"):
        IntegrationEvidenceCheckResult(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            status=IntegrationEvidenceStatus.FAIL,
            evidence_references=("postgresql://alice:s3cr3t@example.test/db",),
        )


def test_optional_failed_check_does_not_block_certification_when_required_check_passes():
    spec = _spec(
        IntegrationEvidenceCheckSpec(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            required=True,
        ),
        IntegrationEvidenceCheckSpec(
            check_id="kafka.live",
            kind=IntegrationEvidenceCheckKind.KAFKA_PROVIDER,
            required=False,
        ),
    )
    manifest = run_integration_evidence(
        spec,
        runners={"fabric.item.read": _item_pass},
        now=lambda: NOW,
    )

    assert manifest.certified is True
    assert manifest.results[1].status is IntegrationEvidenceStatus.NOT_RUN


def test_runner_result_identity_mismatch_is_recorded_as_fail():
    spec = _spec(
        IntegrationEvidenceCheckSpec(
            check_id="fabric.copy",
            kind=IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        )
    )

    manifest = run_integration_evidence(
        spec,
        runners={"fabric.copy": _item_pass},
        now=lambda: NOW,
    )

    assert manifest.certified is False
    assert manifest.results[0].status is IntegrationEvidenceStatus.FAIL
    assert manifest.results[0].detail == "integration check runner raised ValueError"


def test_retained_manifest_must_match_exact_environment_release_and_check_spec():
    spec = _spec()
    manifest = IntegrationEvidenceManifest(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=2),
        checks=spec.checks,
        results=(_item_pass(), _pipeline_pass()),
    )
    changed_spec = spec.model_copy(update={"release_hash": "c" * 64})

    with pytest.raises(ValueError, match="release hash mismatch"):
        validate_integration_evidence_manifest(changed_spec, manifest)


def test_manifest_rejects_missing_or_extra_result_membership():
    spec = _spec()
    with pytest.raises(ValidationError, match="membership must exactly match"):
        IntegrationEvidenceManifest(
            environment=EnvironmentName.DEV,
            domain="customer",
            framework_version="0.4.0",
            release_hash="a" * 64,
            started_at=NOW,
            completed_at=NOW,
            checks=spec.checks,
            results=(_item_pass(),),
        )
