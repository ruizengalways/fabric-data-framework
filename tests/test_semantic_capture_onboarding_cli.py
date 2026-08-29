import json
from pathlib import Path

from fabric_data_framework.cli import main


WATERMARK_CONFIG = {
    "dataset_id": "crm.customer",
    "source": {"system": "crm", "object": "dbo.Customer"},
    "target": {"layer": "silver", "object": "customer"},
    "load": {
        "capture_strategy": "WATERMARK",
        "apply_strategy": "SCD1",
        "business_key": ["customer_id"],
        "merge_key": ["customer_id"],
        "watermark": {
            "column": "modified_at",
            "tie_breaker": ["customer_id"],
            "overlap_window_seconds": 900,
        },
        "event_time_column": "modified_at",
    },
    "orchestration": {"execution_group": "crm_daily"},
    "quality": {"policy_name": "standard", "quarantine_policy": "reject_bad_rows"},
    "reconciliation": {"policy_name": "row_accounting"},
}


def _write_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "crm.customer.json").write_text(
        json.dumps(WATERMARK_CONFIG), encoding="utf-8"
    )
    return config_dir


def test_cli_validates_cheatsheet_semantic_onboarding_and_writes_contract(tmp_path: Path):
    config_dir = _write_config(tmp_path)
    selections = tmp_path / "semantic-selections.json"
    selections.write_text(
        json.dumps(
            [
                {
                    "dataset_id": "crm.customer",
                    "cheatsheet_pattern": "WATERMARK_LOOKBACK_RAW",
                    "history_claim": "OBSERVED_CHANGES",
                    "delete_claim": "NONE",
                    "rationale": "Retain raw extraction observations.",
                    "known_limitations": ["Hard deletes are not visible."],
                }
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "semantic-report.json"

    assert (
        main(
            [
                "capture-semantic-onboarding-validate",
                "--config-dir",
                str(config_dir),
                "--selections",
                str(selections),
                "--require-all",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report[0]["selection"]["cheatsheet_pattern"] == "WATERMARK_LOOKBACK_RAW"
    assert report[0]["contract"]["bronze_contract"] == "RAW_OBSERVATION"
    assert report[0]["contract"]["bronze_write_mode"] == "APPEND"
    assert report[0]["contract"]["history_fidelity"] == "OBSERVED_CHANGES"


def test_cli_semantic_onboarding_fails_closed_on_wrong_exact_pattern(tmp_path: Path):
    config_dir = _write_config(tmp_path)
    selections = tmp_path / "semantic-selections.json"
    selections.write_text(
        json.dumps(
            [
                {
                    "dataset_id": "crm.customer",
                    "cheatsheet_pattern": "WATERMARK_CURRENT",
                    "rationale": "Incorrectly claims strict watermark despite overlap.",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "capture-semantic-onboarding-validate",
                "--config-dir",
                str(config_dir),
                "--selections",
                str(selections),
                "--require-all",
            ]
        )
        == 2
    )


def test_cli_semantic_onboarding_require_all_rejects_missing_selection(tmp_path: Path):
    config_dir = _write_config(tmp_path)
    selections = tmp_path / "semantic-selections.json"
    selections.write_text("[]", encoding="utf-8")

    assert (
        main(
            [
                "capture-semantic-onboarding-validate",
                "--config-dir",
                str(config_dir),
                "--selections",
                str(selections),
                "--require-all",
            ]
        )
        == 2
    )
