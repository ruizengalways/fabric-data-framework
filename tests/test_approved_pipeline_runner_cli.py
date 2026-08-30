from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fabric_data_framework import cli
from fabric_data_framework.cli import approved as cli_approved
from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.deployment.delivery import build_release_manifest
from fabric_data_framework.infrastructure import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
)
from fabric_data_framework.evidence.integration_runner import (
    ApprovedIntegrationRunnerConfig,
    IntegrationCheckPhysicalBinding,
)


def _write(path: Path, value) -> None:
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifacts(tmp_path: Path):
    dataset = DatasetConfig(
        dataset_id="crm.customer",
        source=SourceConfig(system="crm", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
    )
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _write(config_dir / "crm.customer.json", dataset)
    release = build_release_manifest(
        domain="customer",
        domain_release_version="0.4.0-dev",
        domain_git_sha="1" * 40,
        framework_version="0.4.0",
        configs=(dataset,),
        config_schema_version=1,
        fabric_item_manifest_version="dev-v1",
        build_id="pipeline-cli-test",
    )
    spec = IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=release.bundle.release_hash,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="control-plane.certify",
                kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            ),
        ),
    )
    prerequisite = IntegrationEvidenceManifest(
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        started_at=release.generated_at,
        completed_at=release.generated_at,
        checks=spec.checks,
        results=(
            IntegrationEvidenceCheckResult(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
                status=IntegrationEvidenceStatus.PASS,
                workspace_id=uuid4(),
                item_id=uuid4(),
                evidence_references=("artifact:item-read",),
            ),
            IntegrationEvidenceCheckResult(
                check_id="control-plane.certify",
                kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
                status=IntegrationEvidenceStatus.PASS,
                evidence_references=("artifact:control-plane",),
            ),
            IntegrationEvidenceCheckResult(
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
                status=IntegrationEvidenceStatus.NOT_RUN,
            ),
        ),
    )
    runner = ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=release.bundle.release_hash,
        control_plane_profile="fabric_sql_database_v1",
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
        bindings=(
            IntegrationCheckPhysicalBinding(
                check_id="fabric.pipeline",
                workspace_id=uuid4(),
                item_id=uuid4(),
            ),
        ),
    )
    config_path = tmp_path / "runner.json"
    spec_path = tmp_path / "spec.json"
    prerequisite_path = tmp_path / "prerequisite.json"
    release_path = tmp_path / "release.json"
    _write(config_path, runner)
    _write(spec_path, spec)
    _write(prerequisite_path, prerequisite)
    _write(release_path, release)
    return config_path, spec_path, prerequisite_path, release_path, config_dir, spec


def _argv(config, spec, prerequisite, release, config_dir, output, *, allow=True):
    values = [
        "integration-pipeline-run",
        "--config",
        str(config),
        "--spec",
        str(spec),
        "--prerequisite-manifest",
        str(prerequisite),
        "--release-manifest",
        str(release),
        "--config-dir",
        str(config_dir),
        "--check-id",
        "fabric.pipeline",
        "--dataset-id",
        "crm.customer",
        "--evidence-reference",
        "artifact:pipeline-run",
        "--output",
        str(output),
    ]
    if allow:
        values.append("--allow-pipeline-execution")
    return values


def test_pipeline_cli_routes_exact_artifacts_and_writes_partial_manifest(tmp_path: Path, monkeypatch):
    config, spec_path, prerequisite, release, config_dir, spec = _artifacts(tmp_path)
    output = tmp_path / "pipeline-partial.json"
    now = datetime.now(timezone.utc)
    expected = IntegrationEvidenceManifest(
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        started_at=now,
        completed_at=now,
        checks=spec.checks,
        results=(
            IntegrationEvidenceCheckResult(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
                status=IntegrationEvidenceStatus.NOT_RUN,
            ),
            IntegrationEvidenceCheckResult(
                check_id="control-plane.certify",
                kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
                status=IntegrationEvidenceStatus.NOT_RUN,
            ),
            IntegrationEvidenceCheckResult(
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
                status=IntegrationEvidenceStatus.PASS,
                framework_pipeline_run_id=uuid4(),
                dataset_run_id=uuid4(),
                workspace_id=uuid4(),
                item_id=uuid4(),
                native_job_instance_id=uuid4(),
                root_activity_id=uuid4(),
                evidence_references=("artifact:pipeline-run",),
            ),
        ),
    )
    observed = {}

    def fake_execute(**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(manifest=expected)

    monkeypatch.setattr(cli_approved, "execute_approved_pipeline", fake_execute)
    rc = cli.main(_argv(config, spec_path, prerequisite, release, config_dir, output))

    assert rc == 0
    assert observed["check_id"] == "fabric.pipeline"
    assert observed["dataset_id"] == "crm.customer"
    assert observed["allow_pipeline_execution"] is True
    assert observed["evidence_references"] == ("artifact:pipeline-run",)
    assert output.exists()
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["results"][2]["status"] == "PASS"


def test_pipeline_cli_failure_does_not_write_manifest(tmp_path: Path, monkeypatch):
    config, spec, prerequisite, release, config_dir, _ = _artifacts(tmp_path)
    output = tmp_path / "pipeline-partial.json"

    def fake_execute(**kwargs):
        assert kwargs["allow_pipeline_execution"] is False
        raise ValueError("approved Pipeline preflight is not ready")

    monkeypatch.setattr(cli_approved, "execute_approved_pipeline", fake_execute)
    rc = cli.main(
        _argv(config, spec, prerequisite, release, config_dir, output, allow=False)
    )

    assert rc == 2
    assert not output.exists()
