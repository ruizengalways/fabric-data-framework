from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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


def test_customer_alignment_checkpoint_does_not_change_framework_executable_identity():
    state = (ROOT / "docs/machine/STATE.md").read_text(encoding="utf-8")
    assert "pull_request: 109" in state
    assert "merge_sha: 3bd3375b796531e5ca6c7e144e7f50e154cec29f" in state
    assert "wheel_inner_sha256: fe9adb12d9804dd146957dfc84925b18330edd0c189e5f713867e8e7e9478178" in state
    assert "artifact_id: 9978610894" in state
    assert "candidate_status: not_frozen" in state
    assert "release_allowed: false" in state
    assert "actual_selected_candidate_input_artifact_retained: false" in state
    assert "real_control_plane_external_evidence_retained: false" in state
    assert "real_warehouse_fault_controller_configured: false" in state
    assert "next boundary is real isolated DEV Fabric execution, not more topology alignment" in state
