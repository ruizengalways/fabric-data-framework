from __future__ import annotations

import json
from uuid import uuid4

import fabric_data_framework.cli as cli
from fabric_data_framework.certification.fabric.bindings import (
    CertificationBindingItem,
    CertificationIntegrationBindings,
)


def _result():
    workspace_id = uuid4()
    item_read_id = uuid4()
    pipeline_id = uuid4()
    copy_id = uuid4()
    spark_id = uuid4()
    return CertificationIntegrationBindings(
        workspace_id=workspace_id,
        item_read_id=item_read_id,
        pipeline_item_id=pipeline_id,
        copy_job_id=copy_id,
        spark_job_id=spark_id,
        resolved_items=(
            CertificationBindingItem(
                role="item_read",
                item_id=item_read_id,
                display_name="fdf-cert-read",
                item_type="Lakehouse",
            ),
            CertificationBindingItem(
                role="pipeline",
                item_id=pipeline_id,
                display_name="fdf-cert-pipeline",
                item_type="DataPipeline",
            ),
            CertificationBindingItem(
                role="copy_job",
                item_id=copy_id,
                display_name="fdf-cert-copy",
                item_type="CopyJob",
            ),
            CertificationBindingItem(
                role="spark_job",
                item_id=spark_id,
                display_name="fdf-cert-spark",
                item_type="SparkJobDefinition",
            ),
        ),
    )


def _argv(*, output=None):
    values = [
        "discover-certification-bindings",
        "--workspace-id",
        str(uuid4()),
        "--item-read-name",
        "fdf-cert-read",
        "--item-read-type",
        "Lakehouse",
        "--pipeline-name",
        "fdf-cert-pipeline",
        "--copy-job-name",
        "fdf-cert-copy",
        "--spark-job-name",
        "fdf-cert-spark",
    ]
    if output is not None:
        values.extend(["--output", str(output)])
    return values


def test_binding_discovery_cli_routes_non_secret_names_and_writes_json(tmp_path, monkeypatch):
    expected = _result()
    observed = {}

    def fake_discover(**kwargs):
        observed.update(kwargs)
        return expected

    monkeypatch.setattr(
        "fabric_data_framework.cli.certification.discover_certification_bindings_from_names",
        fake_discover,
    )
    monkeypatch.setenv("FABRIC_ACCESS_TOKEN", "must-never-be-retained")
    output = tmp_path / "bindings.json"

    rc = cli.main(_argv(output=output))

    assert rc == 0
    assert observed["item_read_name"] == "fdf-cert-read"
    assert observed["item_read_type"] == "Lakehouse"
    assert observed["pipeline_name"] == "fdf-cert-pipeline"
    assert observed["copy_job_name"] == "fdf-cert-copy"
    assert observed["spark_job_name"] == "fdf-cert-spark"
    assert callable(observed["token_provider"])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["workspace_id"] == str(expected.workspace_id)
    assert "must-never-be-retained" not in output.read_text(encoding="utf-8")


def test_binding_discovery_cli_reports_local_ambiguity_without_writing_output(
    tmp_path, monkeypatch, capsys
):
    def fail(**_):
        raise ValueError("Fabric item binding is ambiguous")

    monkeypatch.setattr(
        "fabric_data_framework.cli.certification.discover_certification_bindings_from_names",
        fail,
    )
    output = tmp_path / "bindings.json"

    rc = cli.main(_argv(output=output))

    assert rc == 2
    assert not output.exists()
    assert "ambiguous" in capsys.readouterr().err
