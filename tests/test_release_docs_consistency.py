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
        "PR CI PROVEN / PENDING MERGE" + " for candidate-certification",
    )
    for phrase in forbidden:
        assert phrase not in combined


def test_strict_release_proof_merge_docs_remain_merged_main_proven():
    combined = _combined()

    assert "0f70e037806482c677fccae0ce9432504f2a9885" in combined
    assert "33342806854" in combined
    assert "664" in combined
    assert "release_readiness_merge.py" in combined
    assert "release-proofs-merge" in combined
    assert "strict partial proof merge = IMPLEMENTED ON FEATURE BRANCH / CI PENDING" not in combined
    assert "strict partial release-proof merge is implemented on the current feature branch" not in combined.lower()


def test_candidate_release_producer_docs_remain_merged_main_proven():
    combined = _combined()

    assert "5a2edffe5930e9b8a2a79f66f4580ca4d9df2b4e" in combined
    assert "33343223496" in combined
    assert "670" in combined
    assert ".github/workflows/candidate-release-proofs.yml" in combined
    assert "candidate-release-proofs workflow | NOT YET IMPLEMENTED" not in combined
    assert "Candidate release-proof producer workflow | NOT YET IMPLEMENTED" not in combined
    assert "candidate-release-proofs          feature branch implemented / ci pending" not in combined.lower()


def test_business_path_docs_remain_merged_main_proven():
    combined = _combined()

    assert "1632aefe8c1fd71098200c434a1648d0385f4967" in combined
    assert "33346470401" in combined
    assert "717" in combined
    assert ".github/workflows/candidate-business-path-evidence.yml" in combined
    assert "approved_business_path_runner.py" in combined
    assert "business_path_driver.py" in combined
    assert "business_path_evidence.py" in combined
    assert "business_path_plan.py" in combined
    assert "full.replace" in combined
    assert "watermark.scd1" in combined
    assert "watermark.scd2" in combined
    assert "retry.idempotency" in combined
    assert "reconciliation.fail_closed" in combined
    assert "business-path evidence producer workflow | NOT YET IMPLEMENTED" not in combined
    assert "candidate-business-path-evidence   implemented on feature branch / ci pending" not in combined.lower()
    assert "typed evaluator / driver / plan / runner / workflow = IMPLEMENTED / CI PENDING" not in combined


def test_candidate_integration_producer_docs_match_green_pr90_state():
    combined = _combined()

    assert ".github/workflows/candidate-integration-evidence.yml" in combined
    assert "33347382522" in combined
    assert "727" in combined
    assert "PR CI PROVEN / PENDING MERGE" in combined
    assert "IntegrationCheckPhysicalBinding" in combined
    assert "dataset_id" in combined
    assert "authorize_live_mutations" in combined
    assert "authorize_warehouse_session_termination" in combined
    assert "integration-evidence-merge --require-certified" in combined
    assert "integration-evidence-validate --require-certified" in combined

    stale = (
        "candidate-integration-evidence     NOT YET IMPLEMENTED",
        "candidate-integration-evidence.yml        NOT YET IMPLEMENTED",
        "Candidate integration-evidence workflow | NOT YET IMPLEMENTED",
        "candidate-integration-evidence     FEATURE BRANCH IMPLEMENTED / CI PENDING",
        "candidate-integration-evidence workflow       FEATURE BRANCH IMPLEMENTED / CI PENDING",
        "candidate-integration-evidence   implemented on feature branch / ci pending",
        "This producer is not yet implemented",
        "It is **NOT YET IMPLEMENTED**",
    )
    for phrase in stale:
        assert phrase not in combined


def test_release_docs_keep_framework_and_domain_release_identity_distinct():
    combined = _combined()

    assert "domain_release_hash" in combined
    assert "framework_artifact_sha256" in combined
    assert "exact framework candidate wheel SHA256" in combined
    assert "ReleaseManifest.bundle.release_hash" in combined
    assert "IntegrationEvidence.release_hash" in combined
    assert "IntegrationEvidence.domain_release_hash" in combined
    assert "must never be assumed equal" in combined or "not expected to be equal" in combined


def test_release_docs_keep_actual_live_producer_and_release_gaps_explicit():
    combined = _combined()

    assert ".github/workflows/candidate-business-path-evidence.yml" in combined
    assert ".github/workflows/candidate-integration-evidence.yml" in combined
    assert "candidate-business-path-inputs.yml" in combined
    assert "release_allowed = false" in combined or "release_allowed: false" in combined
    assert "not yet frozen" in combined.lower() or "not_frozen" in combined.lower()
    assert "not yet produced" in combined.lower()
    assert "no live run" in combined.lower() or "no live fabric" in combined.lower()
    assert "release-proof/domain" in combined.lower()
