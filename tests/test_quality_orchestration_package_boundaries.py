from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]


def test_quality_and_orchestration_roots_are_namespace_only():
    quality = importlib.import_module("fabric_data_framework.quality")
    orchestration = importlib.import_module("fabric_data_framework.orchestration")
    assert not hasattr(quality, "validate_records")
    assert not hasattr(quality, "SchemaChangeKind")
    assert not hasattr(orchestration, "build_dispatch_plan")
    assert not hasattr(orchestration, "DispatchPlan")


def test_explicit_quality_and_orchestration_modules_import():
    modules = (
        "fabric_data_framework.quality.rules",
        "fabric_data_framework.quality.schema_evolution",
        "fabric_data_framework.quality.temporal",
        "fabric_data_framework.quality.reconciliation",
        "fabric_data_framework.orchestration.planner",
        "fabric_data_framework.orchestration.dispatcher",
    )
    for module_name in modules:
        assert importlib.import_module(module_name) is not None


def test_source_and_tests_do_not_use_quality_orchestration_facades():
    forbidden = (
        "from fabric_data_framework.quality import",
        "from fabric_data_framework.orchestration import",
    )
    offenders: list[str] = []
    current = Path(__file__).resolve()
    for root in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            if path.resolve() == current:
                continue
            text = path.read_text(encoding="utf-8")
            for value in forbidden:
                if value in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {value}")
    assert offenders == []
