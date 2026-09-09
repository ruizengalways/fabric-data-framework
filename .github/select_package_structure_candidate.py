from pathlib import Path

CANDIDATE_SHA = "8b118e9bf5c5132738eb1a486a6df3e6589cd16e"
WHEEL_SHA = "7ae26c3bef5cc5e5310c59c8f7182402ed26247b23c04cff4189250d8507e9a2"
FRAMEWORK_CI = "34347024953"
WHEEL_CI = "34347025079"
ARTIFACT_ID = "10102117043"
ARTIFACT_NAME = f"framework-wheel-{CANDIDATE_SHA}"

state_path = Path("docs/internal/STATE.md")
state = state_path.read_text(encoding="utf-8")

old_identity = '''  exact_candidate_source_selected: false\n  release_allowed: false\n'''
new_identity = '''  exact_candidate_source_selected: true\n  release_allowed: false\n'''
assert old_identity in state
state = state.replace(old_identity, new_identity, 1)

old_block = '''candidate_identity:\n  current_source_candidate_git_sha: not_selected_after_packaged_source_change\n  current_source_framework_artifact_sha256: not_selected_after_packaged_source_change\n  integration_inputs_hash: not_yet_constructed\n  integration_inputs_status: blocked_pending_approved_live_DEV_bindings\n  current_source_requires_new_exact_artifact_before_release_claim: true\n  candidate_bytes_must_not_change: true\n  previous_selected_candidate:\n    candidate_git_sha: 1c04216812dd438af58ffda73b22f6ff4d96459b\n    candidate_main_framework_ci_run: 34232496900\n    candidate_main_installed_wheel_run: 34232496960\n    candidate_wheel_artifact_id: 10058373727\n    candidate_wheel_artifact_name: framework-wheel-1c04216812dd438af58ffda73b22f6ff4d96459b\n    candidate_wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl\n    framework_artifact_sha256: 704989633b11ae110d0728dbc168cb85a994f7310aae13682ccd800a2a00b587\n    wheel_sha_verified_against_candidate_json: true\n    wheel_sha_verified_against_sha256sums: true\n    wheel_sha_independently_rehashed: true\n    status: superseded_by_package_structure_refactor\n  historical_candidate:\n    candidate_git_sha: 81f4d5f93983e8288246f5b1521f763091880297\n    framework_artifact_sha256: 845f68d938a39ada944a1a71513b4f46b3a68416a5b53d60dbd10c2f6f95327c\n    status: superseded_for_current_source_by_packaged_runtime_changes\n'''
new_block = f'''candidate_identity:\n  current_source_candidate_git_sha: {CANDIDATE_SHA}\n  current_source_framework_artifact_sha256: {WHEEL_SHA}\n  integration_inputs_hash: not_yet_constructed\n  integration_inputs_status: blocked_pending_approved_live_DEV_bindings\n  current_source_requires_new_exact_artifact_before_release_claim: false\n  candidate_bytes_must_not_change: true\n  selected_candidate:\n    candidate_git_sha: {CANDIDATE_SHA}\n    candidate_main_framework_ci_run: {FRAMEWORK_CI}\n    candidate_main_installed_wheel_run: {WHEEL_CI}\n    candidate_wheel_artifact_id: {ARTIFACT_ID}\n    candidate_wheel_artifact_name: {ARTIFACT_NAME}\n    candidate_wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl\n    framework_artifact_sha256: {WHEEL_SHA}\n    wheel_sha_verified_against_candidate_json: true\n    wheel_sha_verified_against_sha256sums: true\n    wheel_sha_independently_rehashed: true\n    status: selected_not_frozen\n  historical_reconciliation_candidate:\n    candidate_git_sha: 1c04216812dd438af58ffda73b22f6ff4d96459b\n    framework_artifact_sha256: 704989633b11ae110d0728dbc168cb85a994f7310aae13682ccd800a2a00b587\n    status: superseded_by_package_structure_refactor\n  older_historical_candidate:\n    candidate_git_sha: 81f4d5f93983e8288246f5b1521f763091880297\n    framework_artifact_sha256: 845f68d938a39ada944a1a71513b4f46b3a68416a5b53d60dbd10c2f6f95327c\n    status: superseded_for_current_source_by_packaged_runtime_changes\n'''
assert old_block in state
state = state.replace(old_block, new_block, 1)

state = state.replace(
    '''fabric_proof:\n  exact_current_candidate_selected: false\n  current_source_installed_wheel_acceptance: pending_new_exact_main_candidate\n''',
    '''fabric_proof:\n  exact_current_candidate_selected: true\n  current_source_installed_wheel_acceptance: passed\n''',
    1,
)

state = state.replace(
    '''next_boundary:\n  - finish the package-structure refactor with exact-head CI and merge it to main\n  - select and independently verify a new exact post-merge main wheel before any Fabric certification claim\n''',
    '''next_boundary:\n''',
    1,
)

