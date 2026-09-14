from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "fabric_data_framework"

# Hard-cut retained audit safety to the provider-neutral contracts layer.
for root in (ROOT / "src", ROOT / "tests"):
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        updated = text.replace("evidence.safety", "contracts.audit_safety")
        if updated != text:
            path.write_text(updated, encoding="utf-8")

for root in (ROOT / "docs", PKG):
    for path in root.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        updated = text.replace("evidence/safety.py", "contracts/audit_safety.py")
        if updated != text:
            path.write_text(updated, encoding="utf-8")

old_safety = PKG / "evidence" / "safety.py"
if old_safety.exists():
    old_safety.unlink()

# Move the provider-neutral current-projection execution vocabulary into contracts.
contract_path = PKG / "contracts" / "current_projection.py"
text = contract_path.read_text(encoding="utf-8")
if "from .audit import MutationCounts" not in text:
    text = text.replace("from .base import FrozenModel\n", "from .audit import MutationCounts\nfrom .base import FrozenModel\n")
insert = '''\n\nclass CurrentProjectionExecutionError(RuntimeError):\n    \"\"\"Provider-neutral failure for current-projection execution.\"\"\"\n\n\nclass CurrentProjectionExecutionResult(FrozenModel):\n    \"\"\"Durable execution result shared by reference and provider runtimes.\"\"\"\n\n    dataset_id: str = Field(min_length=1)\n    lower_processed_version: int | None = Field(default=None, ge=0)\n    upper_processed_version: int = Field(ge=0)\n    affected_keys: int = Field(ge=0)\n    mutations: MutationCounts\n    checkpoint_version: int = Field(ge=0)\n    no_work: bool = False\n'''
anchor = "\n\nclass CurrentProjectionMode(str, Enum):\n"
if "class CurrentProjectionExecutionResult" not in text:
    text = text.replace(anchor, insert + anchor)
text = text.replace(
    '    "CurrentProjectionConfig",\n',
    '    "CurrentProjectionConfig",\n    "CurrentProjectionExecutionError",\n    "CurrentProjectionExecutionResult",\n',
)
contract_path.write_text(text, encoding="utf-8")

execution_path = PKG / "execution" / "current_projection.py"
text = execution_path.read_text(encoding="utf-8")
text = text.replace("from pydantic import Field\n", "")
text = text.replace("from fabric_data_framework.contracts.base import FrozenModel\n", "")
text = text.replace(
    "from fabric_data_framework.contracts.current_projection import (\n    current_projection_checkpoint_partition,\n)",
    "from fabric_data_framework.contracts.current_projection import (\n    CurrentProjectionExecutionError,\n    CurrentProjectionExecutionResult,\n    current_projection_checkpoint_partition,\n)",
)
text = re.sub(
    r"\n\nclass CurrentProjectionExecutionError\(RuntimeError\):\n    pass\n",
    "",
    text,
    count=1,
)
text = re.sub(
    r"\n\nclass CurrentProjectionExecutionResult\(FrozenModel\):\n(?:    .*\n)+?    no_work: bool = False\n",
    "",
    text,
    count=1,
)
execution_path.write_text(text, encoding="utf-8")

adapter_path = PKG / "adapters" / "fabric" / "current_projection.py"
text = adapter_path.read_text(encoding="utf-8")
text = text.replace(
    "from fabric_data_framework.execution.current_projection import (\n    CurrentProjectionExecutionError,\n    CurrentProjectionExecutionResult,\n)",
    "from fabric_data_framework.contracts.current_projection import (\n    CurrentProjectionExecutionError,\n    CurrentProjectionExecutionResult,\n)",
)
adapter_path.write_text(text, encoding="utf-8")

test_projection = ROOT / "tests" / "test_current_projection.py"
text = test_projection.read_text(encoding="utf-8")
text = text.replace(
    "from fabric_data_framework.execution.current_projection import (\n    CurrentProjectionExecutionError,\n",
    "from fabric_data_framework.contracts.current_projection import CurrentProjectionExecutionError\nfrom fabric_data_framework.execution.current_projection import (\n",
)
test_projection.write_text(text, encoding="utf-8")

