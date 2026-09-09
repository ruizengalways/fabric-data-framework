from datetime import datetime, timezone
from uuid import uuid4

from fabric_data_framework.cli import main
from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.evidence.integration.evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    run_integration_evidence,
    write_integration_evidence_manifest,
)


NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
FRAMEWORK_SHA = "a" * 64
INPUTS_SHA = "b" * 64


def _spec():
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="framework-certification",
        framework_version="0.4.0",
        framework_artifact_sha256=FRAMEWORK_SHA,
        integration_inputs_hash=INPUTS_SHA,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            ),
        ),
    )


def _pass():
    return IntegrationEvidenceCheckResult(
        check_id="fabric.item.read",
        kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
        status=IntegrationEvidenceStatus.PASS,
        started_at=NOW,
        completed_at=NOW,
        workspace_id=uuid4(),
        item_id=uuid4(),
        evidence_references=("dev-evidence:item-read.json",),
    )


def test_cli_requires_exact_certified_manifest(tmp_path, capsys):
    spec = _spec()
    manifest = IntegrationEvidenceManifest(
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        framework_artifact_sha256=spec.framework_artifact_sha256,
        integration_inputs_hash=spec.integration_inputs_hash,
        started_at=NOW,
        completed_at=NOW,
        checks=spec.checks,
        results=(_pass(),),
    )
    spec_path = tmp_path / "evidence-spec.json"
    manifest_path = tmp_path / "evidence-manifest.json"
    spec_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    write_integration_evidence_manifest(manifest, manifest_path)

    assert (
        main(
            [
                "integration-evidence-validate",
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--require-certified",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "certified=true" in output
    assert "manifest_hash=" in output


def test_cli_fails_when_required_check_is_not_pass(tmp_path):
    spec = _spec()
    manifest = run_integration_evidence(spec, runners={}, now=lambda: NOW)
    spec_path = tmp_path / "evidence-spec.json"
    manifest_path = tmp_path / "evidence-manifest.json"
    spec_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    write_integration_evidence_manifest(manifest, manifest_path)

    assert (
        main(
            [
                "integration-evidence-validate",
                "--spec",
                str(spec_path),
                "--manifest",
                str(manifest_path),
                "--require-certified",
            ]
        )
        == 2
    )


def test_runner_ids_not_declared_in_spec_fail_closed():
    spec = _spec()

    try:
        run_integration_evidence(
            spec,
            runners={"fabric.item.typo": _pass},
            now=lambda: NOW,
        )
    except ValueError as exc:
        assert "not declared" in str(exc)
    else:
        raise AssertionError("unexpected runner ID should fail closed")
