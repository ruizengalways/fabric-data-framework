import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STATE = DOCS / "internal/STATE.md"


CANONICAL_DOCS = (
    "README.md",
    "ARCHITECTURE.md",
    "CODE_READING_GUIDE.md",
    "GETTING_STARTED.md",
    "IMPLEMENTATION_PROJECT.md",
    "DATA_PATTERNS.md",
    "OPERATIONS.md",
    "REPAIR_AND_REBUILD.md",
    "TESTING_AND_CERTIFICATION.md",
    "RELEASE.md",
    "reference/FABRIC_SQL_AUTH.md",
    "reference/PIPELINE_CHILD_CONTRACT.md",
    "internal/STATE.md",
    "internal/CAPABILITIES.md",
    "internal/IMPLEMENTATION_MAP.md",
)

_REPO_PATH_REFERENCE = re.compile(
    r"(?P<path>"
    r"(?:src|tests|certification|release)/[A-Za-z0-9_.\-/<>{}*]+"
    r"|\.github/[A-Za-z0-9_.\-/<>{}*]+"
    r")"
)
_PLACEHOLDER_CHARS = frozenset("<>{}*")
_CONCRETE_FILE_SUFFIXES = frozenset(
    {".json", ".md", ".py", ".sh", ".toml", ".txt", ".yaml", ".yml"}
)


def _read(relative: str) -> str:
    return (DOCS / relative).read_text(encoding="utf-8")


def _concrete_repo_path_references():
    """Yield explicit repository paths from docs, excluding prose and templates.

    The guard intentionally handles only unambiguous repo-root references. A token
    must start with a guarded root and either name a directory (trailing slash) or
    a known repository file type. This rejects false positives such as
    ``release/Fabric`` or ``tests/docs`` while still catching a misspelled concrete
    file such as ``tests/test_orchestration_dispatcher.py``.
    """

    for doc_path in sorted(DOCS.rglob("*.md")):
        text = doc_path.read_text(encoding="utf-8")
        for match in _REPO_PATH_REFERENCE.finditer(text):
            reference = match.group("path").rstrip(".,;:)]")
            if _PLACEHOLDER_CHARS.intersection(reference):
                continue
            if not reference.endswith("/") and Path(reference).suffix not in _CONCRETE_FILE_SUFFIXES:
                continue
            yield doc_path.relative_to(ROOT).as_posix(), reference


def test_documentation_has_one_canonical_topic_tree():
    for relative in CANONICAL_DOCS:
        assert (DOCS / relative).is_file(), relative

    assert not (DOCS / "human").exists()
    assert not (DOCS / "machine").exists()


def test_docs_index_is_navigation_not_a_second_architecture_doc():
    index = _read("README.md")
    for relative in (
        "ARCHITECTURE.md",
        "CODE_READING_GUIDE.md",
        "GETTING_STARTED.md",
        "IMPLEMENTATION_PROJECT.md",
        "DATA_PATTERNS.md",
        "OPERATIONS.md",
        "REPAIR_AND_REBUILD.md",
        "TESTING_AND_CERTIFICATION.md",
        "RELEASE.md",
        "internal/STATE.md",
    ):
        assert relative in index

    assert "A fact should have **one home**" in index
    assert "Do not create a new top-level document" in index


def test_root_readme_surfaces_code_reading_and_repair_runbooks():
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/CODE_READING_GUIDE.md" in root_readme
    assert "docs/REPAIR_AND_REBUILD.md" in root_readme


def test_state_is_single_current_recovery_checkpoint_and_fail_closed():
    state = STATE.read_text(encoding="utf-8")
    for token in (
        "fabric-data-framework-state-v4",
        "public_release: v0.3.0",
        "source_version: 0.4.0-development-unreleased",
        "candidate_status: not_frozen",
        "exact_candidate_source_selected: true",
        "release_allowed: false",
        "candidate_git_sha: 81f4d5f93983e8288246f5b1521f763091880297",
        "candidate_main_framework_ci_run: 34216247521",
        "candidate_main_installed_wheel_run: 34216247544",
        "framework_artifact_sha256: 845f68d938a39ada944a1a71513b4f46b3a68416a5b53d60dbd10c2f6f95327c",
        "integration_inputs_hash: not_constructed_for_selected_candidate",
        "integration_inputs_status: blocked_pending_approved_live_DEV_bindings",
        "exact_current_candidate_selected: true",
        "selected_candidate_real_fabric_execution: not_run",
        "canonical_control_plane_profile: fabric_sql_database_v1",
        "promote_runtime_state_between_environments: false",
        "framework_dependency_allowed: false",
        "status_label: FABRIC_CERTIFICATION_REQUIRED",
        "release_authorized_by_certification_runner: false",
        "do_not_guess_or_reuse_unverified_resource_ids: true",
        "stop on any real FAIL",
    ):
        assert token in state


