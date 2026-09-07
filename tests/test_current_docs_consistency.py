from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "docs/machine/STATE.md"
FRAMEWORK_SHA = "17fbbd8ed2afb14771748a25d3e12d9bf63fe986"
FRAMEWORK_MAIN_CI = "34010629765"
FRAMEWORK_WHEEL_SHA = "0d7d351548712db3293b00a3b8eb968387f573b542d8fe506c9436a1b9b0a834"
CUSTOMER_MAIN_SHA = "9b461e7b9dfacb45fa9b42caf56ebc67d3d4092b"
CUSTOMER_MAIN_CI = "34073023216"
CUSTOMER_CERT_CI = "34073023163"


def test_state_is_a_current_recovery_checkpoint():
    state = STATE.read_text(encoding="utf-8")
    for token in (
        "fabric-data-framework-machine-state-v2",
        "public_release: v0.3.0",
        "source_version: 0.4.0-development-unreleased",
        "candidate_status: not_frozen",
        "release_allowed: false",
        "strict_release_ready: false",
        "readiness_required_blockers: 15",
        f"source_sha: {FRAMEWORK_SHA}",
        f"main_ci_run: {FRAMEWORK_MAIN_CI}",
        f"wheel_sha256: {FRAMEWORK_WHEEL_SHA}",
        "artifact_id: 9982333832",
        "selected_as_frozen_candidate: false",
        "live_fabric_evidence_retained_for_current_bytes: false",
        "real_fabric_execution: NOT_YET",
        "canonical_control_plane_profile: fabric_sql_database_v1",
        "medallion_data_plane: Lakehouse / OneLake",
        "warehouse_role: optional SQL-first Gold / dimensional serving",
        "sql_runtime_default: fabric-user",
        "key_vault_required_for_default_lane: false",
        f"customer_main_sha: {CUSTOMER_MAIN_SHA}",
        f"customer_main_ci: {CUSTOMER_MAIN_CI}",
        f"customer_main_certification_contract_ci: {CUSTOMER_CERT_CI}",
        "production_runtime_pin: fabric-data-framework==0.3.0",
        "one_click_bootstrap_source_on_customer_main: true",
        "one_click_bootstrap_command: python certification/bootstrap.py --apply --environment DEV",
        "environment_is_fabric_environment_item: false",
        "repeated_sql_server_database_cli_args_required: false",
        "repository_owned_certification_resources_bootstrapped_in_company_fabric: false",
        "repository_owned_certification_notebook_deployed: false",
        "repository_owned_certification_pipeline_deployed: false",
        "current_framework_real_fabric_certification_executed: false",
        "control_plane_external_evidence_incomplete",
        "control_plane_external_evidence_not_review_bound",
        "warehouse_real_fault_controller_not_configured",
        "isolated DEV Fabric",
        "bootstrap_terminal_state: READY / NOT_RUN",
    ):
        assert token in state


def test_current_recovery_docs_do_not_retain_superseded_history():
    current_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "docs/README.md",
            ROOT / "docs/human/README.md",
            ROOT / "docs/machine/README.md",
            STATE,
        )
    )
    for legacy in (
        "303683729c4915d78200d463a6def01c8de9eae6",
        "33381666892",
        "3bd3375b796531e5ca6c7e144e7f50e154cec29f",
        "Customer PR #25",
        "merged_fabric_native_auth_pr_31_main",
        "historical_first_company_fabric_artifact",
        "FIRST_COMPANY_FABRIC_TEST_2026-09-03.md",
        "FIRST_FABRIC_NOTEBOOK_TEST.md",
        "HISTORY.md",
        "MANUAL_CERTIFICATION.md",
    ):
        assert legacy not in current_docs


def test_superseded_recovery_files_are_removed():
    for relative in (
        "docs/machine/HISTORY.md",
        "docs/machine/FIRST_COMPANY_FABRIC_TEST_2026-09-03.md",
        "docs/human/FIRST_FABRIC_NOTEBOOK_TEST.md",
        "docs/human/MANUAL_CERTIFICATION.md",
        "tests/test_customer_pr29_recovery_checkpoint.py",
        "tests/test_customer_pr31_fabric_native_recovery_checkpoint.py",
        "tests/test_release_docs_consistency.py",
    ):
        assert not (ROOT / relative).exists()


def test_supported_fallback_implementation_is_not_deleted_with_legacy_docs():
    assert (ROOT / ".github/workflows/candidate-admin-certification.yml").is_file()
    assert (ROOT / "src/fabric_data_framework/evidence/manual_certification.py").is_file()
    assert (ROOT / "tests/test_manual_certification.py").is_file()


def test_current_docs_keep_real_fabric_and_release_boundaries_fail_closed():
    state = STATE.read_text(encoding="utf-8")
    assert "release_allowed: false" in state
    assert "candidate_status: not_frozen" in state
    assert "current_framework_real_fabric_certification_executed: false" in state
    assert "repository_owned_certification_resources_bootstrapped_in_company_fabric: false" in state
    assert "stop_on_real_fail: true" in state
    assert "do not create another recovery/checkpoint pr" in state.lower()
