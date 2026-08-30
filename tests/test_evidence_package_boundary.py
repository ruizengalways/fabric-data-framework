from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "fabric_data_framework"

EVIDENCE_MODULES = (
    "integration_evidence",
    "integration_checks",
    "integration_evidence_merge",
    "integration_runner",
    "approved_control_plane_runner",
    "approved_pipeline_runner",
    "approved_capture_runner",
    "approved_warehouse_runner",
    "approved_warehouse_fault_runner",
)


@pytest.mark.parametrize("module_name", EVIDENCE_MODULES)
def test_legacy_evidence_import_is_same_canonical_module(module_name: str):
    legacy = importlib.import_module(f"fabric_data_framework.{module_name}")
    canonical = importlib.import_module(f"fabric_data_framework.evidence.{module_name}")
    assert legacy is canonical


@pytest.mark.parametrize("module_name", EVIDENCE_MODULES)
def test_root_evidence_compatibility_module_contains_no_implementation(module_name: str):
    path = PACKAGE_ROOT / f"{module_name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    implementation_nodes = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )
    assert not any(isinstance(node, implementation_nodes) for node in tree.body)


def test_evidence_package_exposes_stable_contract_surface():
    evidence = importlib.import_module("fabric_data_framework.evidence")
    assert evidence.IntegrationEvidenceSpec.__module__ == (
        "fabric_data_framework.evidence.integration_evidence"
    )
    assert evidence.ApprovedIntegrationRunnerConfig.__module__ == (
        "fabric_data_framework.evidence.integration_runner"
    )
