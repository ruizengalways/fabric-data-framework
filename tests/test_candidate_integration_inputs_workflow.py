from pathlib import Path


WORKFLOW = Path(".github/workflows/candidate-integration-inputs.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_builds_inputs_from_exact_framework_candidate():
    text = _text()
    assert "workflow_dispatch:" in text
    assert "candidate_run_id:" in text
    assert "candidate_git_sha:" in text
    assert "candidate_wheel_sha256:" in text
    assert "candidate-integration-inputs must be dispatched at the exact candidate ref" in text
    assert "framework-wheel-${CANDIDATE_SHA}" in text
    assert "candidate_artifact.py verify" in text
    assert "certification/build_integration_inputs.py" in text
    assert "--framework-wheel" in text


def test_workflow_owns_non_secret_fabric_bindings_without_customer_repo():
    text = _text()
    for expected in (
        "workspace_id:",
        "item_read_id:",
        "pipeline_item_id:",
        "copy_job_id:",
        "spark_job_id:",
        "control_plane_profile:",
    ):
        assert expected in text
    for forbidden in (
        "fabric-customer",
        "customer_git_sha",
        "customer_inputs_run_id",
        "CUSTOMER_REPO_TOKEN",
        "customer-inputs",
    ):
        assert forbidden not in text


def test_workflow_retains_exact_integration_inputs_hash():
    text = _text()
    assert 'payload["integration_inputs_hash"]' in text
    assert "integration-inputs-${{ inputs.candidate_git_sha }}-${{ inputs.environment }}" in text
    assert "retention-days: 90" in text
