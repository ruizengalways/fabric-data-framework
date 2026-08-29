import json
from pathlib import Path

from fabric_data_framework.cli import main


CONFIG = {
    "dataset_id": "crm.customer",
    "source": {"system": "crm", "object": "dbo.Customer"},
    "target": {"layer": "silver", "object": "customer"},
    "load": {
        "capture_strategy": "WATERMARK",
        "apply_strategy": "UPSERT",
        "merge_key": ["customer_id"],
        "watermark": {"column": "modified_at", "tie_breaker": ["customer_id"]},
    },
    "orchestration": {"execution_group": "crm_daily"},
    "quality": {"policy_name": "standard", "quarantine_policy": "reject_bad_rows"},
    "reconciliation": {"policy_name": "row_accounting"},
}


def _materialize(tmp_path: Path) -> str:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "crm.customer.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'control.db'}"
    assert (
        main(
            [
                "metadata-materialize",
                "--database-url",
                database_url,
                "--config-dir",
                str(config_dir),
                "--domain",
                "customer",
                "--domain-git-sha",
                "a" * 40,
            ]
        )
        == 0
    )
    return database_url


def test_cli_control_plane_status_writes_single_dataset_snapshot(tmp_path: Path):
    database_url = _materialize(tmp_path)
    output = tmp_path / "status.json"

    assert (
        main(
            [
                "control-plane-status",
                "--database-url",
                database_url,
                "--dataset-id",
                "crm.customer",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["dataset_id"] == "crm.customer"
    assert payload["latest_run"] is None
    assert payload["quarantine_backlog"] == {"open_batches": 0, "open_rows": 0}


def test_cli_control_plane_status_lists_dataset_overview(tmp_path: Path):
    database_url = _materialize(tmp_path)
    output = tmp_path / "overview.json"

    assert (
        main(
            [
                "control-plane-status",
                "--database-url",
                database_url,
                "--output",
                str(output),
            ]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [item["dataset_id"] for item in payload] == ["crm.customer"]
