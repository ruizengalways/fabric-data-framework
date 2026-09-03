from __future__ import annotations

from pathlib import Path

from fabric_data_framework.certification import simple as simple_module


def _prepare_root(tmp_path: Path) -> Path:
    root = tmp_path / "framework_cert"
    root.mkdir()
    (root / "CANDIDATE.json").write_text("{}\n", encoding="utf-8")
    (root / "fabric_data_framework-0.4.0-py3-none-any.whl").write_bytes(b"wheel")
    return root


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


def test_simple_certification_passes_explicit_runtime_environment_without_retaining_it(
    monkeypatch,
    tmp_path,
):
    root = _prepare_root(tmp_path)
    customer = root / "customer-inputs"
    customer.mkdir()
    runtime_environment = {
        "CONTROL_PLANE_DATABASE_URL": "runtime-control-plane-value",
        "WAREHOUSE_DATABASE_URL": "runtime-warehouse-value",
    }
    observed = {}

    def fake_unified(**kwargs):
        observed.update(kwargs)
        return object()

    monkeypatch.setattr(simple_module, "run_unified_certification", fake_unified)

    simple_module.certify(
        spark=object(),
        certification_root=root,
        runtime_environment=runtime_environment,
        allow_live_mutations=True,
    )

    assert observed["customer_inputs_root"] == customer
    assert observed["environ"] is runtime_environment
    assert observed["allow_control_plane_writes"] is True
    assert observed["allow_pipeline_execution"] is True
    assert observed["allow_capture_execution"] is True
    assert observed["allow_warehouse_execution"] is True
    assert observed["allow_business_path_execution"] is True
    assert observed["allow_warehouse_session_termination"] is False
