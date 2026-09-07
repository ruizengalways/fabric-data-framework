from pathlib import Path


WORKFLOW = Path(".github/workflows/candidate-business-path-evidence.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_is_manual_exact_candidate_live_producer():
    text = _text()
    assert "workflow_dispatch:" in text
    assert "candidate_git_sha:" in text
    assert "candidate_wheel_sha256:" in text
    assert "integration_inputs_run_id:" in text
    assert "integration_evidence_run_id:" in text
    assert "environment:" in text
    assert "candidate-business-path-evidence must be dispatched at the exact candidate ref" in text
    assert 'git merge-base --is-ancestor "${CANDIDATE_SHA}" origin/main' in text
    assert ".github/workflows/ci.yml" in text
    assert "framework-wheel-${CANDIDATE_SHA}" in text
    assert "candidate_artifact.py verify" in text


def test_workflow_uses_only_framework_owned_input_and_integration_producers():
    text = _text()
    assert ".github/workflows/candidate-integration-inputs.yml" in text
    assert ".github/workflows/candidate-integration-evidence.yml" in text
    assert "integration-inputs-${CANDIDATE_SHA}-${CERTIFICATION_ENVIRONMENT}" in text
    assert "integration-evidence-${CANDIDATE_SHA}-${CERTIFICATION_ENVIRONMENT}" in text
    for forbidden in (
        "fabric-customer",
        "customer_git_sha",
        "customer_inputs_run_id",
        "CUSTOMER_REPO_TOKEN",
        "CUSTOMER_SHA",
        "customer-inputs",
        "candidate-business-path-inputs",
        "domain_release_hash",
        "runner.release_hash",
        "retained.release_hash",
    ):
        assert forbidden not in text


def test_workflow_binds_framework_artifact_and_integration_input_hash():
    text = _text()
    assert 'runner.framework_artifact_sha256 != os.environ["CANDIDATE_WHEEL_SHA256"]' in text
    assert "runner.integration_inputs_hash != input_hash" in text
    assert 'retained.framework_artifact_sha256 != os.environ["CANDIDATE_WHEEL_SHA256"]' in text
    assert "retained.integration_inputs_hash != input_hash" in text
    assert "bundle.integration_inputs_hash != expected_hash" in text


def test_workflow_cannot_author_business_gate_pass_json_directly():
    text = _text()
    assert "candidate-business-path-run" in text
    assert "--allow-pipeline-execution" in text
    assert "--allow-scenario-mutation" in text
    assert "release-proofs-merge" in text
    assert "ReleaseReadinessProofResult(" not in text
    assert "ReleaseReadinessProofBundle(" not in text
    assert "InMemory" not in text


def test_workflow_authenticates_exact_plan_scenarios_and_framework_entry_points():
    text = _text()
    assert "load_approved_business_path_certification_plan" in text
    assert "load_approved_business_path_scenario" in text
    assert "load_approved_business_path_driver_config" in text
    assert 'scenario.extension_artifact_name != inputs["framework_wheel_filename"]' in text
    assert 'driver.extension_artifact_name != inputs["framework_wheel_filename"]' in text
    assert 'if len(lines) != 5' in text
    assert "expected = {gate.value for gate in BusinessPathGate}" in text
    assert "every business-path proof must PASS" in text


def test_workflow_retains_exact_input_manifest_with_strictly_merged_proof():
    text = _text()
    assert "cp integration-inputs/INPUTS.json retained/INPUTS.json" in text
    assert "business-path-release-proofs.json" in text
    assert "certified-integration-evidence.json" in text
    assert "customer-release-manifest" not in text


def test_workflow_only_uploads_after_five_strictly_merged_proofs():
    text = _text()
    merge_pos = text.index("Strictly merge and verify five live business-path proofs")
    upload_pos = text.index("Upload exact-candidate business-path evidence")
    assert merge_pos < upload_pos
    assert "business-path-release-proofs-${{ inputs.candidate_git_sha }}-${{ inputs.environment }}" in text
    assert "retention-days: 90" in text
