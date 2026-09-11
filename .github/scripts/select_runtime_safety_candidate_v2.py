from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement target, found {count}: {old!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


state = "docs/internal/STATE.md"
replace_once(state, "  exact_candidate_source_selected: false\n", "  exact_candidate_source_selected: true\n")
replace_once(state, "  current_source_candidate_git_sha: not_selected_after_runtime_safety_hardening\n", "  current_source_candidate_git_sha: b1b69c6ecd465b63c7e83d8405733a0c34962c8c\n")
replace_once(state, "  current_source_framework_artifact_sha256: not_selected_after_runtime_safety_hardening\n", "  current_source_framework_artifact_sha256: 3bfa738f63ae2b85228174dcd4b0949618d4e3f52212e8dc1deae01465860ab2\n")
replace_once(state, "  current_source_requires_new_exact_artifact_before_release_claim: true\n", "  current_source_requires_new_exact_artifact_before_release_claim: false\n")
replace_once(state, "  candidate_bytes_must_not_change: false\n", "  candidate_bytes_must_not_change: true\n")
replace_once(
    state,
    "  superseded_scd2_key_contract_candidate:\n",
    """  selected_candidate:\n    candidate_git_sha: b1b69c6ecd465b63c7e83d8405733a0c34962c8c\n    candidate_main_framework_ci_run: 34595385389\n    candidate_main_installed_wheel_run: 34595385353\n    candidate_wheel_artifact_id: 10261562203\n    candidate_wheel_artifact_name: framework-wheel-b1b69c6ecd465b63c7e83d8405733a0c34962c8c\n    candidate_wheel_filename: fabric_data_framework-0.4.0-py3-none-any.whl\n    framework_artifact_sha256: 3bfa738f63ae2b85228174dcd4b0949618d4e3f52212e8dc1deae01465860ab2\n    wheel_sha_verified_against_candidate_json: true\n    wheel_sha_verified_against_sha256sums: true\n    wheel_sha_independently_rehashed: true\n    status: selected_not_frozen\n  superseded_scd2_key_contract_candidate:\n""",
)
replace_once(state, "  exact_current_candidate_selected: false\n", "  exact_current_candidate_selected: true\n")
replace_once(state, "  current_source_installed_wheel_acceptance: not_run_for_new_current_source\n", "  current_source_installed_wheel_acceptance: passed\n")
replace_once(
    state,
    """next_boundary:\n  - merge the runtime-safety hardening only after exact PR-head source and installed-wheel gates pass\n  - build and retain the exact post-merge main wheel; independently verify its inner SHA256\n  - record a new exact executable candidate before constructing live Fabric integration inputs\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n""",
    """next_boundary:\n  - obtain and live-verify the approved isolated DEV Fabric workspace/lakehouse identity and runtime credentials\n""",
)
replace_once(
    state,
    "## Superseded SCD2 key-contract candidate\n",
    """## Selected exact current candidate after runtime-safety hardening\n\nThe runtime-safety hardening merged on `main` at:\n\n```text\nb1b69c6ecd465b63c7e83d8405733a0c34962c8c\n```\n\nThe exact post-merge main gates are:\n\n```text\nframework-ci               34595385389  PASS\ninstalled-wheel-acceptance 34595385353  PASS\n```\n\nThe retained framework-ci artifact is:\n\n```text\nartifact id    10261562203\nartifact name  framework-wheel-b1b69c6ecd465b63c7e83d8405733a0c34962c8c\nwheel          fabric_data_framework-0.4.0-py3-none-any.whl\n```\n\nThe **inner wheel bytes**, not the outer GitHub Actions artifact ZIP, were independently SHA256-hashed after download. The digest exactly matches both `CANDIDATE.json` and `SHA256SUMS`:\n\n```text\nframework_artifact_sha256\n= 3bfa738f63ae2b85228174dcd4b0949618d4e3f52212e8dc1deae01465860ab2\n```\n\nThis selects the exact executable post-hardening candidate. It does **not** freeze 0.4, construct integration inputs, execute Microsoft Fabric, authorize release, or claim Fabric PASS. Candidate/evidence identity remains `framework_artifact_sha256 + integration_inputs_hash`; `integration_inputs_hash` is still not yet constructed.\n\n## Superseded SCD2 key-contract candidate\n""",
)
replace_once(
    state,
    "`0.4.0` is not frozen and not release-authorized. Packaged runtime-safety changes supersede the previously selected executable candidate, so no exact current-source candidate is selected until the hardening reaches `main`, both post-merge gates pass, and the retained main wheel is independently verified.\n",
    "`0.4.0` is not frozen and not release-authorized. The exact post-hardening executable candidate is selected and independently verified, but release certification remains blocked at the external live-Fabric binding/evidence boundary.\n",
)

consistency = "tests/test_current_docs_consistency.py"
replace_once(consistency, '        "exact_candidate_source_selected: false",\n', '        "exact_candidate_source_selected: true",\n')
replace_once(consistency, '        "current_source_candidate_git_sha: not_selected_after_runtime_safety_hardening",\n', '        "current_source_candidate_git_sha: b1b69c6ecd465b63c7e83d8405733a0c34962c8c",\n')
replace_once(consistency, '        "current_source_framework_artifact_sha256: not_selected_after_runtime_safety_hardening",\n', '        "current_source_framework_artifact_sha256: 3bfa738f63ae2b85228174dcd4b0949618d4e3f52212e8dc1deae01465860ab2",\n')
replace_once(consistency, '        "current_source_requires_new_exact_artifact_before_release_claim: true",\n', '        "current_source_requires_new_exact_artifact_before_release_claim: false",\n')
replace_once(consistency, '        "candidate_main_framework_ci_run: 34565985394",\n', '        "candidate_main_framework_ci_run: 34595385389",\n')
replace_once(consistency, '        "candidate_main_installed_wheel_run: 34565985349",\n', '        "candidate_main_installed_wheel_run: 34595385353",\n')
replace_once(consistency, '        "candidate_wheel_artifact_id: 10186013452",\n', '        "candidate_wheel_artifact_id: 10261562203",\n')
replace_once(consistency, '        "candidate_wheel_artifact_name: framework-wheel-81b574fb79bcc5e74cb9eee6d0644c6de8ef7ffd",\n', '        "candidate_wheel_artifact_name: framework-wheel-b1b69c6ecd465b63c7e83d8405733a0c34962c8c",\n')
replace_once(consistency, '        "framework_artifact_sha256: 5ee9a032d242f3a164ccfbfcfe5b646d91e6f35dbf603f21735b745dda6cead6",\n', '        "framework_artifact_sha256: 3bfa738f63ae2b85228174dcd4b0949618d4e3f52212e8dc1deae01465860ab2",\n')
replace_once(consistency, '        "wheel_sha_independently_rehashed: true",\n', '        "wheel_sha_independently_rehashed: true",\n        "status: selected_not_frozen",\n')
replace_once(consistency, '        "exact_current_candidate_selected: false",\n', '        "exact_current_candidate_selected: true",\n')
replace_once(consistency, '        "current_source_installed_wheel_acceptance: not_run_for_new_current_source",\n', '        "current_source_installed_wheel_acceptance: passed",\n')