# Replace the old path-only test with direct behavior and dependency-direction guards.
boundary_test = ROOT / "tests" / "test_evidence_safety_boundary.py"
boundary_test.write_text('''from __future__ import annotations\n\nimport ast\nimport importlib\nimport math\nfrom pathlib import Path\n\nimport pytest\n\nfrom fabric_data_framework.contracts.audit_safety import (\n    AUDIT_MAX_SERIALIZED_BYTES,\n    AUDIT_MAX_STRING,\n    assert_safe_retained_text,\n    sanitize_audit_details,\n    sanitize_audit_text,\n    sanitize_audit_value,\n)\n\n\nREPO_ROOT = Path(__file__).parents[1]\nPACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"\nCORE_PACKAGES = {\n    "adapters",\n    "apply",\n    "capture",\n    "contracts",\n    "control_plane",\n    "data_plane",\n    "deployment",\n    "execution",\n    "extensions",\n    "metadata",\n    "orchestration",\n    "quality",\n    "recovery",\n}\nFORBIDDEN_CORE_TARGETS = {"evidence", "certification", "cli"}\n\n\ndef test_audit_safety_has_one_canonical_module_path():\n    module = importlib.import_module("fabric_data_framework.contracts.audit_safety")\n    assert callable(module.assert_safe_retained_text)\n    assert not (PACKAGE_ROOT / "evidence" / "safety.py").exists()\n    with pytest.raises(ModuleNotFoundError):\n        importlib.import_module("fabric_data_framework.evidence.safety")\n\n\n@pytest.mark.parametrize(\n    "value",\n    (\n        "password=hunter2",\n        "Authorization: Bearer abc",\n        "https://user:secret@example.test/path",\n        "https://example.test/path?token=abc",\n    ),\n)\ndef test_retained_text_rejects_secret_material(value: str):\n    with pytest.raises(ValueError):\n        assert_safe_retained_text(value)\n\n\ndef test_audit_sanitization_redacts_truncates_and_bounds_nested_values():\n    text = sanitize_audit_text("password=hunter2 " + "x" * (AUDIT_MAX_STRING + 100))\n    assert "hunter2" not in text\n    assert "[REDACTED]" in text\n    assert len(text) <= AUDIT_MAX_STRING\n\n    value = sanitize_audit_value(\n        {\n            "token": "secret",\n            "nested": {"items": [1, math.inf, object()]},\n        }\n    )\n    assert value["token"] == "[REDACTED]"\n    assert value["nested"]["items"][1] == "[NON_FINITE_FLOAT]"\n    assert value["nested"]["items"][2].startswith("[UNSUPPORTED_AUDIT_VALUE:")\n    assert sanitize_audit_details([1, 2]) == {"value": [1, 2]}\n\n\ndef test_audit_sanitization_enforces_serialized_size_limit():\n    value = sanitize_audit_value({str(index): "x" * 2000 for index in range(20)})\n    assert value["_truncated"] is True\n    assert value["original_serialized_bytes"] > AUDIT_MAX_SERIALIZED_BYTES\n\n\ndef _absolute_import_targets(path: Path) -> set[str]:\n    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))\n    targets: set[str] = set()\n    for node in ast.walk(tree):\n        if isinstance(node, ast.Import):\n            targets.update(alias.name for alias in node.names)\n        elif isinstance(node, ast.ImportFrom) and node.module:\n            targets.add(node.module)\n    return targets\n\n\ndef test_core_dependency_direction_does_not_reach_leaf_layers():\n    offenders: list[str] = []\n    for owner in sorted(CORE_PACKAGES):\n        root = PACKAGE_ROOT / owner\n        if not root.exists():\n            continue\n        for path in sorted(root.rglob("*.py")):\n            for target in _absolute_import_targets(path):\n                prefix = "fabric_data_framework."\n                if not target.startswith(prefix):\n                    continue\n                first = target[len(prefix) :].split(".", 1)[0]\n                if first in FORBIDDEN_CORE_TARGETS:\n                    offenders.append(f"{path.relative_to(REPO_ROOT)} -> {target}")\n    assert offenders == []\n\n\ndef test_adapters_do_not_import_execution_layer():\n    offenders: list[str] = []\n    for path in sorted((PACKAGE_ROOT / "adapters").rglob("*.py")):\n        for target in _absolute_import_targets(path):\n            if target == "fabric_data_framework.execution" or target.startswith(\n                "fabric_data_framework.execution."\n            ):\n                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {target}")\n    assert offenders == []\n''', encoding="utf-8")

# Invalidate the selected 0.4 candidate without creating release bookkeeping for a new one.
state_path = ROOT / "docs" / "internal" / "STATE.md"
state = state_path.read_text(encoding="utf-8")
state = state.replace("updated: 2026-09-12", "updated: 2026-09-14", 1)
state = state.replace("exact_candidate_source_selected: true", "exact_candidate_source_selected: false", 1)
state = state.replace(
    "current_source_candidate_git_sha: 5d4b69702acc3e362a52a3b890cc7096f2acc02a",
    "current_source_candidate_git_sha: not_selected_after_architecture_readability_refactor",
    1,
)
state = state.replace(
    "current_source_framework_artifact_sha256: 5e19368c5c63e48e78abb47aa095638d4f0b39c831fc909c37df6817ed7e21a8",
    "current_source_framework_artifact_sha256: not_selected_after_architecture_readability_refactor",
    1,
)
state = state.replace(
    "current_source_requires_new_exact_artifact_before_release_claim: false",
    "current_source_requires_new_exact_artifact_before_release_claim: true",
    1,
)
state = state.replace("candidate_bytes_must_not_change: true", "candidate_bytes_must_not_change: false", 1)
state = state.replace("  selected_candidate:\n", "  superseded_projection_production_candidate:\n", 1)
state = state.replace("    status: selected_not_frozen", "    status: superseded_by_architecture_readability_refactor", 1)
state = state.replace("exact_current_candidate_selected: true", "exact_current_candidate_selected: false", 1)
state = state.replace(
    "current_source_installed_wheel_acceptance: passed_main_run_34689765815",
    "current_source_installed_wheel_acceptance: not_run_for_new_current_source",
    1,
)
state_path.write_text(state, encoding="utf-8")

# Keep ownership docs explicit about deterministic cross-layer invariant helpers.
for rel in ("docs/CODE_READING_GUIDE.md", "src/fabric_data_framework/README.md"):
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "stable immutable cross-layer contracts only",
        "stable immutable cross-layer contracts and deterministic provider-neutral contract invariants",
    )
    text = text.replace(
        "`contracts/` | stable immutable cross-layer contracts only |",
        "`contracts/` | stable immutable cross-layer contracts and provider-neutral contract invariants |",
    )
    path.write_text(text, encoding="utf-8")

# Remove this one-shot script from the generated change set.
Path(__file__).unlink()
'''
