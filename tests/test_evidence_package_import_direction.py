from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).parents[1] / "src" / "fabric_data_framework"

ROOT_COMPATIBILITY_MODULES = {
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


def test_root_compatibility_modules_point_only_to_evidence_package():
    for filename in ROOT_COMPATIBILITY_MODULES:
        text = (PACKAGE_ROOT / filename).read_text(encoding="utf-8")
        assert ".evidence." in text
        assert "_sys.modules[__name__] = _module" in text


def test_evidence_package_has_no_cli_dependency():
    offenders: list[str] = []
    for path in sorted((PACKAGE_ROOT / "evidence").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "fabric_data_framework.cli" in text or "from ..cli" in text:
            offenders.append(str(path.relative_to(PACKAGE_ROOT)))
    assert offenders == []
