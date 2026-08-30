from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fabric_data_framework import cli_router
from fabric_data_framework.evidence.approved_capture_runner import ApprovedCaptureRunConfig
from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    ExecutionEngine,
    ExecutionPolicy,
    LoadPolicy,
    OrchestrationPolicy,
    ProgressOwner,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
)
from fabric_data_framework.delivery import build_release_manifest
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


EXTENSION_ARTIFACT = "fabric-customer-0.4.0.dev1-py3-none-any.whl"


def _write(path: Path, value) -> None:
    payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifacts(tmp_path: Path):
    dataset = DatasetConfig(
        dataset_id="crm.customer_copy",
        source=SourceConfig(system="crm", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.REPLACE,
            watermark=WatermarkConfig(column="updated_at", overlap_window_seconds=60),
        ),
        orchestration=OrchestrationPolicy(execution_group="daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
        execution=ExecutionPolicy(
            engine=ExecutionEngine.FABRIC_COPY_JOB,
            progress_owner=ProgressOwner.FABRIC_NATIVE,
        ),
    )
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _write(config_dir / "crm.customer_copy.json", dataset)
    release = build_release_manifest(
        domain="customer",
        domain_release_version="0.4.0-dev",
        domain_git_sha="1" * 40,
        framework_version="0.4.0",
        configs=(dataset,),
        config_schema_version=1,
        fabric_item_manifest_version="dev-v1",
        build_id="capture-cli-test",
    ).model_copy(update={"artifact_sha256": {EXTENSION_ARTIFACT: "a" * 64}})
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
                check_id="fabric.copy",
                kind=IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
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
                check_id="fabric.copy",
                kind=IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
                status=IntegrationEvidenceStatus.NOT_RUN,
            ),
        ),
    )
    runner = ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=release.bundle.release_hash,
        bindings=(
            IntegrationCheckPhysicalBinding(
                check_id="fabric.copy",
                workspace_id=uuid4(),
                item_id=uuid4(),
            ),
        ),
    )
    capture = ApprovedCaptureRunConfig(
        check_id="fabric.copy",
        dataset_id="crm.customer_copy",
        landing_reference="bronze.crm_customer_copy",
        observation_extension="crm.copy.observe",
        extension_artifact_name=EXTENSION_ARTIFACT,
    )
    paths = {
        "runner": tmp_path / "runner.json",
        "spec": tmp_path / "spec.json",
        "prerequisite": tmp_path / "prerequisite.json",
        "release": tmp_path / "release.json",
        "capture": tmp_path / "capture.json",
    }
    _write(paths["runner"], runner)
    _write(paths["spec"], spec)
    _write(paths["prerequisite"], prerequisite)
    _write(paths["release"], release)
    _write(paths["capture"], capture)
    return paths, config_dir, spec, capture


def _argv(paths, config_dir, output, report, *, allow=True):
    values = [
        "integration-capture-run",
        "--config",
        str(paths["runner"]),
        "--spec",
        str(paths["spec"]),
        "--prerequisite-manifest",
        str(paths["prerequisite"]),
        "--release-manifest",
        str(paths["release"]),
        "--config-dir",
        str(config_dir),
        "--capture-config",
        str(paths["capture"]),
        "--evidence-reference",
        "artifact:copy-run",
        "--report-output",
        str(report),
        "--output",
        str(output),
    ]
    if allow:
        values.append("--allow-capture-execution")
    return values


def test_capture_cli_routes_exact_artifacts_and_writes_report_and_partial_manifest(
    tmp_path: Path, monkeypatch
):
    paths, config_dir, spec, capture = _artifacts(tmp_path)
    output = tmp_path / "capture-partial.json"
    report = tmp_path / "capture-report.json"
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
                check_id="fabric.copy",
                kind=IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
                status=IntegrationEvidenceStatus.PASS,
                dataset_run_id=uuid4(),
                workspace_id=uuid4(),
                item_id=uuid4(),
                native_job_instance_id=uuid4(),
                root_activity_id=uuid4(),
                evidence_references=("artifact:copy-run",),
            ),
        ),
    )
    observed = {}

    def fake_execute(**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(
            manifest=expected,
            report={
                "check_id": "fabric.copy",
                "run_config_hash": capture.run_config_hash,
            },
        )

    monkeypatch.setattr(cli_router, "execute_approved_capture", fake_execute)
    rc = cli_router.main(_argv(paths, config_dir, output, report))

    assert rc == 0
    assert observed["capture_config"].check_id == "fabric.copy"
    assert observed["allow_capture_execution"] is True
    assert observed["evidence_references"] == ("artifact:copy-run",)
    assert output.exists()
    assert report.exists()
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["results"][2]["status"] == "PASS"
    retained_report = json.loads(report.read_text(encoding="utf-8"))
    assert retained_report["check_id"] == "fabric.copy"


def test_capture_cli_preflight_failure_does_not_write_outputs(tmp_path: Path, monkeypatch):
    paths, config_dir, _, _ = _artifacts(tmp_path)
    output = tmp_path / "capture-partial.json"
    report = tmp_path / "capture-report.json"

    def fake_execute(**kwargs):
        assert kwargs["allow_capture_execution"] is False
        raise ValueError("approved capture preflight is not ready")

    monkeypatch.setattr(cli_router, "execute_approved_capture", fake_execute)
    rc = cli_router.main(_argv(paths, config_dir, output, report, allow=False))

    assert rc == 2
    assert not output.exists()
    assert not report.exists()
