from __future__ import annotations

import json
from pathlib import Path

from fabric_data_framework.cli import main
from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceSpec,
)
from fabric_data_framework.evidence.integration_runner import ApprovedIntegrationRunnerConfig


def _write(path: Path, value) -> None:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _spec():
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="control-plane.certify",
                kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            ),
        ),
    )


def _config():
    return ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
        control_plane_profile="fabric_sql_database_v1",
    )


def _external(network="ticket:network-1"):
    return {
        "backend_service_identity_reference": "inventory:fabric-sql-dev",
        "identity_access_control_reference": "ticket:iam-1",
        "network_security_reference": network,
        "backup_restore_reference": "drill:restore-1",
        "availability_recovery_reference": "drill:ha-1",
        "monitoring_alerting_reference": "runbook:monitoring-1",
        "retention_governance_reference": "policy:retention-1",
    }


def _paths(tmp_path: Path):
    config = tmp_path / "runner.json"
    spec = tmp_path / "spec.json"
    external = tmp_path / "external.json"
    report = tmp_path / "report.json"
    manifest = tmp_path / "manifest.json"
    _write(config, _config())
    _write(spec, _spec())
    _write(external, _external())
    return config, spec, external, report, manifest


def _argv(config, spec, external, report, manifest, *, allow=True):
    values = [
        "integration-control-plane-certify-run",
        "--config",
        str(config),
        "--spec",
        str(spec),
        "--check-id",
        "control-plane.certify",
        "--external-evidence",
        str(external),
        "--evidence-reference",
        "artifact:control-plane-certification",
        "--report-output",
        str(report),
        "--output",
        str(manifest),
    ]
    if allow:
        values.append("--allow-conformance-writes")
    return values


def test_cli_requires_explicit_conformance_write_authorization_before_outputs(
    tmp_path: Path, monkeypatch
):
    config, spec, external, report, manifest = _paths(tmp_path)
    monkeypatch.setenv(
        "CONTROL_PLANE_DATABASE_URL",
        f"sqlite:///{tmp_path / 'control.db'}",
    )

    rc = main(_argv(config, spec, external, report, manifest, allow=False))

    assert rc == 2
    assert not report.exists()
    assert not manifest.exists()


def test_cli_real_certification_failure_writes_sanitized_report_and_partial_manifest(
    tmp_path: Path, monkeypatch
):
    config, spec, external, report, manifest = _paths(tmp_path)
    runtime_url = f"sqlite:///{tmp_path / 'runtime-secret-control.db'}"
    monkeypatch.setenv("CONTROL_PLANE_DATABASE_URL", runtime_url)

    rc = main(_argv(config, spec, external, report, manifest, allow=True))

    # SQLite cannot satisfy the production Fabric SQL profile, so this is expected
    # to retain a useful FAIL partial rather than pretending CI is production proof.
    assert rc == 2
    assert report.exists()
    assert manifest.exists()
    retained = report.read_text(encoding="utf-8") + manifest.read_text(encoding="utf-8")
    assert runtime_url not in retained
    parsed = json.loads(manifest.read_text(encoding="utf-8"))
    assert parsed["results"][0]["status"] == "FAIL"
    report_json = json.loads(report.read_text(encoding="utf-8"))
    by_id = {item["check_id"]: item for item in report_json["checks"]}
    assert by_id["dialect_profile"]["status"] == "FAIL"
    assert by_id["transaction_rollback"]["status"] == "NOT_RUN"


def test_cli_rejects_secret_bearing_external_reference_before_writing_outputs(
    tmp_path: Path, monkeypatch
):
    config, spec, external, report, manifest = _paths(tmp_path)
    _write(external, _external("postgresql://alice:s3cr3t@example.test/db"))
    monkeypatch.setenv(
        "CONTROL_PLANE_DATABASE_URL",
        f"sqlite:///{tmp_path / 'control.db'}",
    )

    rc = main(_argv(config, spec, external, report, manifest, allow=True))

    assert rc == 2
    assert not report.exists()
    assert not manifest.exists()
