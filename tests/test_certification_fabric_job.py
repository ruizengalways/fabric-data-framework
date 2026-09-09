from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from fabric_data_framework.certification.fabric import fabric_job
from fabric_data_framework.metadata.config import DatasetStatus


class _Engine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


def _runtime_blob() -> str:
    return fabric_job.encode_certification_runtime_config(
        control_plane_sql_server="control.fabric.microsoft.com",
        control_plane_sql_database="FrameworkControl",
        warehouse_sql_server="warehouse.fabric.microsoft.com",
        warehouse_sql_database="FrameworkWarehouse",
    )


def _child_argv(blob: str) -> list[str]:
    return [
        "--runtime-config-b64",
        blob,
        "--framework-pipeline-run-id",
        str(uuid4()),
        "--framework-dataset-run-id",
        str(uuid4()),
        "--dataset-id",
        "cert.full_replace",
        "--run-mode",
        "NORMAL",
        "--attempt",
        "1",
        "--effective-config-hash",
        "a" * 64,
        "--execution-plan-hash",
        "b" * 64,
    ]


def test_runtime_config_is_credential_free_and_round_trips_to_fabric_user_env():
    blob = _runtime_blob()
    runtime, root = fabric_job._runtime_from_blob(blob, {})

    assert runtime["FABRIC_SQL_AUTH_MODE"] == "fabric-user"
    assert runtime["CONTROL_PLANE_SQL_SERVER"] == "control.fabric.microsoft.com"
    assert runtime["WAREHOUSE_SQL_DATABASE"] == "FrameworkWarehouse"
    assert str(root) == "/lakehouse/default/Files/framework_cert"
    assert "password" not in blob.lower()


def test_runtime_config_rejects_secret_like_values():
    with pytest.raises(ValueError, match="appears to contain credentials"):
        fabric_job.encode_certification_runtime_config(
            control_plane_sql_server="server.example",
            control_plane_sql_database="password=not-allowed",
            warehouse_sql_server="warehouse.example",
            warehouse_sql_database="warehouse",
        )


def test_direct_spark_payload_and_pipeline_child_arguments_are_mutually_exclusive():
    with pytest.raises(ValueError, match="cannot be combined"):
        fabric_job.main(["--payload-b64", "e30=", "--dataset-id", "cert.spark"])


def test_valid_framework_failed_outcome_keeps_provider_entry_successful(monkeypatch):
    control_engine = _Engine()
    warehouse_engine = _Engine()
    monkeypatch.setattr(
        fabric_job,
        "load_candidate_artifact_manifest",
        lambda _path: SimpleNamespace(
            framework_version="0.4.0",
            candidate_git_sha="c" * 40,
        ),
    )
    monkeypatch.setattr(fabric_job, "installed_version", lambda _name: "0.4.0")
    monkeypatch.setattr(fabric_job, "load_dataset_configs", lambda _path: (object(),))
    monkeypatch.setattr(fabric_job, "SqlAlchemyControlPlaneRepository", lambda *args, **kwargs: object())
    observed = {}

    def fake_execute_pipeline_child(*, repository, request, executor):
        observed["repository"] = repository
        observed["request"] = request
        observed["executor"] = executor
        return SimpleNamespace(
            dataset_id=request.dataset_id,
            dataset_run_id=request.framework_dataset_run_id,
            status=DatasetStatus.FAILED,
        )

    monkeypatch.setattr(fabric_job, "execute_pipeline_child", fake_execute_pipeline_child)

    result = fabric_job.main(
        _child_argv(_runtime_blob()),
        environ={},
        control_plane_engine_factory=lambda _runtime: control_engine,
        warehouse_engine_factory=lambda _runtime: warehouse_engine,
    )

    assert result == 0
    assert observed["request"].dataset_id == "cert.full_replace"
    assert control_engine.disposed is True
    assert warehouse_engine.disposed is True


def test_child_argument_contract_is_complete_before_any_engine_is_created():
    calls = []
    with pytest.raises(ValueError, match="arguments are incomplete"):
        fabric_job.main(
            ["--runtime-config-b64", _runtime_blob()],
            control_plane_engine_factory=lambda _runtime: calls.append("control"),
            warehouse_engine_factory=lambda _runtime: calls.append("warehouse"),
        )
    assert calls == []
