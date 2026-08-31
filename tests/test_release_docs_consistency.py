from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = (
    ROOT / "docs/machine/STATE.md",
    ROOT / "docs/machine/CAPABILITIES.md",
    ROOT / "docs/machine/IMPLEMENTATION_MAP.md",
    ROOT / "docs/machine/APPROVED_EVIDENCE.md",
    ROOT / "docs/machine/BUSINESS_PATH_EVIDENCE.md",
    ROOT / "docs/machine/RELEASE_READINESS.md",
    ROOT / "docs/machine/HISTORY.md",
    ROOT / "docs/human/RELEASE_CANDIDATE.md",
)


def _combined() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in CANONICAL)


def test_candidate_certification_docs_do_not_regress_to_stale_state():
    combined = _combined()
    forbidden = (
        "future `.github/workflows/candidate-certification.yml`",
        "Candidate-certification workflow / certified readiness artifact | NOT YET IMPLEMENTED",
        "candidate-certification workflow / evidence packaging that consumes",
    )
    for phrase in forbidden:
        assert phrase not in combined


def test_strict_release_proof_merge_docs_remain_merged_main_proven():
    combined = _combined()
    assert "0f70e037806482c677fccae0ce9432504f2a9885" in combined
    assert "33342806854" in combined
    assert "release_readiness_merge.py" in combined
    assert "release-proofs-merge" in combined
    assert "strict partial proof merge = IMPLEMENTED ON FEATURE BRANCH / CI PENDING" not in combined


def test_candidate_release_producer_docs_remain_merged_main_proven():
    combined = _combined()
    assert "5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e" in combined
    assert "33343223496" in combined
    assert ".github/workflows/candidate-release-proofs.yml" in combined
    assert "candidate-release-proofs workflow | NOT YET IMPLEMENTED" not in combined
    assert "Candidate release-proof producer workflow | NOT YET IMPLEMENTED" not in combined


def test_business_path_docs_remain_merged_main_proven():
    combined = _combined()
    assert "1632aefe8c1fd71098200c434a1648d0385f4967" in combined
    assert "33346470401" in combined
    assert ".github/workflows/candidate-business-path-evidence.yml" in combined
    assert "approved_business_path_runner.py" in combined
    assert "business_path_driver.py" in combined
    assert "business_path_evidence.py" in combined
    assert "business_path_plan.py" in combined
    for gate in (
        "full.replace",
        "watermark.scd1",
        "watermark.scd2",
        "retry.idempotency",
        "reconciliation.fail_closed",
    ):
        assert gate in combined
    assert "business-path evidence producer workflow | NOT YET IMPLEMENTED" not in combined


def test_candidate_integration_producer_docs_match_merged_pr90_state():
    combined = _combined()
    assert ".github/workflows/candidate-integration-evidence.yml" in combined
    assert "7e12a320e73aa06f3e80f57e3deed14a6cc7add0" in combined
    assert "33349005817" in combined
    assert "33349064335" in combined
    assert "728" in combined
    assert "IntegrationCheckPhysicalBinding" in combined
    assert "dataset_id" in combined
    assert "authorize_live_mutations" in combined
    assert "authorize_warehouse_session_termination" in combined
    assert "integration-evidence-merge --require-certified" in combined
    assert "integration-evidence-validate --require-certified" in combined


def test_customer_input_contract_docs_match_merged_customer_state():
    combined = _combined()
    assert "candidate-business-path-inputs.yml" in combined
    assert "cda90f1c02fc9606aa64d2d1bd13f2ab89628aab" in combined
    assert "31f3f506bc1c16a445652de2ad48fe512cfec10a" in combined
    assert "9ddc11405de329fb647fb21b1217d1015e0fa3f5" in combined
    assert "c4097dcc1319f382eb370e9c4d46dcbed7bb383b" in combined
    assert "f83dc722da479971cdfd68d883291646c433ec15" in combined
    assert "33368266794" in combined
    assert "33368266793" in combined
    assert "fabric-data-framework==0.3.0" in combined
    assert "actual_selected_candidate_input_artifact_retained: false" in combined
    assert "control_plane_external_evidence_incomplete" in combined
    assert "control_plane_external_evidence_not_review_bound" in combined
    assert "warehouse_real_fault_controller_not_configured" in combined


def test_release_docs_keep_framework_and_domain_release_identity_distinct():
    combined = _combined()
    assert "domain_release_hash" in combined
    assert "framework_artifact_sha256" in combined
    assert "exact framework candidate wheel SHA256" in combined
    assert "ReleaseManifest.bundle.release_hash" in combined
    assert "ReleaseReadinessProofBundle.domain_release_hash" in combined
    assert "ReleaseReadinessReport.domain_release_hash" in combined
    assert "IntegrationEvidence.release_hash" in combined
    assert "IntegrationEvidence.domain_release_hash" in combined
    assert "must never be assumed equal" in combined or "not expected to be equal" in combined


