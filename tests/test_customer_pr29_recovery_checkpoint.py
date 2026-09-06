from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FRAMEWORK_PR109_MAIN = "3bd3375b796531e5ca6c7e144e7f50e154cec29f"
FRAMEWORK_PR109_WHEEL_SHA = (
    "fe9adb12d9804dd146957dfc84925b18330edd0c189e5f713867e8e7e9478178"
)
FRAMEWORK_PR112_MAIN = "17fbbd8ed2afb14771748a25d3e12d9bf63fe986"
FRAMEWORK_PR112_WHEEL_SHA = (
    "0d7d351548712db3293b00a3b8eb968387f573b542d8fe506c9436a1b9b0a834"
)


def test_customer_enterprise_candidate_input_alignment_is_complete():
    state = (ROOT / "docs/machine/STATE.md").read_text(encoding="utf-8")
    for token in (
        "merged_enterprise_topology_pr_27_main: fa495fce622de8a5344bf74ecc52885fe85596f4",
        "enterprise_topology_checkpoint_pr_28_main: 9488b1b4b1f1f90a750bee66fee0c7b373c1839a",
        "merged_candidate_input_topology_hardening_pr_29_main: 1effd5fe283afeb5b960a87e64638f1674433580",
        "candidate_input_checkpoint_pr_30_main: 4676157be2d8203c7cd5a625e9e68540dc12d4ad",
        "pr_29_customer_ci: 34001442382",
        "pr_29_certification_contract_ci: 34001442376",
        "pr_29_main_customer_ci: 34001481213",
        "pr_29_main_certification_contract_ci: 34001481204",
        "pr_30_main_customer_ci: 34001648070",
        "pr_30_main_certification_contract_ci: 34001648061",
        "enterprise_topology_customer_update_in_progress: false",
        "enterprise_topology_customer_main_ci_proven: true",
        "candidate_input_canonical_control_plane_profile: fabric_sql_database_v1",
        "candidate_input_alternate_profile_rejected: true",
    ):
        assert token in state


def test_pr29_checkpoint_history_is_preserved_while_pr112_is_current():
    state = (ROOT / "docs/machine/STATE.md").read_text(encoding="utf-8")

    # PR #109 remains recoverable as historical exact bytes; it is no longer current.
    assert "historical_framework_executable:" in state
    assert "pull_request: 109" in state
    assert f"merge_sha: {FRAMEWORK_PR109_MAIN}" in state
    assert f"wheel_inner_sha256: {FRAMEWORK_PR109_WHEEL_SHA}" in state
    assert "artifact_id: 9978610894" in state
    assert "current_executable_identity: false" in state

    # PR #112 is the exact current executable identity.
    assert "code_baseline:" in state
    assert "pull_request: 112" in state
    assert f"merge_sha: {FRAMEWORK_PR112_MAIN}" in state
    assert f"wheel_inner_sha256: {FRAMEWORK_PR112_WHEEL_SHA}" in state
    assert "artifact_id: 9982333832" in state
    assert "candidate_status: not_frozen" in state
    assert "release_allowed: false" in state
    assert "actual_selected_candidate_input_artifact_retained: false" in state
    assert "real_control_plane_external_evidence_retained: false" in state
    assert "real_warehouse_fault_controller_configured: false" in state
    assert "next execution boundary is real isolated DEV Fabric" in state
