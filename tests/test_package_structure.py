"""Stable package-ownership contract for the 0.4 hard-cut structure.

This test intentionally rejects the pre-refactor module locations. 0.4 is still
unreleased, so moved internals are a hard cut rather than compatibility aliases.
"""

from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "fabric_data_framework"


CANONICAL_MODULES = (
    "fabric_data_framework.execution.watermark_scd2",
    "fabric_data_framework.quality.reconciliation.engine",
    "fabric_data_framework.quality.reconciliation.append",
    "fabric_data_framework.quality.reconciliation.full_replace",
    "fabric_data_framework.quality.reconciliation.scd2",
    "fabric_data_framework.quality.reconciliation.snapshot_diff",
    "fabric_data_framework.certification.fabric.assets",
    "fabric_data_framework.certification.fabric.bindings",
    "fabric_data_framework.certification.fabric.fabric_job",
    "fabric_data_framework.certification.fabric.pipeline_child",
    "fabric_data_framework.evidence.integration.evidence",
    "fabric_data_framework.evidence.integration.runner",
    "fabric_data_framework.evidence.integration.approved.capture",
    "fabric_data_framework.evidence.integration.approved.pipeline",
    "fabric_data_framework.evidence.business_paths.approved_runner",
    "fabric_data_framework.evidence.business_paths.evidence",
    "fabric_data_framework.evidence.release.candidate_certification",
    "fabric_data_framework.evidence.release.readiness",
)


OLD_PATHS = (
    "execution/dataset_runner.py",
    "quality/reconciliation_engine.py",
    "quality/full_refresh.py",
    "quality/append.py",
    "quality/snapshot_diff.py",
    "certification/fabric_assets.py",
    "certification/bindings.py",
    "certification/fabric_job.py",
    "certification/pipeline_child.py",
    "evidence/integration_evidence.py",
    "evidence/integration_checks.py",
    "evidence/integration_runner.py",
    "evidence/approved_capture_runner.py",
    "evidence/approved_control_plane_runner.py",
    "evidence/approved_pipeline_runner.py",
    "evidence/approved_warehouse_runner.py",
    "evidence/approved_warehouse_fault_runner.py",
    "evidence/approved_business_path_runner.py",
    "evidence/business_path_driver.py",
    "evidence/business_path_evidence.py",
    "evidence/business_path_plan.py",
    "evidence/business_path_release_proof.py",
    "evidence/candidate_certification.py",
    "evidence/release_readiness.py",
)


NAVIGATION_READMES = (
    "capture/README.md",
    "apply/README.md",
    "data_plane/README.md",
    "metadata/README.md",
    "quality/README.md",
    "quality/reconciliation/README.md",
    "orchestration/README.md",
    "execution/README.md",
    "adapters/README.md",
    "recovery/README.md",
    "certification/README.md",
    "certification/fabric/README.md",
    "evidence/integration/README.md",
    "evidence/business_paths/README.md",
    "evidence/release/README.md",
    "extensions/README.md",
)


def test_canonical_modules_import_from_new_bounded_contexts() -> None:
    for module_name in CANONICAL_MODULES:
        module = importlib.import_module(module_name)
        module_path = Path(module.__file__).resolve()
        assert SRC.resolve() in module_path.parents, (module_name, module_path)


def test_pre_refactor_module_files_are_removed_not_shimmed() -> None:
    for relative_path in OLD_PATHS:
        assert not (SRC / relative_path).exists(), relative_path

    assert not (ROOT / "certification").exists()
    assert (ROOT / "certification_harness").is_dir()


def test_stable_package_navigation_readmes_exist() -> None:
    for relative_path in NAVIGATION_READMES:
        assert (SRC / relative_path).is_file(), relative_path
