from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fabric_data_framework.cli_router import main
from fabric_data_framework.infrastructure import EnvironmentName
from fabric_data_framework.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
)


NOW = datetime(2026, 8, 29, 13, 0, tzinfo=timezone.utc)
WORKSPACE = UUID("00000000-0000-0000-0000-000000001001")
ITEM = UUID("00000000-0000-0000-0000-000000001002")
PIPELINE_RUN = UUID("00000000-0000-0000-0000-000000001003")
PIPELINE_ITEM = UUID("00000000-0000-0000-0000-000000001004")
PIPELINE_JOB = UUID("00000000-0000-0000-0000-000000001005")
PIPELINE_ROOT = UUID("00000000-0000-0000-0000-000000001006")


def _spec() -> IntegrationEvidenceSpec:
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            ),
        ),
    )


def _not_run(check: IntegrationEvidenceCheckSpec):
    return IntegrationEvidenceCheckResult(
        check_id=check.check_id,
        kind=check.kind,
        status=IntegrationEvidenceStatus.NOT_RUN,
        started_at=NOW,
        completed_at=NOW,
        detail="not run in this stage",
    )


def _item_pass(reference: str = "evidence:item:one"):
    return IntegrationEvidenceCheckResult(
        check_id="fabric.item.read",
        kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
        status=IntegrationEvidenceStatus.PASS,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        workspace_id=WORKSPACE,
        item_id=ITEM,
        evidence_references=(reference,),
    )


def _pipeline_pass():
    return IntegrationEvidenceCheckResult(
        check_id="fabric.pipeline",
        kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        status=IntegrationEvidenceStatus.PASS,
        started_at=NOW + timedelta(minutes=1),
        completed_at=NOW + timedelta(minutes=1, seconds=1),
        framework_pipeline_run_id=PIPELINE_RUN,
        workspace_id=WORKSPACE,
        item_id=PIPELINE_ITEM,
        native_job_instance_id=PIPELINE_JOB,
        root_activity_id=PIPELINE_ROOT,
        evidence_references=("evidence:pipeline:one",),
    )


def _manifest(spec: IntegrationEvidenceSpec, *, item=None, pipeline=None):
    checks = {check.check_id: check for check in spec.checks}
    return IntegrationEvidenceManifest(
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        started_at=NOW,
        completed_at=NOW + timedelta(minutes=2),
        checks=spec.checks,
        results=(
            item or _not_run(checks["fabric.item.read"]),
            pipeline or _not_run(checks["fabric.pipeline"]),
        ),
    )


def _write_model(path: Path, model) -> None:
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_console_merge_combines_two_partials_and_certifies(tmp_path: Path):
    spec = _spec()
    spec_path = tmp_path / "spec.json"
    item_path = tmp_path / "item.json"
    pipeline_path = tmp_path / "pipeline.json"
    output_path = tmp_path / "merged.json"
    _write_model(spec_path, spec)
    _write_model(item_path, _manifest(spec, item=_item_pass()))
    _write_model(pipeline_path, _manifest(spec, pipeline=_pipeline_pass()))

    rc = main(
        [
            "integration-evidence-merge",
            "--spec",
            str(spec_path),
            "--input",
            str(item_path),
            "--input",
            str(pipeline_path),
            "--output",
            str(output_path),
            "--require-certified",
        ]
    )

    assert rc == 0
    merged = json.loads(output_path.read_text(encoding="utf-8"))
    assert [result["status"] for result in merged["results"]] == ["PASS", "PASS"]


def test_require_certified_failure_does_not_write_output(tmp_path: Path):
    spec = _spec()
    spec_path = tmp_path / "spec.json"
    partial_path = tmp_path / "partial.json"
    output_path = tmp_path / "merged.json"
    _write_model(spec_path, spec)
    _write_model(partial_path, _manifest(spec, item=_item_pass()))

    rc = main(
        [
            "integration-evidence-merge",
            "--spec",
            str(spec_path),
            "--input",
            str(partial_path),
            "--output",
            str(output_path),
            "--require-certified",
        ]
    )

    assert rc == 2
    assert not output_path.exists()


def test_merge_conflict_preserves_existing_output_file(tmp_path: Path):
    spec = _spec()
    spec_path = tmp_path / "spec.json"
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    output_path = tmp_path / "merged.json"
    _write_model(spec_path, spec)
    _write_model(first_path, _manifest(spec, item=_item_pass("evidence:item:first")))
    _write_model(second_path, _manifest(spec, item=_item_pass("evidence:item:second")))
    output_path.write_text("retained-existing-evidence\n", encoding="utf-8")

    rc = main(
        [
            "integration-evidence-merge",
            "--spec",
            str(spec_path),
            "--input",
            str(first_path),
            "--input",
            str(second_path),
            "--output",
            str(output_path),
        ]
    )

    assert rc == 2
    assert output_path.read_text(encoding="utf-8") == "retained-existing-evidence\n"


def test_successful_merge_does_not_serialize_runtime_secret_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FABRIC_ACCESS_TOKEN", "runtime-secret-value-never-retain")
    spec = _spec()
    spec_path = tmp_path / "spec.json"
    item_path = tmp_path / "item.json"
    output_path = tmp_path / "merged.json"
    _write_model(spec_path, spec)
    _write_model(item_path, _manifest(spec, item=_item_pass()))

    assert (
        main(
            [
                "integration-evidence-merge",
                "--spec",
                str(spec_path),
                "--input",
                str(item_path),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    assert "runtime-secret-value-never-retain" not in output_path.read_text(encoding="utf-8")


def test_console_router_delegates_existing_commands_unchanged():
    assert main(["validate-tag", "--tag", "v0.4.0", "--version", "0.4.0"]) == 0
