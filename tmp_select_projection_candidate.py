from pathlib import Path

STATE = Path("docs/internal/STATE.md")
TEST = Path("tests/test_current_docs_consistency.py")

SOURCE = "5d4b69702acc3e362a52a3b890cc7096f2acc02a"
WHEEL_SHA = "5e19368c5c63e48e78abb47aa095638d4f0b39c831fc909c37df6817ed7e21a8"
FRAMEWORK_RUN = "34689765814"
INSTALLED_RUN = "34689765815"
ARTIFACT_ID = "10297211433"
ARTIFACT_NAME = f"framework-wheel-{SOURCE}"
WHEEL = "fabric_data_framework-0.4.0-py3-none-any.whl"
ZIP_DIGEST = "sha256:e3e4ef03e8cbb500c1f7eeb2bd8e5af2aae6bd3b3de91c4a7ac55ab8e901547e"


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


state = STATE.read_text(encoding="utf-8")
for old, new, label in (
    ("  exact_candidate_source_selected: false", "  exact_candidate_source_selected: true", "release selected flag"),
    ("  current_source_candidate_git_sha: not_selected_after_projection_production_runtime", f"  current_source_candidate_git_sha: {SOURCE}", "source candidate"),
    ("  current_source_framework_artifact_sha256: not_selected_after_projection_production_runtime", f"  current_source_framework_artifact_sha256: {WHEEL_SHA}", "wheel identity"),
    ("  current_source_requires_new_exact_artifact_before_release_claim: true", "  current_source_requires_new_exact_artifact_before_release_claim: false", "artifact requirement"),
    ("  candidate_bytes_must_not_change: false", "  candidate_bytes_must_not_change: true", "candidate immutability"),
    ("  exact_current_candidate_selected: false", "  exact_current_candidate_selected: true", "fabric candidate flag"),
    ("  current_source_installed_wheel_acceptance: not_run_for_new_current_source", f"  current_source_installed_wheel_acceptance: passed_main_run_{INSTALLED_RUN}", "installed wheel proof"),
):
    state = once(state, old, new, label)

old_selected = """  selected_candidate:\n    status: not_selected_after_projection_production_runtime\n  superseded_second_review_candidate:\n"""
new_selected = f"""  selected_candidate:\n    candidate_git_sha: {SOURCE}\n    candidate_main_framework_ci_run: {FRAMEWORK_RUN}\n    candidate_main_installed_wheel_run: {INSTALLED_RUN}\n    candidate_wheel_artifact_id: {ARTIFACT_ID}\n    candidate_wheel_artifact_name: {ARTIFACT_NAME}\n    candidate_wheel_filename: {WHEEL}\n    framework_artifact_sha256: {WHEEL_SHA}\n    wheel_sha_verified_against_candidate_json: true\n    wheel_sha_verified_against_sha256sums: true\n    wheel_sha_independently_rehashed: true\n    github_artifact_zip_digest: {ZIP_DIGEST}\n    github_artifact_zip_digest_role: provenance_only_not_candidate_identity\n    status: selected_not_frozen\n  superseded_second_review_candidate:\n"""
state = once(state, old_selected, new_selected, "selected candidate block")

old_next = """next_boundary:\n  - merge the projection production runtime only after exact PR-head framework and installed-wheel gates pass\n  - verify post-merge main framework and installed-wheel gates\n  - download and independently verify the exact post-merge main wheel bytes\n  - select the new exact executable candidate before any live Fabric certification\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n  - bootstrap/read back framework-owned certification assets using the newly selected exact wheel\n"""
new_next = """next_boundary:\n  - keep the exact selected candidate wheel bytes immutable while Fabric certification is pending\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n  - bootstrap/read back framework-owned certification assets using the exact selected wheel\n"""
state = once(state, old_next, new_next, "next boundary")

