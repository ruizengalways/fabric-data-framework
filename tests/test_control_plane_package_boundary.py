from __future__ import annotations

import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"
CONTROL_PLANE_ROOT = PACKAGE_ROOT / "control_plane"

REMOVED_FLAT_MODULES = (
    "control_plane_certification",
    "control_plane_io",
    "control_plane_schema",
    "control_plane_stage_policy",
    "repository",
    "relational_repository",
    "operator",
    "target_operation_io",
)

EXPECTED_CANONICAL_MODULES = (
    "schema",
    "io",
    "schema_evidence",
    "certification",
    "repository",
    "sqlalchemy_repository",
    "operator",
    "target_operation_journal",
)


def test_control_plane_package_is_canonical_and_explicit():
    package = importlib.import_module("fabric_data_framework.control_plane")
    assert not hasattr(package, "apply_baseline_schema")
    assert not hasattr(package, "SqlAlchemyControlPlaneRepository")
    for module_name in EXPECTED_CANONICAL_MODULES:
        imported = importlib.import_module(
            f"fabric_data_framework.control_plane.{module_name}"
        )
        assert imported is not None


@pytest.mark.parametrize("module_name", REMOVED_FLAT_MODULES)
def test_removed_flat_control_plane_imports_do_not_resolve(module_name: str):
    assert not (PACKAGE_ROOT / f"{module_name}.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"fabric_data_framework.{module_name}")


def test_former_control_plane_module_file_is_replaced_by_package():
    assert not (PACKAGE_ROOT / "control_plane.py").exists()
    assert CONTROL_PLANE_ROOT.is_dir()


def test_control_plane_package_has_no_cli_dependency():
    offenders: list[str] = []
    for path in sorted(CONTROL_PLANE_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "fabric_data_framework.cli" in text or "from ..cli" in text:
            offenders.append(str(path.relative_to(PACKAGE_ROOT)))
    assert offenders == []


def test_source_and_tests_do_not_reintroduce_removed_flat_import_paths():
    forbidden = tuple(
        f"fabric_data_framework.{module_name}" for module_name in REMOVED_FLAT_MODULES
    ) + (
        "from fabric_data_framework.control_plane import",
    )
    offenders: list[str] = []
    current_test = Path(__file__).resolve()
    for root in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            if path.resolve() == current_test:
                continue
            text = path.read_text(encoding="utf-8")
            for value in forbidden:
                if value in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {value}")
    assert offenders == []
