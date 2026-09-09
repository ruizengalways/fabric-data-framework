from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PATH_REPLACEMENTS = [
    ("src/fabric_data_framework/execution/dataset_runner.py", "src/fabric_data_framework/execution/watermark_scd2.py"),
    ("src/fabric_data_framework/quality/reconciliation_engine.py", "src/fabric_data_framework/quality/reconciliation/engine.py"),
    ("src/fabric_data_framework/quality/reconciliation.py", "src/fabric_data_framework/quality/reconciliation/scd2.py"),
    ("src/fabric_data_framework/quality/full_refresh.py", "src/fabric_data_framework/quality/reconciliation/full_replace.py"),
    ("src/fabric_data_framework/quality/append.py", "src/fabric_data_framework/quality/reconciliation/append.py"),
    ("src/fabric_data_framework/quality/snapshot_diff.py", "src/fabric_data_framework/quality/reconciliation/snapshot_diff.py"),
    ("quality/reconciliation_engine.py", "quality/reconciliation/engine.py"),
    ("quality/reconciliation.py", "quality/reconciliation/scd2.py"),
    ("quality/full_refresh.py", "quality/reconciliation/full_replace.py"),
    ("quality/append.py", "quality/reconciliation/append.py"),
    ("quality/snapshot_diff.py", "quality/reconciliation/snapshot_diff.py"),
    ("execution/dataset_runner.py", "execution/watermark_scd2.py"),
    ("evidence/integration_evidence_merge.py", "evidence/integration/merge.py"),
    ("evidence/integration_evidence_rerun.py", "evidence/integration/rerun.py"),
    ("evidence/integration_evidence.py", "evidence/integration/evidence.py"),
    ("evidence/integration_checks.py", "evidence/integration/checks.py"),
    ("evidence/integration_runner.py", "evidence/integration/runner.py"),
    ("evidence/approved_capture_runner.py", "evidence/integration/approved/capture.py"),
    ("evidence/approved_control_plane_runner.py", "evidence/integration/approved/control_plane.py"),
    ("evidence/approved_pipeline_runner.py", "evidence/integration/approved/pipeline.py"),
    ("evidence/approved_warehouse_fault_runner.py", "evidence/integration/approved/warehouse_fault.py"),
    ("evidence/approved_warehouse_runner.py", "evidence/integration/approved/warehouse.py"),
    ("evidence/approved_business_path_runner.py", "evidence/business_paths/approved_runner.py"),
    ("evidence/business_path_driver.py", "evidence/business_paths/driver.py"),
    ("evidence/business_path_evidence.py", "evidence/business_paths/evidence.py"),
    ("evidence/business_path_plan.py", "evidence/business_paths/plan.py"),
    ("evidence/business_path_release_proof.py", "evidence/business_paths/release_proof.py"),
    ("evidence/release_readiness_merge.py", "evidence/release/merge.py"),
    ("evidence/release_readiness.py", "evidence/release/readiness.py"),
    ("evidence/candidate_certification.py", "evidence/release/candidate_certification.py"),
    ("certification/fabric_assets.py", "certification/fabric/assets.py"),
    ("certification/bindings.py", "certification/fabric/bindings.py"),
    ("certification/fabric_job.py", "certification/fabric/fabric_job.py"),
    ("certification/pipeline_child.py", "certification/fabric/pipeline_child.py"),
    ("certification/smoke_installed_wheel.py", "certification_harness/smoke_installed_wheel.py"),
    ("certification/build_integration_inputs.py", "certification_harness/build_integration_inputs.py"),
    ("certification/integration_project", "certification_harness/integration_project"),
]

