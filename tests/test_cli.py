import json
from pathlib import Path

from fabric_data_framework.cli import main


CONFIG = {
    "dataset_id": "crm.customer",
    "source": {"system": "crm", "object": "dbo.Customer"},
    "target": {"layer": "silver", "object": "customer"},
    "load": {
        "capture_strategy": "WATERMARK",
        "apply_strategy": "SCD2",
        "business_key": ["customer_id"],
        "merge_key": ["customer_id"],
        "watermark": {"column": "modified_at", "tie_breaker": ["customer_id"]},
        "tracked_columns": ["name"],
    },
    "orchestration": {"execution_group": "crm_daily"},
    "quality": {"policy_name": "standard", "quarantine_policy": "reject_bad_rows"},
    "reconciliation": {"policy_name": "row_accounting"},
}


def test_cli_can_migrate_materialize_build_manifest_and_plan(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "crm.customer.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'control.db'}"

    assert main(["control-plane-migrate", "--database-url", database_url]) == 0
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

    manifest_path = tmp_path / "release.json"
    assert (
        main(
            [
                "release-manifest",
                "--domain",
                "customer",
                "--domain-release-version",
                "0.1.0",
                "--domain-git-sha",
                "a" * 40,
                "--config-dir",
                str(config_dir),
                "--build-id",
                "local-1",
                "--output",
                str(manifest_path),
            ]
        )
        == 0
    )

    bindings_path = tmp_path / "bindings.json"
    bindings_path.write_text(
        json.dumps(
            {
                "profile_name": "customer-dev",
                "environment": "DEV",
                "domain": "customer",
                "resources": [],
            }
        ),
        encoding="utf-8",
    )
    plan_path = tmp_path / "plan.json"
    assert (
        main(
            [
                "deployment-plan",
                "--manifest",
                str(manifest_path),
                "--bindings",
                str(bindings_path),
                "--output",
                str(plan_path),
            ]
        )
        == 0
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["request"]["target_environment"] == "DEV"
    assert "watermark" in plan["protected_environment_local_state_tables"]
