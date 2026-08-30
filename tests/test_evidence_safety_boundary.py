from __future__ import annotations

import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"


def test_evidence_safety_has_one_canonical_module_path():
    module = importlib.import_module("fabric_data_framework.evidence.safety")
    assert callable(module.assert_safe_retained_text)
    assert not (PACKAGE_ROOT / "retained_evidence_safety.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("fabric_data_framework.retained_evidence_safety")


def test_source_and_tests_do_not_reintroduce_old_evidence_safety_import():
    forbidden = "fabric_data_framework.retained_evidence_safety"
    offenders: list[str] = []
    current_test = Path(__file__).resolve()
    for root in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for path in sorted(root.rglob("*.py")):
            if path.resolve() == current_test:
                continue
            if forbidden in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
