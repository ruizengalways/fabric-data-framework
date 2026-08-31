from pathlib import Path


WORKFLOW = Path(".github/workflows/candidate-integration-evidence.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_is_manual_exact_candidate_producer_with_protected_environment():
    text = _text()
    assert "workflow_dispatch:" in text
    assert "candidate_run_id:" in text
    assert "candidate_git_sha:" in text
    assert "candidate_wheel_sha256:" in text
    assert "customer_git_sha:" in text
    assert "customer_inputs_run_id:" in text
    assert "environment: ${{ inputs.environment }}" in text
    assert "candidate-integration-evidence must be dispatched at the exact candidate ref" in text
    assert 'git merge-base --is-ancestor "${CANDIDATE_SHA}" origin/main' in text
    assert ".github/workflows/ci.yml" in text
    assert "framework-wheel-${CANDIDATE_SHA}" in text
    assert "candidate_artifact.py verify" in text


def test_workflow_requires_explicit_live_and_separate_session_termination_authorization():
    text = _text()
    assert "authorize_live_mutations:" in text
    assert "authorize_warehouse_session_termination:" in text
    assert "authorize_live_mutations=true" in text
    assert "--allow-conformance-writes" in text
    assert "--allow-pipeline-execution" in text
    assert text.count("--allow-capture-execution") == 2
    assert "--allow-warehouse-execution" in text
    assert "--allow-warehouse-fault-injection" in text
    assert "--allow-warehouse-session-termination" in text
    assert "AUTHORIZE_WAREHOUSE_SESSION_TERMINATION" in text


def test_workflow_consumes_exact_customer_release_and_source_controlled_recipes():
    text = _text()
    assert ".github/workflows/candidate-business-path-inputs.yml" in text
    assert "business-path-inputs-${CUSTOMER_SHA}" in text
    assert "customer-inputs/release-manifest.json" in text
    assert "customer-inputs/runner-config.json" in text
    assert "customer-inputs/project/config/datasets" in text
    assert "control-plane-external-evidence.json" in text
    assert "copy-run.json" in text
    assert "spark-run.json" in text
    assert "warehouse-run.json" in text
    assert "warehouse-fault-run.json" in text
    assert "extension SHA256 mismatch" in text
    assert "fabric.pipeline binding requires customer-owned dataset_id" in text


def test_workflow_keeps_framework_wheel_and_domain_release_hashes_independent():
    text = _text()
    assert "runner.framework_artifact_sha256" in text
    assert "runner.release_hash != release_manifest.bundle.release_hash" in text
    assert "domain_release_hash=os.environ[\"DOMAIN_RELEASE_HASH\"]" in text
    assert 'manifest.release_hash != os.environ["CANDIDATE_WHEEL_SHA256"]' in text
    assert 'manifest.domain_release_hash != os.environ["DOMAIN_RELEASE_HASH"]' in text


def test_workflow_uses_only_existing_approved_execution_commands_and_staged_merge():
    text = _text()
    assert "integration-item-smoke-run" in text
    assert "integration-control-plane-certify-run" in text
    assert "integration-pipeline-run" in text
    assert text.count("integration-capture-run") == 2
    assert "integration-warehouse-run" in text
    assert "integration-warehouse-fault-drill-run" in text
    assert "integration-evidence-merge" in text
    assert "--require-certified" in text
    assert "IntegrationEvidenceCheckResult(" not in text
    assert "IntegrationEvidenceStatus.PASS" not in text
    assert "run_fabric_item_read_check(" not in text


def test_workflow_orders_warehouse_fault_after_normal_commit_prerequisite():
    text = _text()
    normal_pos = text.index("Run approved Warehouse target and marker commit evidence")
    prereq_pos = text.index("Build exact prerequisites for real ambiguous-COMMIT drill")
    fault_pos = text.index("Run approved real ambiguous-COMMIT recovery evidence")
    final_pos = text.index("Strictly merge and require fully certified exact integration evidence")
    assert normal_pos < prereq_pos < fault_pos < final_pos
    assert "--input retained/partials/warehouse-commit.json" in text
    assert "--prerequisite-manifest retained/partials/fault-prerequisites.json" in text


def test_workflow_uploads_only_after_certified_validation_and_exact_identity_check():
    text = _text()
    merge_pos = text.index("Strictly merge and require fully certified exact integration evidence")
    verify_pos = text.index("Verify final exact identities and credential-safe retained output")
    upload_pos = text.index("Upload certified exact-candidate integration evidence")
    assert merge_pos < verify_pos < upload_pos
    assert "integration-evidence-validate" in text
    assert "--require-certified" in text
    assert "integration-evidence-${{ inputs.candidate_git_sha }}" in text
    assert "retention-days: 90" in text


def test_workflow_maps_only_named_runtime_secrets_and_never_retains_secret_values():
    text = _text()
    for name in (
        "CUSTOMER_REPO_TOKEN",
        "FABRIC_ACCESS_TOKEN",
        "CONTROL_PLANE_DATABASE_URL",
        "WAREHOUSE_DATABASE_URL",
        "WAREHOUSE_ADMIN_DATABASE_URL",
    ):
        assert f"{name}: ${{{{ secrets.{name} }}}}" in text
    assert "runner config fabric_access_token_env_var must equal FABRIC_ACCESS_TOKEN" in text or (
        '"fabric_access_token_env_var": "FABRIC_ACCESS_TOKEN"' not in text
        and 'expected_env_names = {' in text
    )