start = state.index("## Previous exact candidate superseded by package refactor")
end = state.index("## Declarative reconciliation")
selected_section = f'''## Selected exact current candidate\n\nThe package-structure refactor merged on `main` at:\n\n```text\n{CANDIDATE_SHA}\n```\n\nThe exact post-merge main gates are:\n\n```text\nframework-ci               {FRAMEWORK_CI}  PASS\ninstalled-wheel-acceptance {WHEEL_CI}  PASS\n```\n\nThe retained framework-ci artifact is:\n\n```text\nartifact id    {ARTIFACT_ID}\nartifact name  {ARTIFACT_NAME}\nwheel          fabric_data_framework-0.4.0-py3-none-any.whl\n```\n\nThe **inner wheel bytes**, not the outer GitHub artifact ZIP, were independently SHA256-hashed after download. That digest exactly matches both `CANDIDATE.json` and `SHA256SUMS`:\n\n```text\nframework_artifact_sha256\n= {WHEEL_SHA}\n```\n\nThis selects the exact executable candidate source/artifact after the package-structure refactor. It does **not** freeze 0.4, construct integration inputs, execute Microsoft Fabric, authorize release, or claim Fabric PASS.\n\nCandidate/evidence identity remains exactly:\n\n```text\nframework_artifact_sha256\n+\nintegration_inputs_hash\n```\n\n`integration_inputs_hash` is still **not yet constructed** because the currently connected tooling does not expose an approved, live-verified isolated DEV workspace/Lakehouse/item binding and Fabric runtime credential set. Do not guess resource IDs, reuse stale fixture IDs, or substitute customer/domain identities.\n\nThe previous reconciliation candidate at `1c04216812dd438af58ffda73b22f6ff4d96459b` / `704989633b11ae110d0728dbc168cb85a994f7310aae13682ccd800a2a00b587` is historical provenance only.\n\n'''
state = state[:start] + selected_section + state[end:]

old_release = '''`0.4.0` is not frozen and not release-authorized. The package-structure refactor invalidates the previous executable candidate, so no exact current candidate is selected until a new successful post-merge `main` wheel is independently verified.\n\nAny packaged-code change invalidates an executable candidate and requires a new exact main wheel. A docs/test-only bookkeeping merge after candidate selection does not change selected wheel bytes. Release promotion must use the exact already-built/certified wheel bytes; no release-time rebuild.\n'''
new_release = '''`0.4.0` is not frozen and not release-authorized. The exact post-refactor executable candidate is selected, but release certification remains blocked at the external live-Fabric binding/evidence boundary.\n\nAny packaged-code change invalidates this executable candidate and requires a new exact main wheel. A docs/test-only bookkeeping merge after candidate selection does not change selected wheel bytes. Release promotion must use the exact already-built/certified wheel bytes; no release-time rebuild.\n'''
assert old_release in state
state = state.replace(old_release, new_release, 1)
state_path.write_text(state, encoding="utf-8")

test_path = Path("tests/test_current_docs_consistency.py")
test = test_path.read_text(encoding="utf-8")
repls = {
    '"exact_candidate_source_selected: false"': '"exact_candidate_source_selected: true"',
    '"current_source_candidate_git_sha: not_selected_after_packaged_source_change"': f'"current_source_candidate_git_sha: {CANDIDATE_SHA}"',
    '"current_source_framework_artifact_sha256: not_selected_after_packaged_source_change"': f'"current_source_framework_artifact_sha256: {WHEEL_SHA}"',
    '"current_source_requires_new_exact_artifact_before_release_claim: true"': '"current_source_requires_new_exact_artifact_before_release_claim: false"',
    '"candidate_main_framework_ci_run: 34232496900"': f'"candidate_main_framework_ci_run: {FRAMEWORK_CI}"',
    '"candidate_main_installed_wheel_run: 34232496960"': f'"candidate_main_installed_wheel_run: {WHEEL_CI}"',
    '"candidate_wheel_artifact_id: 10058373727"': f'"candidate_wheel_artifact_id: {ARTIFACT_ID}"',
    '"candidate_wheel_artifact_name: framework-wheel-1c04216812dd438af58ffda73b22f6ff4d96459b"': f'"candidate_wheel_artifact_name: {ARTIFACT_NAME}"',
    '"framework_artifact_sha256: 704989633b11ae110d0728dbc168cb85a994f7310aae13682ccd800a2a00b587"': f'"framework_artifact_sha256: {WHEEL_SHA}"',
    '"status: superseded_by_package_structure_refactor"': '"status: selected_not_frozen"',
    '"exact_current_candidate_selected: false"': '"exact_current_candidate_selected: true"',
    '"current_source_installed_wheel_acceptance: pending_new_exact_main_candidate"': '"current_source_installed_wheel_acceptance: passed"',
}
for old, new in repls.items():
    if old not in test:
        raise SystemExit(f"missing expected test token: {old}")
    test = test.replace(old, new, 1)
test_path.write_text(test, encoding="utf-8")
