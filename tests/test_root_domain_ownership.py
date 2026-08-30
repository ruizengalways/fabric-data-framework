from __future__ import annotations

import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "fabric_data_framework"

CANONICAL = {
    "watermark": "capture.watermark",
    "scd2": "apply.scd2",
    "bronze": "data_plane.bronze",
    "reconciliation": "quality.reconciliation",
    "fabric_auth": "adapters.fabric.auth",
}


@pytest.mark.parametrize(("old", "new"), CANONICAL.items())
def test_root_domain_stragglers_have_one_canonical_owner(old: str, new: str):
    assert importlib.import_module(f"fabric_data_framework.{new}") is not None
    assert not (PACKAGE_ROOT / f"{old}.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"fabric_data_framework.{old}")


def test_source_and_tests_do_not_reintroduce_removed_root_domain_imports():
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