BARE_EVIDENCE_REPLACEMENTS = [
    ("approved_capture_runner.py", "integration/approved/capture.py"),
    ("approved_control_plane_runner.py", "integration/approved/control_plane.py"),
    ("approved_pipeline_runner.py", "integration/approved/pipeline.py"),
    ("approved_warehouse_fault_runner.py", "integration/approved/warehouse_fault.py"),
    ("approved_warehouse_runner.py", "integration/approved/warehouse.py"),
    ("approved_business_path_runner.py", "business_paths/approved_runner.py"),
    ("business_path_driver.py", "business_paths/driver.py"),
    ("business_path_evidence.py", "business_paths/evidence.py"),
    ("business_path_plan.py", "business_paths/plan.py"),
    ("business_path_release_proof.py", "business_paths/release_proof.py"),
    ("integration_evidence_merge.py", "integration/merge.py"),
    ("integration_evidence_rerun.py", "integration/rerun.py"),
    ("integration_evidence.py", "integration/evidence.py"),
    ("integration_checks.py", "integration/checks.py"),
    ("integration_runner.py", "integration/runner.py"),
    ("release_readiness_merge.py", "release/merge.py"),
    ("release_readiness.py", "release/readiness.py"),
    ("candidate_certification.py", "release/candidate_certification.py"),
]


