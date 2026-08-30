from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "fabric_data_framework"

REMOVED_ROOT_EVIDENCE_MODULES = {
    "integration_evidence.py",
    "integration_checks.py",
    "integration_evidence_merge.py",
    "integration_runner.py",
    "approved_control_plane_runner.py",
    "approved_pipeline_runner.py",
    "approved_capture_runner.py",
    "approved_warehouse_runner.py",
    "approved_warehouse_fault_runner.py",
}


def test_root_evidence_compatibility_modules_are_not_present():
    present = sorted(
        filename
        for filename in REMOVED_ROOT_EVIDENCE_MODULES
        if (PACKAGE_ROOT / filename).exists()
    )
    assert present == []


def test_evidence_package_has_no_cli_dependency():
    offenders: list[str] = []
    for path in sorted((PACKAGE_ROOT / "evidence").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "fabric_data_framework.cli" in text or "from ..cli" in text:
            offenders.append(str(path.relative_to(PACKAGE_ROOT)))
    assert offenders == []
