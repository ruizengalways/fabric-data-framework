import json
from pathlib import Path

from fabric_data_framework.cli import main
from fabric_data_framework.control_plane.schema import CONTROL_PLANE_SCHEMA_VERSION


def test_cli_certifies_sqlite_reference_after_explicit_migration(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'control.db'}"
    output = tmp_path / "certification.json"

    assert main(["control-plane-migrate", "--database-url", database_url]) == 0
    assert (
        main(
            [
                "control-plane-certify",
                "--database-url",
                database_url,
                "--profile",
                "sqlite_reference_v1",
                "--run-conformance",
                "--require-reference-certified",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["observed_dialect"] == "sqlite"
    assert report["schema_version"] == CONTROL_PLANE_SCHEMA_VERSION == 5
    assert report["reference_certified"] is True
    assert report["production_certified"] is False


def test_cli_refuses_to_label_sqlite_as_production_certified(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'control.db'}"
    evidence_path = tmp_path / "external-evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "identity_access_control_reference": "ticket:iam-1",
                "network_security_reference": "ticket:network-1",
                "backup_restore_reference": "drill:restore-1",
                "availability_recovery_reference": "drill:ha-1",
                "monitoring_alerting_reference": "runbook:monitoring-1",
                "retention_governance_reference": "policy:retention-1",
            }
        ),
        encoding="utf-8",
    )

    assert main(["control-plane-migrate", "--database-url", database_url]) == 0
    assert (
        main(
            [
                "control-plane-certify",
                "--database-url",
                database_url,
                "--profile",
                "sqlite_reference_v1",
                "--run-conformance",
                "--external-evidence",
                str(evidence_path),
                "--require-production-certified",
            ]
        )
        == 2
    )


def test_cli_production_requirement_never_runs_without_explicit_conformance_opt_in(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'control.db'}"

    assert main(["control-plane-migrate", "--database-url", database_url]) == 0
    assert (
        main(
            [
                "control-plane-certify",
                "--database-url",
                database_url,
                "--profile",
                "fabric_sql_database_v1",
                "--require-production-certified",
            ]
        )
        == 2
    )
