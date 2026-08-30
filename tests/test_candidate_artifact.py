from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from fabric_data_framework.deployment.candidate_artifact import (
    CandidateArtifactManifest,
    create_candidate_artifact_manifest,
    load_candidate_artifact_manifest,
    verify_candidate_artifact,
    write_candidate_artifact_manifest,
)


CANDIDATE = "a" * 40


def _write_wheel(root: Path, *, version: str = "0.4.0", suffix: str = "") -> Path:
    wheel = root / f"fabric_data_framework-{version}-py3-none-any{suffix}.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"fabric_data_framework-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: fabric-data-framework\nVersion: {version}\n",
        )
    return wheel


def test_create_and_verify_candidate_manifest_binds_exact_wheel_bytes(tmp_path):
    wheel = _write_wheel(tmp_path)
    manifest = create_candidate_artifact_manifest(
        tmp_path,
        candidate_git_sha=CANDIDATE,
        workflow_run_id=1234,
        workflow_run_attempt=2,
    )

    assert manifest.package_name == "fabric-data-framework"
    assert manifest.framework_version == "0.4.0"
    assert manifest.wheel_filename == wheel.name
    assert len(manifest.wheel_sha256) == 64

    verified = verify_candidate_artifact(
        tmp_path,
        manifest,
        expected_candidate_git_sha=CANDIDATE,
        expected_workflow_run_id=1234,
        expected_workflow_run_attempt=2,
        expected_framework_version="0.4.0",
        expected_wheel_sha256=manifest.wheel_sha256,
    )
    assert verified == manifest


def test_modified_wheel_is_rejected_after_manifest_creation(tmp_path):
    wheel = _write_wheel(tmp_path)
    manifest = create_candidate_artifact_manifest(
        tmp_path,
        candidate_git_sha=CANDIDATE,
        workflow_run_id=7,
        workflow_run_attempt=1,
    )
    wheel.write_bytes(wheel.read_bytes() + b"tampered")

    with pytest.raises(ValueError, match="wheel bytes do not match"):
        verify_candidate_artifact(
            tmp_path,
            manifest,
            expected_candidate_git_sha=CANDIDATE,
            expected_workflow_run_id=7,
        )


def test_manifest_cannot_be_reused_for_different_candidate_or_run(tmp_path):
    _write_wheel(tmp_path)
    manifest = create_candidate_artifact_manifest(
        tmp_path,
        candidate_git_sha=CANDIDATE,
        workflow_run_id=7,
        workflow_run_attempt=1,
    )

    with pytest.raises(ValueError, match="git SHA"):
        verify_candidate_artifact(
            tmp_path,
            manifest,
            expected_candidate_git_sha="b" * 40,
            expected_workflow_run_id=7,
        )
    with pytest.raises(ValueError, match="workflow run ID"):
        verify_candidate_artifact(
            tmp_path,
            manifest,
            expected_candidate_git_sha=CANDIDATE,
            expected_workflow_run_id=8,
        )


def test_candidate_dist_must_contain_exactly_one_wheel(tmp_path):
    _write_wheel(tmp_path)
    _write_wheel(tmp_path, suffix="-second")

    with pytest.raises(ValueError, match="exactly one wheel"):
        create_candidate_artifact_manifest(
            tmp_path,
            candidate_git_sha=CANDIDATE,
            workflow_run_id=7,
            workflow_run_attempt=1,
        )


def test_manifest_loader_rejects_unknown_fields(tmp_path):
    _write_wheel(tmp_path)
    manifest = create_candidate_artifact_manifest(
        tmp_path,
        candidate_git_sha=CANDIDATE,
        workflow_run_id=7,
        workflow_run_attempt=1,
    )
    path = tmp_path / "CANDIDATE.json"
    write_candidate_artifact_manifest(manifest, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["claim"] = "release-ready"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="keys mismatch"):
        load_candidate_artifact_manifest(path)


def test_manifest_rejects_path_traversal_wheel_filename():
    payload = {
        "schema_version": 1,
        "package_name": "fabric-data-framework",
        "framework_version": "0.4.0",
        "candidate_git_sha": CANDIDATE,
        "workflow_run_id": 1,
        "workflow_run_attempt": 1,
        "wheel_filename": "../candidate.whl",
        "wheel_sha256": "b" * 64,
    }

    with pytest.raises(ValueError, match="plain .whl filename"):
        CandidateArtifactManifest.from_dict(payload)