marker = "## Superseded second-independent-review candidate\n"
selected_section = f"""## Selected projection-production candidate\n\nThe production current-projection runtime merged on `main` at:\n\n```text\n{SOURCE}\n```\n\nThe exact post-merge main gates are:\n\n```text\nframework-ci               {FRAMEWORK_RUN}  PASS\ninstalled-wheel-acceptance {INSTALLED_RUN}  PASS\n```\n\nThe retained framework-ci artifact is:\n\n```text\nartifact id    {ARTIFACT_ID}\nartifact name  {ARTIFACT_NAME}\nwheel          {WHEEL}\n```\n\nThe **inner wheel bytes**, not the outer GitHub Actions artifact ZIP, were independently\nSHA256-hashed after download. The digest exactly matches both `CANDIDATE.json` and\n`SHA256SUMS`:\n\n```text\nframework_artifact_sha256\n= {WHEEL_SHA}\n```\n\nThe outer Actions artifact digest is `{ZIP_DIGEST}` and is retained only as provenance;\nit is not candidate identity. `CANDIDATE.json` binds the wheel to workflow run\n`{FRAMEWORK_RUN}`, attempt `1`, and source `{SOURCE}`.\n\nThis exact executable candidate is **selected but not frozen**. It has not constructed\n`integration_inputs_hash`, executed Microsoft Fabric, authorized release, or claimed\nFabric PASS. Candidate/evidence identity remains\n`framework_artifact_sha256 + integration_inputs_hash`; these selected wheel bytes must\nnot change before identity-bound Fabric certification.\n\n"""
if state.count(marker) != 1:
    raise SystemExit(f"selected narrative marker: expected 1, found {state.count(marker)}")
state = state.replace(marker, selected_section + marker, 1)
STATE.write_text(state, encoding="utf-8")


test = TEST.read_text(encoding="utf-8")
for old, new, label in (
    ('"exact_candidate_source_selected: false"', '"exact_candidate_source_selected: true"', "test release selected"),
    ('"current_source_candidate_git_sha: not_selected_after_projection_production_runtime"', f'"current_source_candidate_git_sha: {SOURCE}"', "test source"),
    ('"current_source_framework_artifact_sha256: not_selected_after_projection_production_runtime"', f'"current_source_framework_artifact_sha256: {WHEEL_SHA}"', "test wheel"),
    ('"current_source_requires_new_exact_artifact_before_release_claim: true"', '"current_source_requires_new_exact_artifact_before_release_claim: false"', "test artifact flag"),
    ('"status: not_selected_after_projection_production_runtime"', '"status: selected_not_frozen"', "test selection status"),
    ('"exact_current_candidate_selected: false"', '"exact_current_candidate_selected: true"', "test fabric selected"),
    ('"current_source_installed_wheel_acceptance: not_run_for_new_current_source"', f'"current_source_installed_wheel_acceptance: passed_main_run_{INSTALLED_RUN}"', "test installed proof"),
):
    test = once(test, old, new, label)

anchor = '        "current_source_requires_new_exact_artifact_before_release_claim: false",\n'
extra = (
    f'        "candidate_git_sha: {SOURCE}",\n'
    f'        "candidate_main_framework_ci_run: {FRAMEWORK_RUN}",\n'
    f'        "candidate_main_installed_wheel_run: {INSTALLED_RUN}",\n'
    f'        "candidate_wheel_artifact_id: {ARTIFACT_ID}",\n'
    f'        "candidate_wheel_artifact_name: {ARTIFACT_NAME}",\n'
    f'        "framework_artifact_sha256: {WHEEL_SHA}",\n'
    '        "wheel_sha_verified_against_candidate_json: true",\n'
    '        "wheel_sha_verified_against_sha256sums: true",\n'
    '        "wheel_sha_independently_rehashed: true",\n'
    f'        "github_artifact_zip_digest: {ZIP_DIGEST}",\n'
)
if test.count(anchor) != 1:
    raise SystemExit(f"test selection anchor: expected 1, found {test.count(anchor)}")
test = test.replace(anchor, anchor + extra, 1)
TEST.write_text(test, encoding="utf-8")
