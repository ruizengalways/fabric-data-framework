from __future__ import annotations

from uuid import uuid4

import pytest

from fabric_data_framework.adapters.fabric.items import FabricItem
from fabric_data_framework.certification.bindings import discover_certification_bindings


class _Catalog:
    def __init__(self, by_type):
        self.by_type = by_type
        self.calls = []

    def list_items(self, *, workspace_id, item_type=None):
        self.calls.append((workspace_id, item_type))
        return tuple(self.by_type.get(item_type, ()))


def _item(workspace_id, name, item_type):
    return FabricItem(
        id=uuid4(),
        workspace_id=workspace_id,
        display_name=name,
        item_type=item_type,
    )


def _catalog(workspace_id):
    items = {
        "Lakehouse": (_item(workspace_id, "fdf-cert-read", "Lakehouse"),),
        "DataPipeline": (_item(workspace_id, "fdf-cert-pipeline", "DataPipeline"),),
        "CopyJob": (_item(workspace_id, "fdf-cert-copy", "CopyJob"),),
        "SparkJobDefinition": (
            _item(workspace_id, "fdf-cert-spark", "SparkJobDefinition"),
        ),
    }
    return _Catalog(items), items


def test_discovery_resolves_exact_names_and_emits_workflow_uuid_inputs():
    workspace_id = uuid4()
    catalog, items = _catalog(workspace_id)

    result = discover_certification_bindings(
        client=catalog,
        workspace_id=workspace_id,
        item_read_name="fdf-cert-read",
        item_read_type="Lakehouse",
        pipeline_name="fdf-cert-pipeline",
        copy_job_name="fdf-cert-copy",
        spark_job_name="fdf-cert-spark",
    )

    assert result.workspace_id == workspace_id
    assert result.item_read_id == items["Lakehouse"][0].id
    assert result.pipeline_item_id == items["DataPipeline"][0].id
    assert result.copy_job_id == items["CopyJob"][0].id
    assert result.spark_job_id == items["SparkJobDefinition"][0].id
    assert result.workflow_dispatch_inputs() == {
        "workspace_id": str(workspace_id),
        "item_read_id": str(items["Lakehouse"][0].id),
        "pipeline_item_id": str(items["DataPipeline"][0].id),
        "copy_job_id": str(items["CopyJob"][0].id),
        "spark_job_id": str(items["SparkJobDefinition"][0].id),
    }
    assert [item.role for item in result.resolved_items] == [
        "item_read",
        "pipeline",
        "copy_job",
        "spark_job",
    ]
    assert [item_type for _, item_type in catalog.calls] == [
        "Lakehouse",
        "DataPipeline",
        "CopyJob",
        "SparkJobDefinition",
    ]


def test_discovery_is_case_sensitive_and_fails_when_exact_name_is_absent():
    workspace_id = uuid4()
    catalog, _ = _catalog(workspace_id)

    with pytest.raises(ValueError, match="no exact Fabric item match"):
        discover_certification_bindings(
            client=catalog,
            workspace_id=workspace_id,
            item_read_name="FDF-CERT-READ",
            item_read_type="Lakehouse",
            pipeline_name="fdf-cert-pipeline",
            copy_job_name="fdf-cert-copy",
            spark_job_name="fdf-cert-spark",
        )


def test_discovery_fails_closed_on_duplicate_exact_name_and_type():
    workspace_id = uuid4()
    catalog, items = _catalog(workspace_id)
    catalog.by_type["DataPipeline"] = (
        items["DataPipeline"][0],
        _item(workspace_id, "fdf-cert-pipeline", "DataPipeline"),
    )

    with pytest.raises(ValueError, match="ambiguous"):
        discover_certification_bindings(
            client=catalog,
            workspace_id=workspace_id,
            item_read_name="fdf-cert-read",
            item_read_type="Lakehouse",
            pipeline_name="fdf-cert-pipeline",
            copy_job_name="fdf-cert-copy",
            spark_job_name="fdf-cert-spark",
        )


def test_same_type_lists_are_cached_when_item_read_uses_pipeline_type():
    workspace_id = uuid4()
    pipeline = _item(workspace_id, "fdf-cert-pipeline", "DataPipeline")
    read_item = _item(workspace_id, "fdf-cert-read-pipeline", "DataPipeline")
    catalog = _Catalog(
        {
            "DataPipeline": (read_item, pipeline),
            "CopyJob": (_item(workspace_id, "fdf-cert-copy", "CopyJob"),),
            "SparkJobDefinition": (
                _item(workspace_id, "fdf-cert-spark", "SparkJobDefinition"),
            ),
        }
    )

    discover_certification_bindings(
        client=catalog,
        workspace_id=workspace_id,
        item_read_name="fdf-cert-read-pipeline",
        item_read_type="DataPipeline",
        pipeline_name="fdf-cert-pipeline",
        copy_job_name="fdf-cert-copy",
        spark_job_name="fdf-cert-spark",
    )

    assert [item_type for _, item_type in catalog.calls].count("DataPipeline") == 1


def test_discovery_output_never_contains_token_material():
    workspace_id = uuid4()
    catalog, _ = _catalog(workspace_id)
    result = discover_certification_bindings(
        client=catalog,
        workspace_id=workspace_id,
        item_read_name="fdf-cert-read",
        item_read_type="Lakehouse",
        pipeline_name="fdf-cert-pipeline",
        copy_job_name="fdf-cert-copy",
        spark_job_name="fdf-cert-spark",
    )

    rendered = result.model_dump_json()
    assert "token" not in rendered.lower()
    assert "secret" not in rendered.lower()
