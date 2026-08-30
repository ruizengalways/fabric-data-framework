from __future__ import annotations

import ast
import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"


def test_root_package_is_namespace_only():
    package = importlib.import_module("fabric_data_framework")
    tree = ast.parse((PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)
    for legacy_name in (
        "__version__",
        "DatasetConfig",
        "CaptureReceipt",
        "SchemaContract",
        "SqlAlchemyControlPlaneRepository",
        "TargetOperationIntent",
        "apply_scd1",
        "dispatch_datasets",
    ):
        assert not hasattr(package, legacy_name)


def test_source_and_tests_do_not_use_root_symbol_imports():
    offenders: list[str] = []
    current = Path(__file__).resolve()
    for root in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            if path.resolve() == current:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.level == 0
                    and node.module == "fabric_data_framework"
                ):
                    offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_cli_does_not_depend_on_root_package_version_symbol():
    text = (PACKAGE_ROOT / "cli" / "base.py").read_text(encoding="utf-8")
    assert "from .. import __version__" not in text
    assert "version(\"fabric-data-framework\")" in text
