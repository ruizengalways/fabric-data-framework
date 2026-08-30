from __future__ import annotations

import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"

CANONICAL = {
    "config": "metadata.config",
    "runtime": "contracts.runtime",
    "infrastructure": "contracts.environment",
    "dispatcher": "orchestration.dispatcher",
}


def test_framework_root_contains_no_implementation_modules():
    root_python = {path.name for path in PACKAGE_ROOT.glob("*.py")}
    assert root_python == {"__init__.py"}


@pytest.mark.parametrize(("old", "new"), CANONICAL.items())
def test_remaining_root_modules_have_one_canonical_owner(old: str, new: str):
    assert importlib.import_module(f"fabric_data_framework.{new}") is not None
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"fabric_data_framework.{old}")


def test_generic_runtime_and_recovery_runtime_have_distinct_owners():
    generic_runtime = importlib.import_module("fabric_data_framework.contracts.runtime")
    recovery_runtime = importlib.import_module("fabric_data_framework.recovery.runtime")

    assert hasattr(generic_runtime, "RuntimeContext")
    assert not hasattr(generic_runtime, "AttemptContext")
    assert hasattr(recovery_runtime, "AttemptContext")
    assert not hasattr(recovery_runtime, "RuntimeContext")


def test_source_and_tests_do_not_reintroduce_root_module_imports():
    forbidden = tuple(f"fabric_data_framework.{old}" for old in CANONICAL)
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
