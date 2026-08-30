from __future__ import annotations

import ast
import importlib
from pathlib import Path
import re

import pytest


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"
DEPLOYMENT_ROOT = PACKAGE_ROOT / "deployment"


def test_deployment_package_has_explicit_canonical_modules():
    package = importlib.import_module("fabric_data_framework.deployment")
    contracts = importlib.import_module("fabric_data_framework.deployment.contracts")
    delivery = importlib.import_module("fabric_data_framework.deployment.delivery")
    assert contracts.ReleaseManifest is not None
    assert callable(delivery.build_release_manifest)
    assert not hasattr(package, "ReleaseManifest")
    assert not hasattr(package, "build_release_manifest")


def test_old_delivery_module_is_absent_and_deployment_file_became_package():
    assert not (PACKAGE_ROOT / "delivery.py").exists()
    assert not (PACKAGE_ROOT / "deployment.py").exists()
    assert DEPLOYMENT_ROOT.is_dir()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("fabric_data_framework.delivery")


def test_deployment_package_root_has_no_reexport_imports():
    tree = ast.parse((DEPLOYMENT_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def test_deployment_package_has_no_cli_dependency():
    offenders: list[str] = []
    for path in sorted(DEPLOYMENT_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "fabric_data_framework.cli" in text or "from ..cli" in text:
            offenders.append(str(path.relative_to(PACKAGE_ROOT)))
    assert offenders == []


def test_source_and_tests_do_not_reintroduce_flat_delivery_or_deployment_symbol_imports():
    forbidden_text = (
        "from fabric_data_framework.delivery import",
        "from fabric_data_framework.deployment import",
    )
    forbidden_patterns = (
        re.compile(r"from \.+delivery import "),
        re.compile(r"from \.+deployment import "),
    )
    offenders: list[str] = []
    current_test = Path(__file__).resolve()
    for root in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            if path.resolve() == current_test:
                continue
            text = path.read_text(encoding="utf-8")
            for value in forbidden_text:
                if value in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {value}")
            for pattern in forbidden_patterns:
                if pattern.search(text):
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}: {pattern.pattern}"
                    )
    assert offenders == []
