from __future__ import annotations

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
def test_root_evidence_legacy_module_file_is_absent(module_name: str):
    assert not (PACKAGE_ROOT / f"{module_name}.py").exists()


@pytest.mark.parametrize("module_name", EVIDENCE_MODULES)
def test_root_evidence_legacy_import_does_not_resolve(module_name: str):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"fabric_data_framework.{module_name}")


def test_evidence_package_exposes_stable_contract_surface():
    evidence = importlib.import_module("fabric_data_framework.evidence")
    assert evidence.IntegrationEvidenceSpec.__module__ == (
        "fabric_data_framework.evidence.integration_evidence"
    )
    assert evidence.ApprovedIntegrationRunnerConfig.__module__ == (
        "fabric_data_framework.evidence.integration_runner"
    )


def test_cli_router_legacy_module_is_absent():
    assert not (PACKAGE_ROOT / "cli_router.py").exists()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("fabric_data_framework.cli_router")
