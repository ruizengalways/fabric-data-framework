from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest

from fabric_data_framework.adapters.fabric.rest import FabricRestError
from fabric_data_framework.certification.fabric.assets import (
    COPY_JOB_DISPLAY_NAME,
    DEFINITION_READ_BACK_STATUS,
    ENVIRONMENT_DISPLAY_NAME,
    PIPELINE_DISPLAY_NAME,
    PIPELINE_PARAMETER_CONTRACT_STATUS,
    SPARK_JOB_DISPLAY_NAME,
    FabricCertificationAssetClient,
    FabricDefinitionPart,
    FabricItemDefinition,
    assert_definition_read_back_matches,
    build_certification_fabric_asset_plan,
)
from fabric_data_framework.deployment.candidate_artifact import CandidateArtifactManifest


WORKSPACE = UUID("11111111-1111-1111-1111-111111111111")
LAKEHOUSE = UUID("22222222-2222-2222-2222-222222222222")
ENVIRONMENT = UUID("33333333-3333-3333-3333-333333333333")
SPARK_JOB = UUID("44444444-4444-4444-4444-444444444444")


def _manifest(path: Path) -> CandidateArtifactManifest:
    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return CandidateArtifactManifest(
        schema_version=1,
        package_name="fabric-data-framework",
        framework_version="0.4.0",
        candidate_git_sha="a" * 40,
        workflow_run_id=1,
        workflow_run_attempt=1,
        wheel_filename=path.name,
        wheel_sha256=digest,
    )


def _decode_json(definition: FabricItemDefinition, path: str):
    part = next(item for item in definition.parts if item.path == path)
    return json.loads(base64.b64decode(part.payload).decode("utf-8"))


def _build(tmp_path: Path):
    wheel = tmp_path / "fabric_data_framework-0.4.0-py3-none-any.whl"
    wheel.write_bytes(b"exact-candidate-wheel")
    return build_certification_fabric_asset_plan(
        workspace_id=WORKSPACE,
        lakehouse_id=LAKEHOUSE,
        candidate_manifest=_manifest(wheel),
        candidate_wheel_path=wheel,
        environment_id=ENVIRONMENT,
        spark_job_id=SPARK_JOB,
        control_plane_sql_server="control.datawarehouse.fabric.microsoft.com",
        control_plane_sql_database="control",
        warehouse_sql_server="warehouse.datawarehouse.fabric.microsoft.com",
        warehouse_sql_database="warehouse",
        certification_root="/lakehouse/default/Files/framework_cert",
    )