def test_operations_and_repair_docs_keep_canonical_ownership_separate():
    state = STATE.read_text(encoding="utf-8")
    operations = _read("OPERATIONS.md")
    repair = _read("REPAIR_AND_REBUILD.md")
    implementation_map = _read("internal/IMPLEMENTATION_MAP.md")

    for token in (
        "TARGET_ONLY",
        "CAPTURE_AND_TARGET",
        "AUTHORITATIVE_RESET",
    ):
        assert token in state
        assert token in operations
        assert token in repair
        assert token in implementation_map

    for token in (
        "RepairIssueOrigin",
        "RebuildImpactPlan",
        "TargetVersionSpec",
        "TargetCutoverRequest",
        "TargetCutoverGate",
    ):
        assert token in repair

    assert "requested_scope_must_equal_completed_scope: true" in state
    assert "automatic_business_data_purge_supported: false" in state
    assert "manual_operator_governance_only" in state
    assert "The old v1 is deliberately not deleted" in repair
    assert "dependency-aware impact planner" in repair

    assert "transient runtime operations" in operations
    assert "REPAIR_AND_REBUILD.md" in operations
    assert "### 10.1 `TARGET_ONLY`" not in operations
    assert "### 10.2 `CAPTURE_AND_TARGET`" not in operations
    assert "### 10.3 `AUTHORITATIVE_RESET`" not in operations
    assert "data correctness repair/rebuild/v1-v2 cutover" in implementation_map


def test_current_docs_lock_framework_owned_candidate_identity():
    docs = "\n".join(
        _read(relative)
        for relative in (
            "ARCHITECTURE.md",
            "TESTING_AND_CERTIFICATION.md",
            "RELEASE.md",
            "internal/STATE.md",
            "internal/CAPABILITIES.md",
            "internal/IMPLEMENTATION_MAP.md",
        )
    )
    assert "framework_artifact_sha256" in docs
    assert "integration_inputs_hash" in docs
    assert "No customer/domain release identity" in docs
    assert "framework-agnostic" in docs
    assert "fabric-customer -X-> fabric-data-framework" in docs


def test_current_docs_do_not_restore_removed_customer_certification_vocabulary():
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in DOCS.rglob("*.md")
    )
    for removed in (
        "--customer-inputs",
        "customer_inputs_root",
        "customer.compatibility",
        "CUSTOMER_COMPATIBILITY",
        "CUSTOMER_REPO_TOKEN",
        "customer_inputs_run_id",
        "customer_git_sha",
        "domain_release_hash",
    ):
        assert removed not in docs


def test_current_docs_do_not_retain_superseded_history_files():
    for relative in (
        "docs/internal/HISTORY.md",
        "docs/machine/HISTORY.md",
        "docs/machine/FIRST_COMPANY_FABRIC_TEST_2026-09-03.md",
        "docs/human/FIRST_FABRIC_NOTEBOOK_TEST.md",
        "docs/human/MANUAL_CERTIFICATION.md",
        "docs/human/CUSTOMER_PROJECT_BOOTSTRAP.md",
    ):
        assert not (ROOT / relative).exists()


def test_supported_manual_certification_implementation_is_not_deleted_with_docs():
    assert (ROOT / ".github/workflows/candidate-admin-certification.yml").is_file()
    assert (ROOT / "src/fabric_data_framework/evidence/manual_certification.py").is_file()
    assert (ROOT / "tests/test_manual_certification.py").is_file()


def test_documented_concrete_repo_paths_exist():
    missing = sorted(
        f"{source}: {reference}"
        for source, reference in _concrete_repo_path_references()
        if not (ROOT / reference).exists()
    )
    assert not missing, "documentation references missing repository paths:\n" + "\n".join(missing)
