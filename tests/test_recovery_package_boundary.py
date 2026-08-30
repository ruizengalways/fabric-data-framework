from __future__ import annotations

import ast
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"
RECOVERY_ROOT = PACKAGE_ROOT / "recovery"


def test_recovery_package_root_is_namespace_only():
    package = importlib.import_module("fabric_data_framework.recovery")
    tree = ast.parse((RECOVERY_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)
    for former_facade_symbol in (
        "RetryPolicy",
        "AttemptContext",
        "execute_with_retry",
        "FullRebuildContext",
        "PreparedQuarantineReplay",
        "FabricWarehouseTargetCommitProbe",
    ):
        assert not hasattr(package, former_facade_symbol)


def test_source_and_tests_do_not_import_recovery_facade_symbols():
    offenders: list[str] = []
    current = Path(__file__).resolve()
    for base in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for path in sorted(base.rglob("*.py")):
            if path.resolve() == current:
                continue
            text = path.read_text(encoding="utf-8")
            if "from fabric_data_framework.recovery import" in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_explicit_recovery_runtime_owner_remains_importable():
    runtime = importlib.import_module("fabric_data_framework.recovery.runtime")
    assert hasattr(runtime, "RetryPolicy")
    assert hasattr(runtime, "AttemptContext")
