from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/candidate-release-proofs.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_candidate_release_proofs_is_exact_candidate_fail_closed_aggregation():
    workflow = _text()
    assert "workflow_dispatch:" in workflow
    assert "candidate_run_id:" in workflow
    assert "candidate_git_sha:" in workflow
    assert "candidate_wheel_sha256:" in workflow
    assert "integration_inputs_run_id:" in workflow
    assert "business_path_evidence_run_id:" in workflow
    assert "environment:" in workflow
    assert 'os.environ["GITHUB_SHA"] != os.environ["CANDIDATE_SHA"]' in workflow
    assert 'ref: ${{ inputs.candidate_git_sha }}' in workflow
    assert "framework-wheel-${CANDIDATE_SHA}" in workflow
    assert "candidate_artifact.py verify" in workflow
    for job in ("test-python-3.11", "test-python-3.13", "build-wheel", "release-readiness-contract"):
        assert f'"{job}"' in workflow


def test_candidate_release_proofs_has_no_customer_compatibility_chain():
    workflow = _text()
    for forbidden in (
        "customer_git_sha",
        "CUSTOMER_SHA",
        "fabric-customer",
        "customer.compatibility",
        "CUSTOMER_COMPATIBILITY",
        "customer-inputs",
        "customer-release-manifest",
        "domain_release_hash",
    ):
        assert forbidden not in workflow


def test_candidate_release_proofs_authenticates_exact_integration_inputs():
    workflow = _text()
    assert ".github/workflows/candidate-integration-inputs.yml" in workflow
    assert "integration-inputs-${CANDIDATE_SHA}-${CERTIFICATION_ENVIRONMENT}" in workflow
    assert "integration-inputs/INPUTS.json" in workflow
    assert 'inputs.get("integration_inputs_hash")' in workflow
    assert "proof.integration_inputs_hash != input_hash" in workflow
    assert "integration_inputs_hash=input_hash" in workflow
    assert 'INTEGRATION_INPUTS_HASH: ${{ steps.inputs.outputs.integration_inputs_hash }}' in workflow


def test_candidate_release_proofs_only_creates_static_passes_it_observed():
    workflow = _text()
    assert 'gate_id="source.tests"' in workflow
    assert 'gate_id="wheel.integrity"' in workflow
    assert 'gate_id="integration.inputs"' in workflow
    assert "ReleaseReadinessGateKind.INTEGRATION_INPUTS" in workflow
    for gate in (
        "full.replace",
        "watermark.scd1",
        "watermark.scd2",
        "retry.idempotency",
        "reconciliation.fail_closed",
    ):
        assert f'gate_id="{gate}"' not in workflow


def test_candidate_release_proofs_requires_live_business_path_artifact_then_strict_merge():
    workflow = _text()
    assert ".github/workflows/candidate-business-path-evidence.yml" in workflow
    assert "business-path-release-proofs-${CANDIDATE_SHA}-${CERTIFICATION_ENVIRONMENT}" in workflow
    assert "business-path-release-proofs.json" in workflow
    assert "fabric-framework release-proofs-merge" in workflow
    assert "required_non_integration" in workflow
    assert "ReleaseReadinessStatus.PASS" in workflow
    assert "release-proofs-${{ inputs.candidate_git_sha }}-${{ inputs.environment }}" in workflow
    assert "retention-days: 90" in workflow
    assert "python -m pip wheel" not in workflow
    assert "gh release create" not in workflow
    assert "git tag" not in workflow
