from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "src/fabric_data_framework/evidence/approved_business_path_runner.py"
PACKAGER = ROOT / "src/fabric_data_framework/evidence/business_path_release_proof.py"
CLI = ROOT / "src/fabric_data_framework/cli/business_path.py"


def test_approved_runner_cannot_package_unbound_candidate_proof():
    source = RUNNER.read_text(encoding="utf-8")
    assert "ReleaseReadinessProofBundle" not in source
    assert "partial_proof_bundle" not in source
    assert "write_business_path_partial_proof_bundle" not in source


def test_exact_release_manifest_is_required_by_candidate_proof_packager():
    source = PACKAGER.read_text(encoding="utf-8")
    assert "ReleaseManifest" in source
    assert "release_manifest.bundle.release_hash" in source
    assert "domain_release_hash=release_manifest.bundle.release_hash" in source
    assert "build_business_path_partial_proof_bundle" in source


def test_cli_uses_only_domain_bound_candidate_proof_writer():
    source = CLI.read_text(encoding="utf-8")
    assert "write_business_path_release_proof_bundle" in source
    assert "write_business_path_partial_proof_bundle" not in source
