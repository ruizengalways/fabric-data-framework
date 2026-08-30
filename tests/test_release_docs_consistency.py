from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = (
    ROOT / "docs/machine/CAPABILITIES.md",
    ROOT / "docs/machine/IMPLEMENTATION_MAP.md",
    ROOT / "docs/machine/RELEASE_READINESS.md",
    ROOT / "docs/human/RELEASE_CANDIDATE.md",
)


def test_candidate_certification_docs_do_not_regress_to_preimplementation_state():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in CANONICAL)

    forbidden = (
        "future `.github/workflows/candidate-certification.yml`",
        "Candidate-certification workflow / certified readiness artifact | NOT YET IMPLEMENTED",
        "candidate-certification workflow / evidence packaging that consumes",
    )
    for phrase in forbidden:
        assert phrase not in combined


def test_candidate_certification_docs_keep_real_upstream_producer_gaps_explicit():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in CANONICAL)

    assert ".github/workflows/candidate-release-proofs.yml" in combined
    assert ".github/workflows/candidate-integration-evidence.yml" in combined
    assert "release_allowed = false" in combined or "release_allowed: false" in combined
    assert "not yet frozen" in combined.lower() or "not_frozen" in combined.lower()
