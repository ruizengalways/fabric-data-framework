from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from fabric_data_framework.certification import simple as simple_module
from fabric_data_framework.certification.models import CertificationCheckStatus


def _prepare_root(tmp_path: Path) -> Path:
    root = tmp_path / "framework_cert"
    root.mkdir()
    (root / "CANDIDATE.json").write_text("{}\n", encoding="utf-8")
    (root / "fabric_data_framework-0.4.0-py3-none-any.whl").write_bytes(b"wheel")
    return root


def _prepare_customer(root: Path) -> Path:
    customer = root / "customer-inputs"
    customer.mkdir()
    runner = {
        "environment": "DEV",
        "domain": "customer-certification",
        "framework_version": "0.4.0",
        "release_hash": "0" * 64,
        "framework_artifact_sha256": "1" * 64,
        "fabric_access_token_env_var": "FABRIC_ACCESS_TOKEN",
        "control_plane_database_url_env_var": "CONTROL_PLANE_DATABASE_URL",
        "warehouse_database_url_env_var": "WAREHOUSE_DATABASE_URL",
        "warehouse_admin_database_url_env_var": "WAREHOUSE_ADMIN_DATABASE_URL",
        "control_plane_profile": "fabric_sql_database_v1",
        "bindings": [],
    }
    (customer / "runner-config.json").write_text(
        json.dumps(runner) + "\n",
        encoding="utf-8",
    )
    return customer


def test_simple_certification_does_not_invent_customer_or_database_configuration(
    monkeypatch,
    tmp_path,
):
    root = _prepare_root(tmp_path)
    observed = {}

    def fake_unified(**kwargs):
        observed.update(kwargs)
        return object()

    monkeypatch.setattr(simple_module, "run_unified_certification", fake_unified)

    simple_module.certify(spark=object(), certification_root=root)

    assert observed["customer_inputs_root"] is None
    assert observed["environ"] is None
    assert observed["allow_control_plane_writes"] is False
    assert observed["allow_warehouse_execution"] is False


def test_simple_certification_scopes_explicit_runtime_environment_for_extensions(
    monkeypatch,
    tmp_path,
):
    root = _prepare_root(tmp_path)
    customer = _prepare_customer(root)
    runtime_environment = {
        "CONTROL_PLANE_DATABASE_URL": "runtime-control-plane-value",
        "WAREHOUSE_DATABASE_URL": "runtime-warehouse-value",
    }
    observed = {}
    monkeypatch.setenv("CONTROL_PLANE_DATABASE_URL", "original-control-plane")
    monkeypatch.delenv("WAREHOUSE_DATABASE_URL", raising=False)
    monkeypatch.setattr(simple_module, "_notebook_fabric_token", lambda: "runtime-token")

    def fake_unified(**kwargs):
        observed.update(kwargs)
        assert os.environ["CONTROL_PLANE_DATABASE_URL"] == "runtime-control-plane-value"
        assert os.environ["WAREHOUSE_DATABASE_URL"] == "runtime-warehouse-value"
        assert os.environ["FABRIC_ACCESS_TOKEN"] == "runtime-token"
        return object()

    monkeypatch.setattr(simple_module, "run_unified_certification", fake_unified)

    simple_module.certify(
        spark=object(),
        certification_root=root,
        runtime_environment=runtime_environment,
        allow_live_mutations=True,
    )

    assert observed["customer_inputs_root"] == customer
    assert observed["environ"] is not runtime_environment
    assert observed["environ"]["CONTROL_PLANE_DATABASE_URL"] == "runtime-control-plane-value"
    assert observed["environ"]["WAREHOUSE_DATABASE_URL"] == "runtime-warehouse-value"
    assert observed["environ"]["FABRIC_ACCESS_TOKEN"] == "runtime-token"
    assert observed["auto_notebook_token"] is False
    assert observed["allow_control_plane_writes"] is True
    assert observed["allow_pipeline_execution"] is True
    assert observed["allow_capture_execution"] is True
    assert observed["allow_warehouse_execution"] is True
    assert observed["allow_business_path_execution"] is True
    assert observed["allow_warehouse_session_termination"] is False
    assert os.environ["CONTROL_PLANE_DATABASE_URL"] == "original-control-plane"
    assert "WAREHOUSE_DATABASE_URL" not in os.environ
    assert "FABRIC_ACCESS_TOKEN" not in os.environ


