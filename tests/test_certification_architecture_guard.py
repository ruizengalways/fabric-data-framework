from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_LEGACY_TOKENS = (
    "customer_inputs_root",
    "--customer-inputs",
    "customer.compatibility",
    "CUSTOMER_COMPATIBILITY",
    "customer_git_sha",
    "customer_inputs_run_id",
    "CUSTOMER_REPO_TOKEN",
    "ruizengalways/fabric-customer",
)

CANDIDATE_WORKFLOWS = (
    "candidate-integration-inputs.yml",
    "candidate-integration-evidence.yml",
    "candidate-business-path-evidence.yml",
    "candidate-release-proofs.yml",
    "candidate-certification.yml",
)


def _certification_surface_files() -> tuple[Path, ...]:
    paths: list[Path] = []
    for directory in (
        ROOT / "src/fabric_data_framework/certification",
        ROOT / "certification",
    ):
        paths.extend(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix in {".py", ".json"}
        )
    paths.append(ROOT / "src/fabric_data_framework/cli/certification.py")
    paths.extend(ROOT / ".github/workflows" / name for name in CANDIDATE_WORKFLOWS)
    return tuple(sorted(set(paths)))


def test_candidate_certification_surface_has_no_legacy_customer_coupling():
    violations: list[str] = []
    for path in _certification_surface_files():
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_LEGACY_TOKENS:
            if token in text:
                violations.append(f"{path.relative_to(ROOT)}: {token}")

    assert violations == [], "legacy customer coupling reintroduced:\n" + "\n".join(violations)
