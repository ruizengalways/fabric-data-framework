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
    assert "integration_inputs_run_id:" in text
    assert "environment: ${{ inputs.environment }}" in text
    assert "candidate-integration-evidence must be dispatched at the exact candidate ref" in text
    assert 'git merge-base --is-ancestor "${CANDIDATE_SHA}" origin/main' in text
    assert ".github/workflows/ci.yml" in text
    assert "framework-wheel-${CANDIDATE_SHA}" in text
    assert "candidate_artifact.py verify" in text


def test_workflow_has_no_customer_repo_or_legacy_input_contract():
    text = _text()
    for forbidden in (
        "customer_git_sha",
        "customer_inputs_run_id",
        "CUSTOMER_SHA",
        "CUSTOMER_REPO_TOKEN",
        "fabric-customer",
        "customer-inputs",
        "candidate-business-path-inputs",
        "domain_release_hash",
        "runner.release_hash",
        "manifest.release_hash",
    ):
        assert forbidden not in text


def test_workflow_consumes_framework_owned_integration_inputs():
    text = _text()
    assert ".github/workflows/candidate-integration-inputs.yml" in text
    assert "integration-inputs-${CANDIDATE_SHA}-${CERTIFICATION_ENVIRONMENT}" in text
    assert "integration-inputs/INPUTS.json" in text
    assert "integration-inputs/release-manifest.json" in text
    assert "integration-inputs/runner-config.json" in text
    assert "integration-inputs/project/config/datasets" in text
    assert "control-plane-external-evidence.json" in text
    assert "copy-run.json" in text
    assert "spark-run.json" in text
    assert "warehouse-run.json" in text
    assert "warehouse-fault-run.json" in text


def test_workflow_binds_framework_artifact_and_integration_inputs_independently():
    text = _text()
    assert "runner.framework_artifact_sha256" in text
    assert "runner.integration_inputs_hash" in text
    assert "integration_inputs_hash=os.environ[\"INTEGRATION_INPUTS_HASH\"]" in text
    assert 'manifest.framework_artifact_sha256 != os.environ["CANDIDATE_WHEEL_SHA256"]' in text
    assert 'manifest.integration_inputs_hash != os.environ["INTEGRATION_INPUTS_HASH"]' in text


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


def test_workflow_uses_approved_execution_commands_and_staged_merge():
    text = _text()
    assert "integration-item-smoke-run" in text
    assert "integration-control-plane-certify-run" in text
    assert "integration-pipeline-run" in text
    assert text.count("integration-capture-run") == 2
    assert "integration-warehouse-run" in text
    assert "integration-warehouse-fault-drill-run" in text
    assert "integration-evidence-merge" in text
    assert "integration-evidence-validate" in text
    assert "--require-certified" in text
    assert "IntegrationEvidenceCheckResult(" not in text
    assert "status=IntegrationEvidenceStatus.PASS" not in text


def test_workflow_orders_warehouse_fault_after_normal_commit_prerequisite():
    text = _text()
    normal_pos = text.index("Run approved Warehouse commit evidence")
    prereq_pos = text.index("Build exact fault prerequisites")
    fault_pos = text.index("Run approved real ambiguous-COMMIT evidence")
    final_pos = text.index("Strictly merge and require certified exact integration evidence")
    assert normal_pos < prereq_pos < fault_pos < final_pos
    assert "--input retained/partials/warehouse-commit.json" in text
    assert "--prerequisite-manifest retained/partials/fault-prerequisites.json" in text


def test_workflow_maps_only_runtime_secrets_needed_by_framework_certification():
    text = _text()
    for name in (
        "FABRIC_ACCESS_TOKEN",
        "CONTROL_PLANE_DATABASE_URL",
        "WAREHOUSE_DATABASE_URL",
        "WAREHOUSE_ADMIN_DATABASE_URL",
    ):
        assert f"{name}: ${{{{ secrets.{name} }}}}" in text
    assert "CUSTOMER_REPO_TOKEN" not in text
    assert "assert_safe_retained_text" in text


def test_workflow_uploads_environment_scoped_exact_candidate_evidence():
    text = _text()
    merge_pos = text.index("Strictly merge and require certified exact integration evidence")
    verify_pos = text.index("Verify final exact identities and safe retained output")
    upload_pos = text.index("Upload certified exact-candidate integration evidence")
    assert merge_pos < verify_pos < upload_pos
    assert "integration-evidence-${{ inputs.candidate_git_sha }}-${{ inputs.environment }}" in text
    assert "retention-days: 90" in text
