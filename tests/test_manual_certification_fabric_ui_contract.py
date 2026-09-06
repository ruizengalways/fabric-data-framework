from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/fabric_data_framework/evidence/manual_certification.py"
ADMIN_WORKFLOW = ROOT / ".github/workflows/candidate-admin-certification.yml"


def test_notebook_ui_avoids_fabric_unsupported_output_widget():
    source = SOURCE.read_text(encoding="utf-8")
    assert "widgets.Output(" not in source
    assert "widgets.Dropdown(" in source
    assert "ManualCertificationCheckStatus.NOT_RUN" in source
    assert "ManualCertificationCheckStatus.PASS" in source
    assert "ManualCertificationCheckStatus.FAIL" in source


def test_supported_admin_fallback_implementation_remains_present():
    assert SOURCE.is_file()
    assert ADMIN_WORKFLOW.is_file()
