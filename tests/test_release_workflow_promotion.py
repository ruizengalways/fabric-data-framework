from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_workflow_promotes_exact_candidate_and_never_rebuilds_wheel():
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "candidate_run_id:" in workflow
    assert "candidate_git_sha:" in workflow
    assert "candidate_wheel_sha256:" in workflow
    assert "readiness_run_id:" in workflow
    assert "certification_environment:" in workflow
    assert "tags:" not in workflow
    assert "python -m pip wheel" not in workflow
    assert "python -m build" not in workflow
    assert "candidate_artifact.py verify" in workflow
    assert 'framework-wheel-${CANDIDATE_SHA}' in workflow
    assert 'release-readiness-certified-${CANDIDATE_SHA}-${CERTIFICATION_ENVIRONMENT}' in workflow
    assert 'report.get("release_ready") is not True' in workflow
    assert 'report.get("blockers") != []' in workflow
    assert 'input_hash = report.get("integration_inputs_hash")' in workflow
    assert 'proofs.get("integration_inputs_hash") != input_hash' in workflow
    assert 'integration.get("framework_artifact_sha256") != expected_wheel' in workflow
    assert 'integration.get("integration_inputs_hash") != input_hash' in workflow
    assert 'inputs.get("integration_inputs_hash") != input_hash' in workflow
    assert 'domain_release_hash' not in workflow
    assert 'integration.get("release_hash")' not in workflow
    assert 'git tag -a "${RELEASE_TAG}" "${CANDIDATE_SHA}"' in workflow


def test_main_ci_candidate_artifact_contains_manifest_and_longer_retention():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "candidate_artifact.py create" in workflow
    assert "candidate_artifact.py verify" in workflow
    assert "--output dist/CANDIDATE.json" in workflow
    assert "framework-wheel-${{ github.sha }}" in workflow
    assert "refs/heads/main' && 90 || 14" in workflow
