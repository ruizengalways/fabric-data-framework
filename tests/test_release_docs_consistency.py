from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = (
    ROOT / "docs/machine/STATE.md",
    ROOT / "docs/machine/CAPABILITIES.md",
    ROOT / "docs/machine/IMPLEMENTATION_MAP.md",
    ROOT / "docs/machine/RELEASE_READINESS.md",
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
        "PR CI PROVEN / PENDING MERGE",
        "PR CI proven and pending merge/main checkpoint",
        "PR CI evidence pending merge/main checkpoint",
        "requires PR CI/merge before it can be called proven",
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


def test_candidate_release_producer_docs_match_current_feature_branch_boundary():
    combined = _combined()

    assert ".github/workflows/candidate-release-proofs.yml" in combined
    assert "source.tests" in combined
    assert "wheel.integrity" in combined
    assert "customer.compatibility" in combined
    assert ".github/workflows/candidate-business-path-evidence.yml" in combined
    assert "candidate-release-proofs workflow | NOT YET IMPLEMENTED" not in combined
    assert "Candidate release-proof producer workflow | NOT YET IMPLEMENTED" not in combined


def test_release_docs_keep_actual_live_producer_and_release_gaps_explicit():
    combined = _combined()

    assert ".github/workflows/candidate-business-path-evidence.yml" in combined
    assert ".github/workflows/candidate-integration-evidence.yml" in combined
    assert "release_allowed = false" in combined or "release_allowed: false" in combined
    assert "not yet frozen" in combined.lower() or "not_frozen" in combined.lower()
    assert "not yet produced" in combined.lower()
