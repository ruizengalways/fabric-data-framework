from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/candidate-release-proofs.yml"


def test_candidate_release_proofs_workflow_is_exact_candidate_fail_closed_aggregation():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "candidate_run_id:" in workflow
    assert "candidate_git_sha:" in workflow
    assert "candidate_wheel_sha256:" in workflow
    assert "customer_git_sha:" in workflow
    assert "business_path_evidence_run_id:" in workflow
    inputs = workflow.split("    inputs:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "domain_release_hash:" not in inputs
    assert 'os.environ["GITHUB_SHA"] != os.environ["CANDIDATE_SHA"]' in workflow
    assert 'ref: ${{ inputs.candidate_git_sha }}' in workflow
    assert 'framework-wheel-${CANDIDATE_SHA}' in workflow
    assert "candidate_artifact.py verify" in workflow
    assert '"test-python-3.11"' in workflow
    assert '"test-python-3.13"' in workflow
    assert '"build-wheel"' in workflow
    assert '"release-readiness-contract"' in workflow
    assert "candidate-ci-jobs.json" in workflow
    assert "printf '%s' \"${JOBS_JSON}\" | python - <<'PY'" not in workflow


def test_candidate_release_proofs_workflow_revalidates_customer_against_exact_wheel():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "repository: ruizengalways/fabric-customer" in workflow
    assert 'ref: ${{ inputs.customer_git_sha }}' in workflow
    assert 'git -C customer merge-base --is-ancestor "${CUSTOMER_SHA}" origin/main' in workflow
    assert "fabric-framework project-validate customer" in workflow
    assert "fabric-framework project-init retained/customer-compat/health-project --domain health" in workflow
    assert "--framework-next" in workflow
    assert 'assert report["dataset_count"] == 100' in workflow
    assert 'assert report["semantic_selection_count"] == 100' in workflow
    assert 'assert counts("capture_strategies") == {"CDC": 10, "FULL": 50, "WATERMARK": 40}' in workflow
    assert 'assert counts("apply_strategies") == {"REPLACE": 50, "SCD1": 20, "SCD2": 20, "UPSERT": 10}' in workflow
    assert "pip install -e" not in workflow


def test_candidate_release_proofs_authenticates_domain_hash_from_retained_customer_release():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "customer-release-manifest.json" in workflow
    assert "ReleaseManifest.model_validate_json" in workflow
    assert 'manifest.bundle.domain_git_sha.lower() != os.environ["CUSTOMER_SHA"]' in workflow
    assert 'proof.domain_release_hash != manifest.bundle.release_hash' in workflow
    assert 'echo "DOMAIN_RELEASE_HASH=${DOMAIN_RELEASE_HASH}" >> "${GITHUB_ENV}"' in workflow
    assert 'domain_release_hash=os.environ["DOMAIN_RELEASE_HASH"]' in workflow
    assert 'bundle.domain_release_hash != os.environ["DOMAIN_RELEASE_HASH"]' in workflow
    assert "cp retained/business/customer-release-manifest.json retained/final/customer-release-manifest.json" in workflow


def test_candidate_release_proofs_workflow_only_creates_static_passes_it_observed():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'gate_id="source.tests"' in workflow
    assert 'gate_id="wheel.integrity"' in workflow
    assert 'gate_id="customer.compatibility"' in workflow
    assert 'gate_id="full.replace"' not in workflow
    assert 'gate_id="watermark.scd1"' not in workflow
    assert 'gate_id="watermark.scd2"' not in workflow
    assert 'gate_id="retry.idempotency"' not in workflow
    assert 'gate_id="reconciliation.fail_closed"' not in workflow


def test_candidate_release_proofs_workflow_requires_live_business_path_artifact_then_strict_merge():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert '".github/workflows/candidate-business-path-evidence.yml"' in workflow
    assert 'business-path-release-proofs-${CANDIDATE_SHA}' in workflow
    assert "business-path-release-proofs.json" in workflow
    assert "fabric-framework release-proofs-merge" in workflow
    assert "required_non_integration" in workflow
    assert "ReleaseReadinessStatus.PASS" in workflow
    assert 'name: release-proofs-${{ inputs.candidate_git_sha }}' in workflow
    assert "retention-days: 90" in workflow
    assert "python -m pip wheel" not in workflow
    assert "gh release create" not in workflow
    assert "git tag" not in workflow
