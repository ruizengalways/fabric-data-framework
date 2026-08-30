from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_candidate_certification_workflow_is_manual_exact_candidate_aggregation_only():
    workflow = (ROOT / ".github/workflows/candidate-certification.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "candidate_git_sha:" in workflow
    assert "candidate_wheel_sha256:" in workflow
    assert "release_proofs_run_id:" in workflow
    assert "integration_evidence_run_id:" in workflow
    assert 'ref: ${{ inputs.candidate_git_sha }}' in workflow
    assert 'framework-wheel-${CANDIDATE_SHA}' in workflow
    assert "candidate_artifact.py verify" in workflow
    assert '".github/workflows/candidate-release-proofs.yml"' in workflow
    assert '".github/workflows/candidate-integration-evidence.yml"' in workflow
    assert 'release-proofs-${CANDIDATE_SHA}' in workflow
    assert 'integration-evidence-${CANDIDATE_SHA}' in workflow
    assert "fabric-framework candidate-certify" in workflow
    assert 'release-readiness-certified-${{ inputs.candidate_git_sha }}' in workflow
    assert "retention-days: 90" in workflow
    assert "python -m pip wheel" not in workflow
    assert "gh release create" not in workflow
    assert "git tag" not in workflow


def test_candidate_certification_workflow_environment_choices_match_typed_contract():
    workflow = (ROOT / ".github/workflows/candidate-certification.yml").read_text(
        encoding="utf-8"
    )

    environment_block = workflow.split("      environment:\n", 1)[1].split(
        "      domain:\n", 1
    )[0]
    assert "- DEV" in environment_block
    assert "- UAT" in environment_block
    assert "- PROD" in environment_block
    assert "- TEST" not in environment_block
