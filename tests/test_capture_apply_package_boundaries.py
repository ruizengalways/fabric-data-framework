from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"


@pytest.mark.parametrize(
    ("package_name", "former_symbols"),
    (
        ("capture", ("CapturePattern", "CDCEvent", "CaptureSemanticContract", "capture_full_snapshot")),
        ("apply", ("apply_scd1", "apply_cdc_scd2", "AppendApplyResult", "SnapshotDiffPlan")),
    ),
)
def test_capture_and_apply_package_roots_are_namespace_only(package_name: str, former_symbols: tuple[str, ...]):
    package = importlib.import_module(f"fabric_data_framework.{package_name}")
    init_path = PACKAGE_ROOT / package_name / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)
    for symbol in former_symbols:
        assert not hasattr(package, symbol)


def test_source_and_tests_do_not_import_capture_or_apply_facades():
    forbidden = (
        "from fabric_data_framework.capture import",
        "from fabric_data_framework.apply import",
    )
    offenders: list[str] = []
    current = Path(__file__).resolve()
    for base in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for path in sorted(base.rglob("*.py")):
            if path.resolve() == current:
                continue
            text = path.read_text(encoding="utf-8")
            for value in forbidden:
                if value in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {value}")
    assert offenders == []


def test_representative_explicit_capture_and_apply_owners_are_importable():
    assert hasattr(importlib.import_module("fabric_data_framework.capture.semantic_contracts"), "CaptureSemanticContract")
    assert hasattr(importlib.import_module("fabric_data_framework.capture.cdc"), "CDCEvent")
    assert hasattr(importlib.import_module("fabric_data_framework.apply.scd1"), "apply_scd1")
    assert hasattr(importlib.import_module("fabric_data_framework.apply.cdc_scd2"), "apply_cdc_scd2")