def apply_replacements(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    updated = text
    for old, new in replacements:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")


# Canonical documentation and package navigation must point only at the hard-cut paths.
for path in sorted((ROOT / "docs").rglob("*.md")):
    apply_replacements(path, PATH_REPLACEMENTS)
for path in sorted((ROOT / "src" / "fabric_data_framework").rglob("README.md")):
    apply_replacements(path, PATH_REPLACEMENTS)
for relative in ("README.md", "CONTRIBUTING.md"):
    path = ROOT / relative
    if path.exists():
        apply_replacements(path, PATH_REPLACEMENTS)

# The evidence package overview historically used bare filenames; make its ownership
# map explicit now that evidence is grouped into bounded-context subpackages.
evidence_readme = ROOT / "src/fabric_data_framework/evidence/README.md"
if evidence_readme.exists():
    apply_replacements(evidence_readme, BARE_EVIDENCE_REPLACEMENTS)

state = ROOT / "docs/internal/STATE.md"
text = state.read_text(encoding="utf-8")
state_replacements = [
    ("updated: 2026-09-08", "updated: 2026-09-09"),
    ("exact_candidate_source_selected: true", "exact_candidate_source_selected: false"),
    ("current_source_candidate_git_sha: 1c04216812dd438af58ffda73b22f6ff4d96459b", "current_source_candidate_git_sha: not_selected_after_packaged_source_change"),
    ("current_source_framework_artifact_sha256: 704989633b11ae110d0728dbc168cb85a994f7310aae13682ccd800a2a00b587", "current_source_framework_artifact_sha256: not_selected_after_packaged_source_change"),
    ("current_source_requires_new_exact_artifact_before_release_claim: false", "current_source_requires_new_exact_artifact_before_release_claim: true"),
    ("  selected_candidate:\n", "  previous_selected_candidate:\n"),
    ("    status: selected_not_frozen", "    status: superseded_by_package_structure_refactor"),
    ("  exact_current_candidate_selected: true", "  exact_current_candidate_selected: false"),
    ("  current_source_installed_wheel_acceptance: passed", "  current_source_installed_wheel_acceptance: pending_new_exact_main_candidate"),
    ("  - preserve selected candidate bytes at source 1c04216812dd438af58ffda73b22f6ff4d96459b and wheel SHA256 704989633b11ae110d0728dbc168cb85a994f7310aae13682ccd800a2a00b587", "  - finish the package-structure refactor with exact-head CI and merge it to main\n  - select and independently verify a new exact post-merge main wheel before any Fabric certification claim"),
]
for old, new in state_replacements:
    if old not in text:
        raise SystemExit(f"STATE expected text not found: {old!r}")
    text = text.replace(old, new, 1)

start = text.index("## Selected exact current candidate")
end = text.index("## Declarative reconciliation", start)
historical_section = """## Previous exact candidate superseded by package refactor

The reconciliation runtime candidate at source `1c04216812dd438af58ffda73b22f6ff4d96459b` and inner wheel SHA256 `704989633b11ae110d0728dbc168cb85a994f7310aae13682ccd800a2a00b587` remains retained historical provenance. Its post-merge main gates were `framework-ci` run `34232496900` and `installed-wheel-acceptance` run `34232496960`, with framework wheel artifact id `10058373727`.

PR #136 changes packaged `src/` paths and therefore changes wheel bytes. The previous wheel is **not** the current executable candidate and must not be used for a new Fabric certification or release claim. A new exact candidate may be selected only from the successful post-merge `main` artifact after this refactor lands, using the inner `.whl` SHA256 verified against both `CANDIDATE.json` and `SHA256SUMS`.

Candidate/evidence identity remains exactly:

```text
framework_artifact_sha256
+
integration_inputs_hash
```

`integration_inputs_hash` is still **not yet constructed** because the currently connected tooling does not expose an approved, live-verified isolated DEV workspace/Lakehouse/item binding and Fabric runtime credential set. Do not guess resource IDs, reuse stale fixture IDs, or substitute customer/domain identities.

"""
text = text[:start] + historical_section + text[end:]
text = text.replace(
    "`0.4.0` is not frozen and not release-authorized. The exact current candidate is selected, but release certification is blocked at the external live-Fabric binding/evidence boundary.",
    "`0.4.0` is not frozen and not release-authorized. The package-structure refactor invalidates the previous executable candidate, so no exact current candidate is selected until a new successful post-merge `main` wheel is independently verified.",
)
text = text.replace(
    "Any future packaged-code change invalidates this executable candidate and requires a new exact main wheel. A docs/test-only bookkeeping merge does not change the selected wheel bytes. Release promotion must use the exact already-built/certified wheel bytes; no release-time rebuild.",
    "Any packaged-code change invalidates an executable candidate and requires a new exact main wheel. A docs/test-only bookkeeping merge after candidate selection does not change selected wheel bytes. Release promotion must use the exact already-built/certified wheel bytes; no release-time rebuild.",
)
state.write_text(text, encoding="utf-8")

# Keep the docs contract test aligned with the fail-closed candidate-invalidated state.
test_path = ROOT / "tests/test_current_docs_consistency.py"
test_text = test_path.read_text(encoding="utf-8")
test_replacements = [
    ("r\"(?:src|tests|certification|release)/", "r\"(?:src|tests|certification|certification_harness|release)/"),
    ('"exact_candidate_source_selected: true",', '"exact_candidate_source_selected: false",'),
    ('"current_source_candidate_git_sha: 1c04216812dd438af58ffda73b22f6ff4d96459b",', '"current_source_candidate_git_sha: not_selected_after_packaged_source_change",'),
    ('"current_source_framework_artifact_sha256: 704989633b11ae110d0728dbc168cb85a994f7310aae13682ccd800a2a00b587",', '"current_source_framework_artifact_sha256: not_selected_after_packaged_source_change",'),
    ('"current_source_requires_new_exact_artifact_before_release_claim: false",', '"current_source_requires_new_exact_artifact_before_release_claim: true",'),
    ('"status: selected_not_frozen",', '"status: superseded_by_package_structure_refactor",'),
    ('"exact_current_candidate_selected: true",', '"exact_current_candidate_selected: false",'),
    ('"current_source_installed_wheel_acceptance: passed",', '"current_source_installed_wheel_acceptance: pending_new_exact_main_candidate",'),
    ('assert "quality/reconciliation_engine.py" in implementation_map', 'assert "quality/reconciliation/engine.py" in implementation_map'),
]
for old, new in test_replacements:
    if old not in test_text:
        raise SystemExit(f"docs consistency expected text not found: {old!r}")
    test_text = test_text.replace(old, new, 1)
test_path.write_text(test_text, encoding="utf-8")
