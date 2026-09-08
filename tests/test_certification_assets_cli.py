from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fabric_data_framework.cli.main import main
import fabric_data_framework.cli.certification_assets as certification_assets_cli


def _candidate_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "package_name": "fabric-data-framework",
                "framework_version": "0.4.0",
                "candidate_git_sha": "a" * 40,
                "workflow_run_id": 1,
                "workflow_run_attempt": 1,
                "wheel_filename": "fabric_data_framework-0.4.0-py3-none-any.whl",
                "wheel_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
    )


def test_bootstrap_certification_assets_cli_routes_exact_inputs_without_mutation(
    tmp_path,
    monkeypatch,
    capsys,
):
    manifest = tmp_path / "CANDIDATE.json"
    wheel = tmp_path / "fabric_data_framework-0.4.0-py3-none-any.whl"
    dependency = tmp_path / "dependency.whl"
    _candidate_manifest(manifest)
    wheel.write_bytes(b"candidate")
    dependency.write_bytes(b"dependency")
    observed = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            observed["client"] = kwargs

        def bootstrap(self, **kwargs):
            observed["bootstrap"] = kwargs
            return SimpleNamespace(
                as_dict=lambda: {
                    "definition_read_back_status": "DEFINITION_READ_BACK_VERIFIED",
                    "pipeline_parameter_contract_status": "PROVIDER_VALIDATION_REQUIRED",
                }
            )

    monkeypatch.setattr(
        certification_assets_cli,
        "FabricCertificationAssetClient",
        _FakeClient,
    )

    code = main(
        [
            "bootstrap-certification-assets",
            "--workspace-id",
            "11111111-1111-1111-1111-111111111111",
            "--lakehouse-id",
            "22222222-2222-2222-2222-222222222222",
            "--candidate-manifest",
            str(manifest),
            "--candidate-wheel",
            str(wheel),
            "--control-plane-sql-server",
            "control.datawarehouse.fabric.microsoft.com",
            "--control-plane-sql-database",
            "control",
            "--warehouse-sql-server",
            "warehouse.datawarehouse.fabric.microsoft.com",
            "--warehouse-sql-database",
            "warehouse",
            "--dependency-wheel",
            str(dependency),
        ]
    )

    assert code == 0
    assert observed["bootstrap"]["allow_item_mutation"] is False
    assert observed["bootstrap"]["dependency_wheels"] == (str(dependency),)
    assert observed["bootstrap"]["candidate_wheel_path"] == str(wheel)
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["definition_read_back_status"] == "DEFINITION_READ_BACK_VERIFIED"
    assert rendered["pipeline_parameter_contract_status"] == "PROVIDER_VALIDATION_REQUIRED"


def test_bootstrap_certification_assets_cli_requires_explicit_mutation_flag(
    tmp_path,
    monkeypatch,
):
    manifest = tmp_path / "CANDIDATE.json"
    wheel = tmp_path / "fabric_data_framework-0.4.0-py3-none-any.whl"
    _candidate_manifest(manifest)
    wheel.write_bytes(b"candidate")
    observed = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            del kwargs

        def bootstrap(self, **kwargs):
            observed.update(kwargs)
            return SimpleNamespace(as_dict=lambda: {"ok": True})

    monkeypatch.setattr(
        certification_assets_cli,
        "FabricCertificationAssetClient",
        _FakeClient,
    )

    code = main(
        [
            "bootstrap-certification-assets",
            "--workspace-id",
            "11111111-1111-1111-1111-111111111111",
            "--lakehouse-id",
            "22222222-2222-2222-2222-222222222222",
            "--candidate-manifest",
            str(manifest),
            "--candidate-wheel",
            str(wheel),
            "--control-plane-sql-server",
            "control.datawarehouse.fabric.microsoft.com",
            "--control-plane-sql-database",
            "control",
            "--warehouse-sql-server",
            "warehouse.datawarehouse.fabric.microsoft.com",
            "--warehouse-sql-database",
            "warehouse",
            "--allow-item-mutation",
        ]
    )
    assert code == 0
    assert observed["allow_item_mutation"] is True
