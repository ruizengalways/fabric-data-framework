from pathlib import Path


WORKFLOW = Path(".github/workflows/candidate-business-path-evidence.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_is_manual_exact_candidate_live_producer():
    text = _text()
    assert "workflow_dispatch:" in text
    assert "candidate_git_sha:" in text
    assert "candidate_wheel_sha256:" in text
    assert "customer_git_sha:" in text
    assert "customer_inputs_run_id:" in text
    assert "integration_evidence_run_id:" in text
    assert "candidate-business-path-evidence must be dispatched at the exact candidate ref" in text
    assert 'git merge-base --is-ancestor "${CANDIDATE_SHA}" origin/main' in text
    assert ".github/workflows/ci.yml" in text
    assert "framework-wheel-${CANDIDATE_SHA}" in text
    assert "candidate_artifact.py verify" in text


def test_workflow_requires_trusted_live_integration_and_customer_input_producers():
    text = _text()
    assert ".github/workflows/candidate-integration-evidence.yml" in text
    assert ".github/workflows/candidate-business-path-inputs.yml" in text
    assert "integration-evidence-${CANDIDATE_SHA}" in text
    assert "business-path-inputs-${CUSTOMER_SHA}" in text
    assert "CUSTOMER_REPO_TOKEN" in text
    assert "retained.certified" in text
    assert "integration evidence must be a successful workflow_dispatch run" in text
    assert "customer certification inputs must come from successful workflow_dispatch" in text


def test_workflow_keeps_framework_wheel_and_domain_release_hashes_distinct():
    text = _text()
    assert 'retained.release_hash != os.environ["CANDIDATE_WHEEL_SHA256"]' in text
    assert "retained.domain_release_hash != manifest.bundle.release_hash" in text
    assert "runner.release_hash != manifest.bundle.release_hash" in text
    assert 'runner.framework_artifact_sha256 != os.environ["CANDIDATE_WHEEL_SHA256"]' in text
    assert "domain_release_hash=retained.domain_release_hash" in text


def test_workflow_cannot_author_business_gate_pass_json_directly():
    text = _text()
    assert "candidate-business-path-run" in text
    assert "--allow-pipeline-execution" in text
    assert "--allow-scenario-mutation" in text
    assert "release-proofs-merge" in text
    assert "ReleaseReadinessProofResult(" not in text
    assert "InMemory" not in text
    assert "fabric_data_framework.apply" not in text
    assert "write_text" not in text or "business-path-release-proofs.json" not in text


def test_workflow_authenticates_exact_plan_scenarios_drivers_and_extension_bytes():
    text = _text()
    assert "load_approved_business_path_certification_plan" in text
    assert "load_approved_business_path_scenario" in text
    assert "load_approved_business_path_driver_config" in text
    assert "business-path extension SHA256 mismatch" in text
    assert 'proof_files[@]}" -ne 5' in text
    assert "expected = {gate.value for gate in BusinessPathGate}" in text
    assert "every business-path proof must PASS" in text


def test_workflow_only_uploads_after_five_strictly_merged_proofs():
    text = _text()
    merge_pos = text.index("Strictly merge and verify five live business-path proofs")
    upload_pos = text.index("Upload exact-candidate business-path evidence")
    assert merge_pos < upload_pos
    assert "business-path-release-proofs-${{ inputs.candidate_git_sha }}" in text
    assert "retention-days: 90" in text
