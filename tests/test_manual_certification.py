from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from fabric_data_framework.deployment.candidate_artifact import CandidateArtifactManifest
from fabric_data_framework.evidence.manual_certification import (
    ManualCertificationCheck,
    ManualCertificationCheckStatus,
    ManualCertificationMode,
    ManualCertificationStatus,
    create_admin_override_record,
    create_manual_certification_record,
    load_manual_certification_record,
    write_manual_certification_record,
)


AT = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)
CANDIDATE = "a" * 40
ARTIFACT = "b" * 64


def _write_manifest(path: Path) -> None:
    payload = CandidateArtifactManifest(
        schema_version=1,
        package_name="fabric-data-framework",
        framework_version="0.4.0",
        candidate_git_sha=CANDIDATE,
        workflow_run_id=123,
        workflow_run_attempt=1,
        wheel_filename="fabric_data_framework-0.4.0-py3-none-any.whl",
        wheel_sha256=ARTIFACT,
    )
    path.write_text(json.dumps(payload.__dict__), encoding="utf-8")


def _pass(check_id: str) -> ManualCertificationCheck:
    return ManualCertificationCheck(
        check_id=check_id,
        status=ManualCertificationCheckStatus.PASS,
        evidence_reference=f"notebook://cert/{check_id}",
    )


def test_manifest_auto_fills_long_candidate_identity_without_manual_typing(tmp_path: Path):
    manifest = tmp_path / "CANDIDATE.json"
    _write_manifest(manifest)

    record = create_manual_certification_record(
        checks=(_pass("full.replace"),),
        candidate_manifest_path=manifest,
        environment="DEV",
        notebook_reference="fabric-notebook://framework-cert-dev/run-1",
        now=lambda: AT,
    )

    assert record.framework_version == "0.4.0"
    assert record.candidate_git_sha == CANDIDATE
    assert record.artifact_sha256 == ARTIFACT
    assert record.status is ManualCertificationStatus.CERTIFIED
    assert record.admin_override is False
    assert record.release_authorized is False
    assert record.missing_fields == ()


def test_incomplete_notebook_record_is_partial_without_admin_override():
    record = create_manual_certification_record(
        checks=(_pass("lakehouse.smoke"),),
        environment="DEV",
        now=lambda: AT,
    )

    assert record.status is ManualCertificationStatus.PARTIAL
    assert record.admin_override is False
    assert "candidate_git_sha" in record.missing_fields
    assert "artifact_sha256" in record.missing_fields
    assert "notebook_reference" in record.missing_fields


def test_admin_override_can_certify_with_missing_optional_context():
    record = create_manual_certification_record(
        checks=(),
        framework_version="0.4.0",
        operator="release-admin",
        admin_override=True,
        override_reason="Company Fabric cannot export the complete notebook evidence bundle",
        now=lambda: AT,
    )

    assert record.status is ManualCertificationStatus.CERTIFIED
    assert record.admin_override is True
    assert record.release_authorized is False
    assert set(record.missing_fields) == {
        "candidate_git_sha",
        "artifact_sha256",
        "environment",
        "notebook_reference",
    }


def test_admin_override_exact_identity_can_explicitly_request_release_authorization():
    record = create_admin_override_record(
        framework_version="0.4.0",
        candidate_git_sha=CANDIDATE,
        artifact_sha256=ARTIFACT,
        operator="github-admin",
        override_reason="Administrator accepts incomplete external evidence",
        request_release_authorization=True,
        now=lambda: AT,
    )

    assert record.certification_mode is ManualCertificationMode.GITHUB_ADMIN_OVERRIDE
    assert record.status is ManualCertificationStatus.CERTIFIED
    assert record.release_authorized is True


def test_release_authorization_stays_false_when_identity_is_missing():
    record = create_admin_override_record(
        framework_version="0.4.0",
        operator="github-admin",
        override_reason="Administrator accepts incomplete external evidence",
        request_release_authorization=True,
        now=lambda: AT,
    )

    assert record.status is ManualCertificationStatus.CERTIFIED
    assert record.release_authorized is False


def test_admin_override_requires_reason():
    with pytest.raises(ValueError, match="override_reason"):
        create_manual_certification_record(
            framework_version="0.4.0",
            admin_override=True,
            now=lambda: AT,
        )


def test_secret_like_override_reason_is_rejected():
    with pytest.raises(ValueError, match="credential material"):
        create_admin_override_record(
            framework_version="0.4.0",
            operator="github-admin",
            override_reason="access_token=do-not-retain",
            now=lambda: AT,
        )


def test_record_round_trip(tmp_path: Path):
    output = tmp_path / "manual-certification.json"
    record = create_admin_override_record(
        framework_version="0.4.0",
        candidate_git_sha=CANDIDATE,
        artifact_sha256=ARTIFACT,
        environment="UAT",
        operator="github-admin",
        notebook_reference="fabric-notebook://cert/run-42",
        override_reason="Manual enterprise certification accepted by administrator",
        checks=(_pass("watermark.scd2"),),
        now=lambda: AT,
    )

    write_manual_certification_record(record, output)
    loaded = load_manual_certification_record(output)

    assert loaded == record
