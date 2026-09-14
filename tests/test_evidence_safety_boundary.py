from __future__ import annotations

import ast
import importlib
import math
from pathlib import Path

import pytest

from fabric_data_framework.contracts.audit_safety import (
    AUDIT_MAX_SERIALIZED_BYTES,
    AUDIT_MAX_STRING,
    assert_safe_retained_text,
    sanitize_audit_details,
    sanitize_audit_text,
    sanitize_audit_value,
)


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"
CORE_PACKAGES = {
    "adapters", "apply", "capture", "contracts", "control_plane", "data_plane",
    "deployment", "execution", "extensions", "metadata", "orchestration", "quality",
    "recovery",
}
FORBIDDEN_CORE_TARGETS = {"evidence", "certification", "cli"}


def test_audit_safety_has_one_canonical_module_path():
    module = importlib.import_module("fabric_data_framework.contracts.audit_safety")
    assert callable(module.assert_safe_retained_text)
    assert not (PACKAGE_ROOT / "evidence" / "safety.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("fabric_data_framework.evidence.safety")


@pytest.mark.parametrize(
    "value",
    (
        "password=hunter2",
        "Authorization: Bearer abc",
        "https://user:secret@example.test/path",
        "https://example.test/path?token=abc",
    ),
)
def test_retained_text_rejects_secret_material(value: str):
    with pytest.raises(ValueError):
        assert_safe_retained_text(value)


def test_audit_sanitization_redacts_truncates_and_bounds_nested_values():
    text = sanitize_audit_text("password=hunter2 " + "x" * (AUDIT_MAX_STRING + 100))
    assert "hunter2" not in text
    assert "[REDACTED]" in text
    assert len(text) <= AUDIT_MAX_STRING
    value = sanitize_audit_value({"token": "secret", "nested": {"items": [1, math.inf, object()]}})
    assert value["token"] == "[REDACTED]"
    assert value["nested"]["items"][1] == "[NON_FINITE_FLOAT]"
    assert value["nested"]["items"][2].startswith("[UNSUPPORTED_AUDIT_VALUE:")
    assert sanitize_audit_details([1, 2]) == {"value": [1, 2]}


def test_audit_sanitization_enforces_serialized_size_limit():
    value = sanitize_audit_value({str(index): "x" * 2000 for index in range(20)})
    assert value["_truncated"] is True
    assert value["original_serialized_bytes"] > AUDIT_MAX_SERIALIZED_BYTES


def _absolute_import_targets(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
    return targets


def test_core_dependency_direction_does_not_reach_leaf_layers():
    offenders: list[str] = []
    for owner in sorted(CORE_PACKAGES):
        root = PACKAGE_ROOT / owner
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            for target in _absolute_import_targets(path):
                prefix = "fabric_data_framework."
                if not target.startswith(prefix):
                    continue
                first = target[len(prefix):].split(".", 1)[0]
                if first in FORBIDDEN_CORE_TARGETS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    assert offenders == []


def test_adapters_do_not_import_execution_layer():
    offenders: list[str] = []
    for path in sorted((PACKAGE_ROOT / "adapters").rglob("*.py")):
        for target in _absolute_import_targets(path):
            if target == "fabric_data_framework.execution" or target.startswith("fabric_data_framework.execution."):
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    assert offenders == []