def test_domain_release_binding_docs_keep_pr92_as_merged_identity_milestone():
    combined = _combined()
    assert "PR #92" in combined
    assert "d5eed17f2ec2f869b4e3a448597e6d8d600568ea" in combined
    assert "33356959856" in combined
    assert "33357032461" in combined
    assert "734" in combined
    assert "business_path_release_proof.py" in combined
    assert "MERGED + MAIN CI PROVEN" in combined

    stale = (
        "release-proof/domain identity machine binding  REQUIRED BEFORE CANDIDATE FREEZE",
        "release-proof/domain hash binding  REQUIRED BEFORE CANDIDATE FREEZE",
        "customer business-path inputs      not yet implemented / not retained",
        "Customer business-path/integration input producer | `fabric-customer/.github/workflows/candidate-business-path-inputs.yml` | NOT YET IMPLEMENTED",
        "release-proof/domain binding       PR #92 PR CI PROVEN / PENDING MERGE",
        "business-path domain proof packaging                               = PR #92 PR CI PROVEN / PENDING MERGE",
        "status:         PR CI PROVEN / PENDING MERGE",
    )
    for phrase in stale:
        assert phrase not in combined


def test_pr97_is_current_code_and_candidate_capable_artifact_baseline():
    combined = _combined()
    state = (ROOT / "docs/machine/STATE.md").read_text(encoding="utf-8")

    assert "pull_request: 97" in state
    assert "3b39448fcefbeba7a66469c847542c3255e462ff" in combined
    assert "33377064054" in combined
    assert "33377208722" in combined
    assert "748" in combined
    assert "5d0c2f1f4348543bb8b9da0748788cc68b3ccbfed96fd73cec11ad7f475c0517" in combined
    assert "9752314929" in combined
    assert "selected_as_frozen_candidate: false" in state
    assert "readiness_required_blockers: 15" in state

    # PR #94 remains a historical identity-chain baseline, but is no longer current.
    assert "pull_request: 94" in state
    assert "abc8b3a2b80b3f6babf88fdc2347a3bfe69be356" in combined
    assert "d763cd4410a69ff6a83c492f3a546d096502c96c87eeddb37c2ae9404557e7b7" in combined


def test_manual_admin_certification_boundary_is_explicit():
    state = (ROOT / "docs/machine/STATE.md").read_text(encoding="utf-8")
    assert ".github/workflows/candidate-admin-certification.yml" in state
    assert "candidate_manifest_auto_identity: true" in state
    assert "github_admin_override_requires_fabric_connectivity: false" in state
    assert "admin_override_record_retained: false" in state
    assert "admin_override_fabricates_missing_live_evidence: false" in state
    assert "existing_framework_release_accepts_admin_override_as_release_readiness: false" in state
    assert "existing_evidence_based_candidate_certification_unchanged: true" in state


def test_business_path_runner_cannot_be_documented_as_candidate_proof_packager():
    combined = _combined()
    assert "business_path_release_proof.py" in combined
    assert "sole business-path candidate proof packaging owner" in combined or "exclusively owned by `business_path_release_proof.py`" in combined
    assert "partial_proof_bundle" in combined
    assert "write_business_path_partial_proof_bundle" in combined
    assert "removed" in combined.lower()
    assert "runner execution report -> candidate proof without exact ReleaseManifest" in combined


def test_latest_candidate_capable_artifact_is_not_frozen():
    state = (ROOT / "docs/machine/STATE.md").read_text(encoding="utf-8")
    assert "candidate_status: not_frozen" in state
    assert "selected_as_frozen_candidate: false" in state
    assert "release_allowed: false" in state
    assert "readiness_required_blockers: 15" in state


def test_release_docs_keep_actual_live_and_release_gaps_explicit():
    combined = _combined()
    assert ".github/workflows/candidate-business-path-evidence.yml" in combined
    assert ".github/workflows/candidate-integration-evidence.yml" in combined
    assert "candidate-business-path-inputs.yml" in combined
    assert "release_allowed = false" in combined or "release_allowed: false" in combined
    assert "not yet frozen" in combined.lower() or "not_frozen" in combined.lower()
    assert "not yet produced" in combined.lower()
    assert "no live run" in combined.lower() or "no retained live" in combined.lower()
    assert "immutable v0.4.0" in combined
