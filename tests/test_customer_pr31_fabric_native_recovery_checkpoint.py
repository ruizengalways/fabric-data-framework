from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "docs/machine/STATE.md"

FRAMEWORK_SHA = "17fbbd8ed2afb14771748a25d3e12d9bf63fe986"
FRAMEWORK_PR_CI = "34010577594"
FRAMEWORK_MAIN_CI = "34010629765"
FRAMEWORK_WHEEL_SHA = "0d7d351548712db3293b00a3b8eb968387f573b542d8fe506c9436a1b9b0a834"
CUSTOMER_PR31_MAIN = "b8791ee3f7c575e87d457501ea2e93e40d75fcb6"
CUSTOMER_PR31_CI = "34016083859"
CUSTOMER_PR31_CERT_CI = "34016083851"
CUSTOMER_PR31_MAIN_CI = "34016136469"
CUSTOMER_PR31_MAIN_CERT_CI = "34016136281"
CUSTOMER_PR32_MAIN = "71947122a6cdfd7c4c6bf5e6c677d28f65d48064"
CUSTOMER_PR32_CI = "34016330538"
CUSTOMER_PR32_CERT_CI = "34016330542"
CUSTOMER_PR32_MAIN_CI = "34016357415"
CUSTOMER_PR32_MAIN_CERT_CI = "34016357443"
HISTORICAL_PROJECT_CONTRACT_SHA = "148e02e3fff7861f238296e7554815a6fd49dd0a"


def test_pr112_and_customer_pr31_pr32_recovery_identity_is_exact():
    state = STATE.read_text(encoding="utf-8")
    for token in (
        "pull_request: 112",
        f"merge_sha: {FRAMEWORK_SHA}",
        f"final_pr_ci_actions: {FRAMEWORK_PR_CI}",
        f"main_ci_actions: {FRAMEWORK_MAIN_CI}",
        f"wheel_inner_sha256: {FRAMEWORK_WHEEL_SHA}",
        "artifact_id: 9982333832",
        f"merged_fabric_native_auth_pr_31_main: {CUSTOMER_PR31_MAIN}",
        f"fabric_native_checkpoint_pr_32_main: {CUSTOMER_PR32_MAIN}",
        f"pr_31_customer_ci: {CUSTOMER_PR31_CI}",
        f"pr_31_certification_contract_ci: {CUSTOMER_PR31_CERT_CI}",
        f"pr_31_main_customer_ci: {CUSTOMER_PR31_MAIN_CI}",
        f"pr_31_main_certification_contract_ci: {CUSTOMER_PR31_MAIN_CERT_CI}",
        f"pr_32_customer_ci: {CUSTOMER_PR32_CI}",
        f"pr_32_certification_contract_ci: {CUSTOMER_PR32_CERT_CI}",
        f"pr_32_main_customer_ci: {CUSTOMER_PR32_MAIN_CI}",
        f"pr_32_main_certification_contract_ci: {CUSTOMER_PR32_MAIN_CERT_CI}",
        f"historical_framework_next_project_contract_sha: {HISTORICAL_PROJECT_CONTRACT_SHA}",
        f"certification_framework_sha: {FRAMEWORK_SHA}",
    ):
        assert token in state


def test_fabric_native_defaults_do_not_create_live_or_release_evidence():
    state = STATE.read_text(encoding="utf-8")
    for token in (
        "fabric_rest_auth_default: azure-cli",
        "sql_runtime_auth_default: fabric-user",
        "key_vault_required_for_default_lane: false",
        "key_vault_optional: true",
        "env_token_optional: true",
        "reusable_certification_pipeline_deployed_in_company_fabric: false",
        "repository_owned_certification_notebook_deployed: false",
        "repository_owned_certification_pipeline_deployed: false",
        "current_pr112_real_fabric_certification_executed: false",
        "released_runtime_pin: fabric-data-framework==0.3.0",
        "candidate_status: not_frozen",
        "release_allowed: false",
        "actual_selected_candidate_input_artifact_retained: false",
        "control_plane_external_evidence_incomplete",
        "control_plane_external_evidence_not_review_bound",
        "warehouse_real_fault_controller_not_configured",
        "next execution boundary is real isolated DEV Fabric",
    ):
        assert token in state
