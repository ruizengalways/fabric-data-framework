import json

from fabric_data_framework.cli import main


BASE_CONFIG = {
    "dataset_id": "crm.customer",
    "source": {"system": "crm", "object": "dbo.customer"},
    "target": {"layer": "silver", "object": "customer"},
    "load": {
        "capture_strategy": "WATERMARK",
        "apply_strategy": "SCD2",
        "business_key": ["customer_id"],
        "merge_key": ["customer_id"],
        "watermark": {
            "column": "updated_at",
            "tie_breaker": ["customer_id"],
            "overlap_window_seconds": 600,
        },
        "event_time_column": "updated_at",
    },
    "orchestration": {"execution_group": "crm"},
    "quality": {"policy_name": "standard", "quarantine_policy": "row"},
    "reconciliation": {"policy_name": "row_accounting"},
}


def test_capture_onboarding_cli_validates_and_writes_report(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "crm.customer.json").write_text(
        json.dumps(BASE_CONFIG), encoding="utf-8"
    )
    selections = tmp_path / "capture-selections.json"
    selections.write_text(
        json.dumps(
            [
                {
                    "dataset_id": "crm.customer",
                    "capture_pattern": "WATERMARK_LOOKBACK",
                    "bronze_write_mode": "MERGE",
                    "history_claim": "OBSERVED_CHANGES",
                    "delete_claim": "NONE",
                    "rationale": "Source exposes updated_at with bounded late commits.",
                    "known_limitations": ["Hard deletes are not visible."],
                }
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"

    assert (
        main(
            [
                "capture-onboarding-validate",
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
    assert report[0]["dataset_id"] == "crm.customer"
    assert report[0]["canonical_history_fidelity"] == "OBSERVED_CHANGES"
    assert report[0]["canonical_delete_visibility"] == "NONE"


def test_capture_onboarding_cli_rejects_overstated_claim(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "crm.customer.json").write_text(
        json.dumps(BASE_CONFIG), encoding="utf-8"
    )
    selections = tmp_path / "capture-selections.json"
    selections.write_text(
        json.dumps(
            [
                {
                    "dataset_id": "crm.customer",
                    "capture_pattern": "WATERMARK_LOOKBACK",
                    "history_claim": "FULL_EVENT",
                    "rationale": "invalid overclaim",
                }
            ]
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "capture-onboarding-validate",
                "--config-dir",
                str(config_dir),
                "--selections",
                str(selections),
            ]
        )
        == 2
    )


def test_capture_onboarding_cli_require_all_detects_missing_selection(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "crm.customer.json").write_text(
        json.dumps(BASE_CONFIG), encoding="utf-8"
    )
    second = dict(BASE_CONFIG)
    second["dataset_id"] = "crm.contact"
    (config_dir / "crm.contact.json").write_text(json.dumps(second), encoding="utf-8")

    selections = tmp_path / "capture-selections.json"
    selections.write_text(
        json.dumps(
            [
                {
                    "dataset_id": "crm.customer",
                    "capture_pattern": "WATERMARK_LOOKBACK",
                    "rationale": "only one classified",
                    "known_limitations": ["Hard deletes are not visible."],
                }
            ]
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "capture-onboarding-validate",
                "--config-dir",
                str(config_dir),
                "--selections",
                str(selections),
                "--require-all",
            ]
        )
        == 2
    )
