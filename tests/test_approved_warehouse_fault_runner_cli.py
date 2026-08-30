from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import fabric_data_framework.cli as cli
from fabric_data_framework.cli import approved as cli_approved
from fabric_data_framework.evidence.approved_warehouse_fault_runner import (
    ApprovedWarehouseFaultDrillConfig,
)
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
from fabric_data_framework.evidence.integration_runner import ApprovedIntegrationRunnerConfig


MUTATION_ARTIFACT = "fabric-customer-0.4.0.dev1-py3-none-any.whl"
FAULT_ARTIFACT = "fabric-customer-faults-0.4.0.dev1-py3-none-any.whl"


def _write(path: Path, model) -> None:
    value = model.model_dump(mode="json") if hasattr(model, "model_dump") else model
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifacts(tmp_path: Path):
    dataset = DatasetConfig(
        dataset_id="sales.order",
        source=SourceConfig(system="erp", object="dbo.SalesOrder"),
        target=TargetConfig(layer="gold", object="sales_order"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="sales"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
    )
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _write(config_dir / "sales.order.json", dataset)
    release = build_release_manifest(
        domain="sales",
        domain_release_version="0.4.0-dev",
        domain_git_sha="1" * 40,
        framework_version="0.4.0",
        configs=(dataset,),
        config_schema_version=1,
        fabric_item_manifest_version="dev-v1",
        build_id="warehouse-fault-cli-test",
    ).model_copy(
        update={
            "artifact_sha256": {
                MUTATION_ARTIFACT: "a" * 64,
                FAULT_ARTIFACT: "b" * 64,
            }
        }
    )
    spec = IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="sales",
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
                check_id="warehouse.commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="warehouse.ambiguous-commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL,
            ),
        ),
    )
    now = datetime.now(timezone.utc)
    prerequisite = IntegrationEvidenceManifest(
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
                check_id="warehouse.commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
                status=IntegrationEvidenceStatus.PASS,
                operation_key="a" * 64,
                evidence_references=("artifact:warehouse-normal",),
            ),
            IntegrationEvidenceCheckResult(
                check_id="warehouse.ambiguous-commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL,
                status=IntegrationEvidenceStatus.NOT_RUN,
            ),
        ),
    )
    runner = ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="sales",
        framework_version="0.4.0",
        release_hash=release.bundle.release_hash,
        control_plane_profile="fabric_sql_database_v1",
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
        warehouse_database_url_env_var="WAREHOUSE_DATABASE_URL",
    )
    fault = ApprovedWarehouseFaultDrillConfig(
        check_id="warehouse.ambiguous-commit",
        dataset_id="sales.order",
        operation_kind="EVIDENCE_AMBIGUOUS_COMMIT_DRILL",
        target_reference="warehouse.dbo.sales_order",
        mutation_extension="sales.order.evidence-mutation",
        mutation_extension_artifact_name=MUTATION_ARTIFACT,
        mutation_payload={"order_id": 42},
        fault_injector_extension="sales.order.commit-ack-fault",
        fault_injector_artifact_name=FAULT_ARTIFACT,
        fault_payload={"fault_case": "commit-ack-disconnect"},
    )
    paths = {
        "runner": tmp_path / "runner.json",
        "spec": tmp_path / "spec.json",
        "prerequisite": tmp_path / "prerequisite.json",
        "release": tmp_path / "release.json",
        "fault": tmp_path / "fault.json",
    }
    _write(paths["runner"], runner)
    _write(paths["spec"], spec)
    _write(paths["prerequisite"], prerequisite)
    _write(paths["release"], release)
    _write(paths["fault"], fault)
    return paths, config_dir, spec, fault


def _argv(paths, config_dir, output, report, *, allow=True):
    args = [
        "integration-warehouse-fault-drill-run",
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
        "--fault-config",
        str(paths["fault"]),
        "--evidence-reference",
        "artifact:warehouse-real-fault",
        "--report-output",
        str(report),
        "--output",
        str(output),
    ]
    if allow:
        args.append("--allow-warehouse-fault-injection")
    return args


def test_fault_drill_cli_routes_exact_inputs_and_writes_report_and_manifest(
    tmp_path, monkeypatch
):
    paths, config_dir, spec, fault = _artifacts(tmp_path)
    output = tmp_path / "fault-partial.json"
    report = tmp_path / "fault-report.json"
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
                check_id="warehouse.commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
                status=IntegrationEvidenceStatus.NOT_RUN,
            ),
            IntegrationEvidenceCheckResult(
                check_id="warehouse.ambiguous-commit",
                kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL,
                status=IntegrationEvidenceStatus.PASS,
                dataset_run_id=uuid4(),
                operation_key="b" * 64,
                evidence_references=("artifact:warehouse-real-fault",),
            ),
        ),
    )
    observed = {}

    def fake_execute(**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(
            manifest=expected,
            report={
                "check_id": fault.check_id,
                "run_config_hash": fault.run_config_hash,
            },
        )

    monkeypatch.setattr(
        cli_approved,
        "execute_approved_warehouse_fault_drill",
        fake_execute,
    )
    rc = cli.main(_argv(paths, config_dir, output, report))

    assert rc == 0
    assert observed["run_config"].check_id == "warehouse.ambiguous-commit"
    assert observed["allow_warehouse_fault_injection"] is True
    assert observed["evidence_references"] == ("artifact:warehouse-real-fault",)
    assert output.exists()
    assert report.exists()


def test_fault_drill_cli_preflight_failure_does_not_write_outputs(tmp_path, monkeypatch):
    paths, config_dir, _, _ = _artifacts(tmp_path)
    output = tmp_path / "fault-partial.json"
    report = tmp_path / "fault-report.json"

    def fake_execute(**kwargs):
        assert kwargs["allow_warehouse_fault_injection"] is False
        raise ValueError("approved Warehouse fault-drill preflight is not ready")

    monkeypatch.setattr(
        cli_approved,
        "execute_approved_warehouse_fault_drill",
        fake_execute,
    )
    rc = cli.main(_argv(paths, config_dir, output, report, allow=False))

    assert rc == 2
    assert not output.exists()
    assert not report.exists()
