from __future__ import annotations

import json
from pathlib import Path

from fabric_data_framework.cli import main
from fabric_data_framework.integration_evidence import (
    IntegrationEvidenceStatus,
    load_integration_evidence_manifest,
)


WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"
ITEM_ID = "22222222-2222-2222-2222-222222222222"


def _paths(tmp_path: Path):
    spec_path = tmp_path / "spec.json"
    config_path = tmp_path / "runner.json"
    spec_path.write_text(
        Path("examples/dev_integration_evidence_spec.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    config_path.write_text(
        Path("examples/dev_integration_runner_config.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return spec_path, config_path


def test_preflight_can_stage_read_only_item_check_without_database_runtime_values(
    tmp_path, monkeypatch
):
    spec_path, config_path = _paths(tmp_path)
    output = tmp_path / "plan.json"
    monkeypatch.setenv("FABRIC_ACCESS_TOKEN", "ephemeral-token-that-must-not-be-retained")
    monkeypatch.delenv("FABRIC_CONTROL_PLANE_DATABASE_URL", raising=False)
    monkeypatch.delenv("FABRIC_WAREHOUSE_DATABASE_URL", raising=False)

    assert (
        main(
            [
                "integration-run-preflight",
                "--config",
                str(config_path),
                "--spec",
                str(spec_path),
                "--check-id",
                "fabric.item.read",
                "--require-ready",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["check_ids"] == ["fabric.item.read"]
    assert payload["missing_runtime_env_vars"] == []
    assert payload["mutating_check_ids"] == []
    assert "ephemeral-token-that-must-not-be-retained" not in output.read_text(
        encoding="utf-8"
    )


def test_full_preflight_requires_runtime_values_and_explicit_mutation_authorization(
    tmp_path, monkeypatch
):
    spec_path, config_path = _paths(tmp_path)
    output = tmp_path / "plan.json"
    monkeypatch.setenv("FABRIC_ACCESS_TOKEN", "token")
    monkeypatch.setenv("FABRIC_CONTROL_PLANE_DATABASE_URL", "secret-db-url")
    monkeypatch.setenv("FABRIC_WAREHOUSE_DATABASE_URL", "secret-wh-url")

    assert (
        main(
            [
                "integration-run-preflight",
                "--config",
                str(config_path),
                "--spec",
                str(spec_path),
                "--require-ready",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "integration-run-preflight",
                "--config",
                str(config_path),
                "--spec",
                str(spec_path),
                "--allow-mutating-checks",
                "--require-ready",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    rendered = output.read_text(encoding="utf-8")
    assert "secret-db-url" not in rendered
    assert "secret-wh-url" not in rendered


class _FakeFabricRestClient:
    wrong_item = False

    def __init__(self, *, token_provider):
        self.token_provider = token_provider

    def _request(self, method, path, *, expected_statuses):
        assert self.token_provider() == "live-ephemeral-token"
        assert method == "GET"
        assert path == f"workspaces/{WORKSPACE_ID}/items/{ITEM_ID}"
        assert expected_statuses == frozenset({200})
        observed = (
            "99999999-9999-9999-9999-999999999999"
            if self.wrong_item
            else ITEM_ID
        )
        return {"id": observed, "displayName": "DEV item"}, {}


def test_item_smoke_writes_partial_manifest_and_never_retains_access_token(
    tmp_path, monkeypatch
):
    spec_path, config_path = _paths(tmp_path)
    output = tmp_path / "item-smoke-manifest.json"
    monkeypatch.setenv("FABRIC_ACCESS_TOKEN", "live-ephemeral-token")
    monkeypatch.setattr("fabric_data_framework.cli.FabricRestClient", _FakeFabricRestClient)
    _FakeFabricRestClient.wrong_item = False

    assert (
        main(
            [
                "integration-item-smoke-run",
                "--config",
                str(config_path),
                "--spec",
                str(spec_path),
                "--check-id",
                "fabric.item.read",
                "--evidence-reference",
                "approved-dev:item-smoke:artifact-1",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    manifest = load_integration_evidence_manifest(output)
    by_id = {item.check_id: item for item in manifest.results}
    assert by_id["fabric.item.read"].status is IntegrationEvidenceStatus.PASS
    assert by_id["fabric.pipeline"].status is IntegrationEvidenceStatus.NOT_RUN
    assert manifest.certified is False
    assert "live-ephemeral-token" not in output.read_text(encoding="utf-8")


def test_item_smoke_identity_mismatch_is_retained_as_sanitized_fail(
    tmp_path, monkeypatch
):
    spec_path, config_path = _paths(tmp_path)
    output = tmp_path / "item-smoke-manifest.json"
    monkeypatch.setenv("FABRIC_ACCESS_TOKEN", "live-ephemeral-token")
    monkeypatch.setattr("fabric_data_framework.cli.FabricRestClient", _FakeFabricRestClient)
    _FakeFabricRestClient.wrong_item = True

    assert (
        main(
            [
                "integration-item-smoke-run",
                "--config",
                str(config_path),
                "--spec",
                str(spec_path),
                "--check-id",
                "fabric.item.read",
                "--evidence-reference",
                "approved-dev:item-smoke:artifact-2",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    manifest = load_integration_evidence_manifest(output)
    result = next(item for item in manifest.results if item.check_id == "fabric.item.read")
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert result.detail == "integration check runner raised ValueError"
    rendered = output.read_text(encoding="utf-8")
    assert "99999999-9999-9999-9999-999999999999" not in rendered
    assert "live-ephemeral-token" not in rendered
