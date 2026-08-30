from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"
CONTRACTS_ROOT = PACKAGE_ROOT / "contracts"


def test_semantic_contracts_have_explicit_canonical_modules():
    package = importlib.import_module("fabric_data_framework.contracts")
    assert importlib.import_module("fabric_data_framework.contracts.schema").SchemaContract
    assert importlib.import_module("fabric_data_framework.contracts.audit").DatasetRunAudit
    assert importlib.import_module("fabric_data_framework.contracts.reconciliation").ReconciliationResult
    assert importlib.import_module("fabric_data_framework.contracts.quarantine").QuarantineBatch
    assert importlib.import_module("fabric_data_framework.contracts.target_operation").TargetOperationIntent
    assert not hasattr(package, "CaptureReceipt")
    assert not hasattr(package, "SchemaContract")


@pytest.mark.parametrize("module_name", ("schema_contract", "operations", "target_operations"))
def test_removed_root_semantic_contract_modules_do_not_resolve(module_name: str):
    assert not (PACKAGE_ROOT / f"{module_name}.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"fabric_data_framework.{module_name}")


def test_contracts_package_root_has_no_reexport_imports():
    tree = ast.parse((CONTRACTS_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def test_config_no_longer_owns_frozen_model():
    config = importlib.import_module("fabric_data_framework.metadata.config")
    base = importlib.import_module("fabric_data_framework.contracts.base")
    assert hasattr(base, "FrozenModel")
    assert not hasattr(config, "FrozenModel")


def _resolve(path: Path, node: ast.ImportFrom) -> str:
    module = node.module or ""
    if node.level == 0:
        return module
    try:
        rel_parent = path.parent.relative_to(PACKAGE_ROOT)
    except ValueError:
        return module
    parts = ["fabric_data_framework", *rel_parent.parts]
    up = node.level - 1
    base = parts[: len(parts) - up]
    return ".".join([*base, *module.split(".")]) if module else ".".join(base)


def test_source_and_tests_use_explicit_contract_submodules():
    forbidden = {
        "fabric_data_framework.schema_contract",
        "fabric_data_framework.operations",
        "fabric_data_framework.target_operations",
        "fabric_data_framework.contracts",
    }
    offenders: list[str] = []
    current = Path(__file__).resolve()
    for root in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            if path.resolve() == current or path == CONTRACTS_ROOT / "__init__.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    resolved = _resolve(path, node)
                    if resolved in forbidden:
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: {resolved}")
                    if resolved == "fabric_data_framework.metadata.config" and any(
                        alias.name == "FrozenModel" for alias in node.names
                    ):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: config.FrozenModel")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in forbidden - {"fabric_data_framework.contracts"}:
                            offenders.append(f"{path.relative_to(REPO_ROOT)}: {alias.name}")
    assert offenders == []
