from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/fabric_data_framework/evidence/manual_certification.py"
RUNBOOK = ROOT / "docs/human/FIRST_FABRIC_NOTEBOOK_TEST.md"
MANUAL_DOC = ROOT / "docs/human/MANUAL_CERTIFICATION.md"


def test_notebook_ui_avoids_fabric_unsupported_output_widget():
    source = SOURCE.read_text(encoding="utf-8")
    assert "widgets.Output(" not in source
    assert "widgets.Dropdown(" in source
    assert "ManualCertificationCheckStatus.NOT_RUN" in source
    assert "ManualCertificationCheckStatus.PASS" in source
    assert "ManualCertificationCheckStatus.FAIL" in source


def test_first_company_fabric_test_runbook_keeps_execution_and_recording_distinct():
    runbook = RUNBOOK.read_text(encoding="utf-8")
    manual = MANUAL_DOC.read_text(encoding="utf-8")

    for token in (
        "CANDIDATE.json",
        "lakehouse.smoke",
        "full.replace",
        "watermark.scd1",
        "watermark.scd2",
        "retry.idempotency",
        "reconciliation.fail_closed",
        "warehouse.commit = NOT_RUN",
        "warehouse.ambiguous_commit = NOT_RUN",
        "Admin Override",
    ):
        assert token in runbook

    assert "dropdowns **record** what you observed; they do not execute the tests" in runbook
    assert "The form in this document does not run Lakehouse/SCD/Warehouse tests by itself" in manual
    assert "ipywidgets.Output" in manual
    assert "unsupported" in manual.lower()