def test_control_plane_bootstrap_requires_bounded_pass_and_exact_customer_identity(
    monkeypatch,
    tmp_path,
):
    root = _prepare_root(tmp_path)
    customer = _prepare_customer(root)
    (customer / "INPUTS.json").write_text(
        json.dumps(
            {
                "candidate_git_sha": "a" * 40,
                "candidate_wheel_sha256": "b" * 64,
                "framework_version": "0.4.0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (customer / "project/config/datasets").mkdir(parents=True)
    (customer / "release-manifest.json").write_text("{}\n", encoding="utf-8")

    bounded = SimpleNamespace(
        candidate_git_sha="a" * 40,
        artifact_sha256="b" * 64,
        framework_version="0.4.0",
        checks=(SimpleNamespace(status=CertificationCheckStatus.PASS),),
    )
    monkeypatch.setattr(simple_module, "run_bounded_certification", lambda **_: bounded)

    runner = SimpleNamespace(
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL"
    )
    monkeypatch.setattr(
        simple_module,
        "load_approved_integration_runner_config",
        lambda _: runner,
    )
    release = SimpleNamespace(
        domain="customer-certification",
        bundle=SimpleNamespace(
            domain_git_sha="c" * 40,
            framework_version="0.4.0",
            config_bundle_hash="d" * 64,
        ),
    )
    monkeypatch.setattr(simple_module, "load_release_manifest", lambda _: release)
    configs = (object(),)
    monkeypatch.setattr(simple_module, "load_dataset_configs", lambda _: configs)

    disposed = []
    engine = SimpleNamespace(dispose=lambda: disposed.append(True))
    monkeypatch.setattr(simple_module, "create_engine", lambda _: engine)
    materialized = []

    def fake_materialize(observed_engine, **kwargs):
        materialized.append((observed_engine, kwargs))
        return "d" * 64

    monkeypatch.setattr(simple_module, "materialize_semantic_metadata", fake_materialize)

    simple_module._bootstrap_control_plane_after_bounded_preflight(
        spark=object(),
        candidate_manifest=root / "CANDIDATE.json",
        wheel=root / "fabric_data_framework-0.4.0-py3-none-any.whl",
        customer_inputs_root=customer,
        output_dir=root / "certification-output",
        environment="DEV",
        lakehouse_base_path="Files/framework_cert",
        runtime_environment={
            "CONTROL_PLANE_DATABASE_URL": "runtime-control-plane-value"
        },
    )

    assert len(materialized) == 1
    observed_engine, kwargs = materialized[0]
    assert observed_engine is engine
    assert kwargs["configs"] is configs
    assert kwargs["domain"] == "customer-certification"
    assert kwargs["domain_git_sha"] == "c" * 40
    assert kwargs["framework_version"] == "0.4.0"
    assert disposed == [True]


def test_control_plane_bootstrap_does_not_mutate_after_bounded_failure(
    monkeypatch,
    tmp_path,
):
    root = _prepare_root(tmp_path)
    customer = _prepare_customer(root)
    bounded = SimpleNamespace(
        checks=(SimpleNamespace(status=CertificationCheckStatus.FAIL),),
    )
    monkeypatch.setattr(simple_module, "run_bounded_certification", lambda **_: bounded)
    monkeypatch.setattr(
        simple_module,
        "create_engine",
        lambda _: (_ for _ in ()).throw(AssertionError("must not create engine")),
    )

    simple_module._bootstrap_control_plane_after_bounded_preflight(
        spark=object(),
        candidate_manifest=root / "CANDIDATE.json",
        wheel=root / "fabric_data_framework-0.4.0-py3-none-any.whl",
        customer_inputs_root=customer,
        output_dir=root / "certification-output",
        environment="DEV",
        lakehouse_base_path="Files/framework_cert",
        runtime_environment={
            "CONTROL_PLANE_DATABASE_URL": "runtime-control-plane-value"
        },
    )


def test_simple_certification_bootstraps_only_with_explicit_first_time_authorization(
    monkeypatch,
    tmp_path,
):
    root = _prepare_root(tmp_path)
    _prepare_customer(root)
    monkeypatch.setattr(simple_module, "_notebook_fabric_token", lambda: "token")
    bootstrap_calls = []
    monkeypatch.setattr(
        simple_module,
        "_bootstrap_control_plane_after_bounded_preflight",
        lambda **kwargs: bootstrap_calls.append(kwargs),
    )
    monkeypatch.setattr(simple_module, "run_unified_certification", lambda **_: object())

    simple_module.certify(
        spark=object(),
        certification_root=root,
        runtime_environment={
            "CONTROL_PLANE_DATABASE_URL": "runtime-control-plane-value",
            "WAREHOUSE_DATABASE_URL": "runtime-warehouse-value",
        },
        allow_live_mutations=True,
        allow_control_plane_migration=False,
    )
    assert bootstrap_calls == []

    simple_module.certify(
        spark=object(),
        certification_root=root,
        runtime_environment={
            "CONTROL_PLANE_DATABASE_URL": "runtime-control-plane-value",
            "WAREHOUSE_DATABASE_URL": "runtime-warehouse-value",
        },
        allow_live_mutations=True,
        allow_control_plane_migration=True,
    )
    assert len(bootstrap_calls) == 1