def test_asset_plan_is_deterministic_and_embeds_exact_wheel(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert first.definition_hashes == second.definition_hashes
    assert first.candidate_wheel_sha256 == second.candidate_wheel_sha256
    env_part = first.environment_definition.parts[0]
    assert env_part.path.endswith(first.candidate_wheel_filename)
    assert base64.b64decode(env_part.payload) == b"exact-candidate-wheel"


def test_sjd_v2_binds_exact_environment_lakehouse_and_framework_entrypoint(tmp_path):
    plan = _build(tmp_path)
    assert plan.spark_job_definition.format == "SparkJobDefinitionV2"

    config = _decode_json(plan.spark_job_definition, "SparkJobDefinitionV1.json")
    assert config["executableFile"] == "main.py"
    assert config["language"] == "Python"
    assert config["defaultLakehouseArtifactId"] == str(LAKEHOUSE)
    assert config["environmentArtifactId"] == str(ENVIRONMENT)
    main = next(
        item for item in plan.spark_job_definition.parts if item.path == "Main/main.py"
    )
    decoded = base64.b64decode(main.payload).decode("utf-8")
    assert "fabric_data_framework.certification.fabric.fabric_job" in decoded
    assert "main()" in decoded


def test_copy_job_is_secret_free_same_lakehouse_table_to_table(tmp_path):
    plan = _build(tmp_path)
    content = _decode_json(plan.copy_job_definition, "copyjob-content.json")

    source = content["properties"]["source"]
    destination = content["properties"]["destination"]
    assert source["type"] == "LakehouseTable"
    assert destination["type"] == "LakehouseTable"
    assert source["connectionSettings"] == destination["connectionSettings"]
    assert source["connectionSettings"]["typeProperties"] == {
        "workspaceId": str(WORKSPACE),
        "artifactId": str(LAKEHOUSE),
        "rootFolder": "Tables",
    }
    activity = content["activities"][0]["properties"]
    assert activity["source"]["datasetSettings"]["table"] == "cert_copy_source"
    assert activity["destination"]["datasetSettings"]["table"] == "cert_copy_landing"
    assert activity["destination"]["writeBehavior"] == "Overwrite"
    rendered = json.dumps(content).lower()
    for marker in ("password", "token", "secret", "externalreferences"):
        assert marker not in rendered


def test_pipeline_has_exact_seven_parameters_and_forwards_all_to_sjd(tmp_path):
    plan = _build(tmp_path)
    content = _decode_json(plan.pipeline_definition, "pipeline-content.json")
    properties = content["properties"]
    expected = {
        "framework_pipeline_run_id",
        "framework_dataset_run_id",
        "dataset_id",
        "run_mode",
        "attempt",
        "effective_config_hash",
        "execution_plan_hash",
    }
    assert set(properties["parameters"]) == expected

    activity = properties["activities"][0]
    assert activity["type"] == "SparkJobDefinition"
    type_properties = activity["typeProperties"]
    assert type_properties["sparkJobDefinitionId"] == str(SPARK_JOB)
    assert type_properties["environmentId"] == str(ENVIRONMENT)
    arguments = type_properties["commandLineArguments"]
    for name in sorted(expected):
        assert f"@{{pipeline().parameters.{name}}}" in arguments
    assert "--runtime-config-b64 " in arguments
    assert "password=" not in arguments.lower()
    assert "bearer " not in arguments.lower()


def test_read_back_ignores_platform_and_canonicalizes_json():
    expected_json = {"b": 2, "a": 1}
    expected = FabricItemDefinition(
        format=None,
        parts=(
            FabricDefinitionPart(
                path="content.json",
                payload=base64.b64encode(
                    json.dumps(expected_json, separators=(",", ":")).encode()
                ).decode(),
            ),
        ),
    )
    observed = {
        "definition": {
            "parts": [
                {
                    "path": "content.json",
                    "payload": base64.b64encode(
                        json.dumps({"a": 1, "b": 2}, indent=2).encode()
                    ).decode(),
                    "payloadType": "InlineBase64",
                },
                {
                    "path": ".platform",
                    "payload": base64.b64encode(b"provider").decode(),
                    "payloadType": "InlineBase64",
                },
            ]
        }
    }
    assert_definition_read_back_matches(expected, observed)


def test_read_back_mismatch_fails_closed():
    expected = FabricItemDefinition(
        format=None,
        parts=(
            FabricDefinitionPart(
                path="Main/main.py",
                payload=base64.b64encode(b"expected").decode(),
            ),
        ),
    )
    observed = {
        "definition": {
            "parts": [
                {
                    "path": "Main/main.py",
                    "payload": base64.b64encode(b"different").decode(),
                    "payloadType": "InlineBase64",
                }
            ]
        }
    }
    with pytest.raises(FabricRestError, match="differs"):
        assert_definition_read_back_matches(expected, observed)


class _FakeClient(FabricCertificationAssetClient):
    _IDS = {
        ENVIRONMENT_DISPLAY_NAME: UUID("33333333-3333-3333-3333-333333333333"),
        SPARK_JOB_DISPLAY_NAME: UUID("44444444-4444-4444-4444-444444444444"),
        COPY_JOB_DISPLAY_NAME: UUID("55555555-5555-5555-5555-555555555555"),
        PIPELINE_DISPLAY_NAME: UUID("66666666-6666-6666-6666-666666666666"),
    }

    def __init__(self):
        super().__init__(
            token_provider=lambda: "token",
            sleeper=lambda _: None,
            clock=lambda: 0.0,
            default_poll_seconds=0,
        )
        self.items: dict[UUID, dict[str, object]] = {}
        self.definitions: dict[UUID, dict[str, object]] = {}
        self.calls: list[tuple[str, str]] = []

    def _request(self, method, path_or_url, *, payload=None, expected_statuses):
        del expected_statuses
        self.calls.append((method, path_or_url))
        if method == "GET" and "/items" in path_or_url:
            parsed = urlparse(path_or_url)
            query = parse_qs(parsed.query)
            selected = query.get("type", [None])[0]
            values = [
                {
                    "id": str(item_id),
                    "workspaceId": str(WORKSPACE),
                    "displayName": value["displayName"],
                    "type": value["type"],
                }
                for item_id, value in self.items.items()
                if selected is None or value["type"] == selected
            ]
            return {"value": values}, {}

        if method == "POST" and path_or_url == f"workspaces/{WORKSPACE}/items":
            assert payload is not None
            display_name = payload["displayName"]
            item_id = self._IDS[display_name]
            self.items[item_id] = {
                "displayName": display_name,
                "type": payload["type"],
            }
            self.definitions[item_id] = payload["definition"]
            return {
                "id": str(item_id),
                "workspaceId": str(WORKSPACE),
                "displayName": display_name,
                "type": payload["type"],
            }, {}

        if method == "POST" and "/updateDefinition?" in path_or_url:
            item_id = UUID(path_or_url.split("/items/")[1].split("/")[0])
            assert payload is not None
            self.definitions[item_id] = payload["definition"]
            return None, {}

        if method == "POST" and path_or_url.endswith("/getDefinition"):
            item_id = UUID(path_or_url.split("/items/")[1].split("/")[0])
            definition = json.loads(json.dumps(self.definitions[item_id]))
            definition.setdefault("parts", []).append(
                {
                    "path": ".platform",
                    "payload": base64.b64encode(b"provider").decode(),
                    "payloadType": "InlineBase64",
                }
            )
            return {"definition": definition}, {}

        if method == "POST" and "/staging/publish?beta=false" in path_or_url:
            return {"status": "Submitted"}, {}

        raise AssertionError(f"unexpected fake request {method} {path_or_url}")


def _bootstrap(client: _FakeClient, tmp_path: Path, *, allow: bool):
    wheel = tmp_path / "fabric_data_framework-0.4.0-py3-none-any.whl"
    wheel.write_bytes(b"exact-candidate-wheel")
    return client.bootstrap(
        workspace_id=WORKSPACE,
        lakehouse_id=LAKEHOUSE,
        candidate_manifest=_manifest(wheel),
        candidate_wheel_path=wheel,
        control_plane_sql_server="control.datawarehouse.fabric.microsoft.com",
        control_plane_sql_database="control",
        warehouse_sql_server="warehouse.datawarehouse.fabric.microsoft.com",
        warehouse_sql_database="warehouse",
        certification_root="/lakehouse/default/Files/framework_cert",
        allow_item_mutation=allow,
    )


def test_bootstrap_requires_explicit_mutation_authorization(tmp_path):
    client = _FakeClient()
    with pytest.raises(PermissionError, match="not authorized"):
        _bootstrap(client, tmp_path, allow=False)
    assert client.items == {}


def test_bootstrap_creates_publishes_readbacks_then_updates_idempotently(tmp_path):
    client = _FakeClient()
    first = _bootstrap(client, tmp_path, allow=True)

    assert [item.action for item in first.assets] == ["CREATED"] * 4
    assert first.definition_read_back_status == DEFINITION_READ_BACK_STATUS
    assert first.pipeline_parameter_contract_status == PIPELINE_PARAMETER_CONTRACT_STATUS
    assert any(
        path.endswith(
            f"/environments/{_FakeClient._IDS[ENVIRONMENT_DISPLAY_NAME]}"
            "/staging/publish?beta=false"
        )
        for method, path in client.calls
        if method == "POST"
    )
    first_ids = tuple(item.item_id for item in first.assets)

    client.calls.clear()
    second = _bootstrap(client, tmp_path, allow=True)
    assert tuple(item.item_id for item in second.assets) == first_ids
    assert [item.action for item in second.assets] == ["UPDATED"] * 4
    assert sum(
        "/updateDefinition?updateMetadata=false" in path for _, path in client.calls
    ) == 4


def test_duplicate_exact_named_item_fails_closed(tmp_path):
    client = _FakeClient()
    env_id = _FakeClient._IDS[ENVIRONMENT_DISPLAY_NAME]
    client.items[env_id] = {
        "displayName": ENVIRONMENT_DISPLAY_NAME,
        "type": "Environment",
    }
    other = UUID("77777777-7777-7777-7777-777777777777")
    client.items[other] = {
        "displayName": ENVIRONMENT_DISPLAY_NAME,
        "type": "Environment",
    }
    client.definitions[env_id] = {"parts": []}
    client.definitions[other] = {"parts": []}
    with pytest.raises(FabricRestError, match="multiple Fabric Environment"):
        _bootstrap(client, tmp_path, allow=True)


class _LroClient(FabricCertificationAssetClient):
    def __init__(self, status):
        super().__init__(
            token_provider=lambda: "token",
            sleeper=lambda _: None,
            clock=lambda: 0.0,
            default_poll_seconds=0,
        )
        self.status = status

    def _request(self, method, path_or_url, *, payload=None, expected_statuses):
        del payload, expected_statuses
        if (
            method == "GET"
            and path_or_url.startswith("operations/")
            and not path_or_url.endswith("/result")
        ):
            return {"status": self.status}, {}
        if method == "GET" and path_or_url.endswith("/result"):
            return {"ok": True}, {}
        raise AssertionError(path_or_url)


def test_lro_unknown_status_fails_closed():
    client = _LroClient("FutureStatus")
    with pytest.raises(FabricRestError, match="unsupported status"):
        client._wait_operation(
            {"x-ms-operation-id": "88888888-8888-8888-8888-888888888888"},
            want_result=False,
        )


def test_lro_succeeded_can_return_result():
    client = _LroClient("Succeeded")
    result = client._wait_operation(
        {"x-ms-operation-id": "88888888-8888-8888-8888-888888888888"},
        want_result=True,
    )
    assert result == {"ok": True}
