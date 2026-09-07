from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "docs/machine/STATE.md"
FRAMEWORK_SHA = "38741777955ffdb59cf9bdeea361bdd6651c5ee2"
FRAMEWORK_MAIN_CI = "34091549404"
FRAMEWORK_WHEEL_SHA = "201947410f75b88596af897c78d6fd056a9a3040fbec4d83d85b5439d7077cf0"
CUSTOMER_MAIN_SHA = "71c6c083e25cd133488d59318a856f7822f670f5"
CUSTOMER_MAIN_CI = "34095079211"


def test_state_is_a_current_recovery_checkpoint():
    state = STATE.read_text(encoding="utf-8")
    for token in (
        "fabric-data-framework-machine-state-v3",
        "public_release: v0.3.0",
        "source_version: 0.4.0-development-unreleased",
        "candidate_status: not_frozen",
        "release_allowed: false",
        "strict_release_ready: false",
        "readiness_required_blockers: 15",
        f"git_sha: {FRAMEWORK_SHA}",
        f"main_ci_run: {FRAMEWORK_MAIN_CI}",
        f"wheel_sha256: {FRAMEWORK_WHEEL_SHA}",
        "artifact_id: 10006992444",
        "installed_wheel_acceptance_run: 34091549510",
        "installed_wheel_acceptance: success",
        "selected_as_frozen_candidate: false",
        "live_fabric_evidence_retained_for_exact_wheel: false",
        "canonical_control_plane_profile: fabric_sql_database_v1",
        "medallion_data_plane: Lakehouse / OneLake",
        "warehouse_role: optional SQL-first Gold / dimensional serving",
        f"main_sha: {CUSTOMER_MAIN_SHA}",
        f"main_ci_run: {CUSTOMER_MAIN_CI}",
        "framework_dependency_allowed: false",
        "verification_command: fabric-customer verify --output <materialized-root>",
        "framework_v1_v2_comparison_requires_same_workload_digest: true",
        "customer_inputs: optional_framework_certification_integration_bundle",
        "customer_compatibility_gate: deprecated_serialized_readiness_name",
        "status_label: FABRIC_CERTIFICATION_REQUIRED",
        "isolated DEV Fabric",
        "stop_on_real_fail: true",
    ):
        assert token in state


def test_current_recovery_docs_do_not_retain_superseded_history():
    current_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "README.md",
            ROOT / "docs/README.md",
            ROOT / "docs/human/README.md",
            ROOT / "docs/human/ARCHITECTURE_BOUNDARIES.md",
            ROOT / "docs/human/IMPLEMENTATION_PROJECT_BOOTSTRAP.md",
            ROOT / "docs/machine/README.md",
            ROOT / "docs/machine/CAPABILITIES.md",
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
        "production_runtime_pin: fabric-data-framework==0.3.0",
        "one_click_bootstrap_source_on_customer_main: true",
        "python certification/bootstrap.py --apply --environment DEV",
    ):
        assert legacy not in current_docs


def test_current_docs_define_customer_as_independent_simulator():
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "README.md",
            ROOT / "docs/human/README.md",
            ROOT / "docs/human/ARCHITECTURE_BOUNDARIES.md",
            ROOT / "docs/human/IMPLEMENTATION_PROJECT_BOOTSTRAP.md",
        )
    )
    assert "framework-agnostic" in docs
    assert "implementation/domain repo" in docs
    assert "installed-wheel certification" in docs
    assert "fabric-customer -X-> fabric-data-framework" in docs


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
    assert "live_fabric_evidence_retained_for_exact_wheel: false" in state
    assert "status_label: FABRIC_CERTIFICATION_REQUIRED" in state
    assert "stop_on_real_fail: true" in state
