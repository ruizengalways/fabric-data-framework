"""Framework-owned Microsoft Fabric certification asset definitions and bootstrap.

The builder side of this module is pure and deterministic: the same exact candidate
wheel bytes and physical identities produce the same item definitions. The bootstrap
client is intentionally separate and mutating operations require explicit authorization.

Real Fabric acceptance remains a provider/runtime concern. In particular, the
parameterized Data Pipeline definition is retained as provider-validation-required
until a real Fabric create/read-back/run proves the current provider contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, UUID, uuid5

from fabric_data_framework.adapters.fabric.items import (
    FabricItem,
    FabricItemCatalogClient,
)
from fabric_data_framework.adapters.fabric.rest import FabricRestError
from fabric_data_framework.deployment.candidate_artifact import (
    CandidateArtifactManifest,
    sha256_file,
)

from .fabric_job import encode_certification_runtime_config


ENVIRONMENT_DISPLAY_NAME = "fabric-framework-certification-env"
SPARK_JOB_DISPLAY_NAME = "fabric-framework-certification-job"
COPY_JOB_DISPLAY_NAME = "fabric-framework-certification-copy"
PIPELINE_DISPLAY_NAME = "fabric-framework-certification-pipeline"

ENVIRONMENT_ITEM_TYPE = "Environment"
SPARK_JOB_ITEM_TYPE = "SparkJobDefinition"
COPY_JOB_ITEM_TYPE = "CopyJob"
PIPELINE_ITEM_TYPE = "DataPipeline"

PIPELINE_PARAMETER_CONTRACT_STATUS = "PROVIDER_VALIDATION_REQUIRED"
DEFINITION_READ_BACK_STATUS = "DEFINITION_READ_BACK_VERIFIED"

_PIPELINE_PARAMETER_NAMES = (
    "framework_pipeline_run_id",
    "framework_dataset_run_id",
    "dataset_id",
    "run_mode",
    "attempt",
    "effective_config_hash",
    "execution_plan_hash",
)
_SUPPORTED_LRO_RUNNING = frozenset({"NotStarted", "Running"})
_SUPPORTED_LRO_TERMINAL = frozenset({"Succeeded", "Failed"})
_INLINE_BASE64 = "InlineBase64"


@dataclass(frozen=True)
class FabricDefinitionPart:
    path: str
    payload: str
    payload_type: str = _INLINE_BASE64

    def as_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "payload": self.payload,
            "payloadType": self.payload_type,
        }


@dataclass(frozen=True)
class FabricItemDefinition:
    format: str | None
    parts: tuple[FabricDefinitionPart, ...]

    def __post_init__(self) -> None:
        if not self.parts:
            raise ValueError("Fabric item definition requires at least one part")
        paths = [part.path for part in self.parts]
        if len(paths) != len(set(paths)):
            raise ValueError("Fabric item definition contains duplicate part paths")
        if any(part.payload_type != _INLINE_BASE64 for part in self.parts):
            raise ValueError("certification definitions only support InlineBase64 payloads")

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "parts": [part.as_dict() for part in self.parts],
        }
        if self.format is not None:
            result["format"] = self.format
        return result

    @property
    def semantic_sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.as_dict(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class CertificationFabricAssetPlan:
    workspace_id: UUID
    lakehouse_id: UUID
    environment_definition: FabricItemDefinition
    spark_job_definition: FabricItemDefinition
    copy_job_definition: FabricItemDefinition
    pipeline_definition: FabricItemDefinition
    candidate_wheel_filename: str
    candidate_wheel_sha256: str

    @property
    def definition_hashes(self) -> dict[str, str]:
        return {
            ENVIRONMENT_DISPLAY_NAME: self.environment_definition.semantic_sha256,
            SPARK_JOB_DISPLAY_NAME: self.spark_job_definition.semantic_sha256,
            COPY_JOB_DISPLAY_NAME: self.copy_job_definition.semantic_sha256,
            PIPELINE_DISPLAY_NAME: self.pipeline_definition.semantic_sha256,
        }


@dataclass(frozen=True)
class CertificationFabricAssetIdentity:
    display_name: str
    item_type: str
    item_id: UUID
    definition_sha256: str
    action: str


@dataclass(frozen=True)
class CertificationFabricBootstrapReport:
    workspace_id: UUID
    lakehouse_id: UUID
    candidate_wheel_filename: str
    candidate_wheel_sha256: str
    assets: tuple[CertificationFabricAssetIdentity, ...]
    definition_read_back_status: str
    pipeline_parameter_contract_status: str

    def as_dict(self) -> dict[str, object]:
        return {
            "workspace_id": str(self.workspace_id),
            "lakehouse_id": str(self.lakehouse_id),
            "candidate_wheel_filename": self.candidate_wheel_filename,
            "candidate_wheel_sha256": self.candidate_wheel_sha256,
            "assets": [
                {
                    "display_name": item.display_name,
                    "item_type": item.item_type,
                    "item_id": str(item.item_id),
                    "definition_sha256": item.definition_sha256,
                    "action": item.action,
                }
                for item in self.assets
            ],
            "definition_read_back_status": self.definition_read_back_status,
            "pipeline_parameter_contract_status": self.pipeline_parameter_contract_status,
        }


def _b64_bytes(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64_text(value: str) -> str:
    return _b64_bytes(value.encode("utf-8"))


def _b64_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return _b64_bytes(encoded)


def _part_json(path: str, payload: object) -> FabricDefinitionPart:
    return FabricDefinitionPart(path=path, payload=_b64_json(payload))


def _safe_plain_name(value: str, *, label: str) -> str:
    name = value.strip()
    if not name or Path(name).name != name:
        raise ValueError(f"{label} must be a plain non-empty file name")
    return name


def _validate_candidate_wheel(
    wheel_path: str | Path,
    manifest: CandidateArtifactManifest,
) -> Path:
    path = Path(wheel_path)
    if not path.is_file():
        raise ValueError(f"candidate wheel does not exist: {path}")
    if path.name != manifest.wheel_filename:
        raise ValueError("candidate wheel filename does not match CANDIDATE.json")
    observed = sha256_file(path)
    if observed != manifest.wheel_sha256:
        raise ValueError("candidate wheel SHA256 does not match CANDIDATE.json")
    return path


def _environment_definition(
    *,
    wheel_path: Path,
    dependency_wheels: Iterable[str | Path] = (),
) -> FabricItemDefinition:
    wheel_paths = [wheel_path]
    seen_names = {wheel_path.name}
    for raw in sorted((Path(item) for item in dependency_wheels), key=lambda item: item.name):
        if not raw.is_file() or raw.suffix != ".whl":
            raise ValueError(f"dependency wheel must be an existing .whl file: {raw}")
        name = _safe_plain_name(raw.name, label="dependency wheel")
        if name in seen_names:
            raise ValueError(f"duplicate environment wheel filename: {name}")
        seen_names.add(name)
        wheel_paths.append(raw)
    parts = tuple(
        FabricDefinitionPart(
            path=f"Libraries/CustomLibraries/{path.name}",
            payload=_b64_bytes(path.read_bytes()),
        )
        for path in wheel_paths
    )
    return FabricItemDefinition(format=None, parts=parts)


def _spark_job_definition(
    *,
    workspace_id: UUID,
    lakehouse_id: UUID,
    environment_id: UUID,
) -> FabricItemDefinition:
    del workspace_id
    main_py = (
        "from fabric_data_framework.certification.fabric_job import main\n"
        "raise SystemExit(main())\n"
    )
    config = {
        "executableFile": "main.py",
        "language": "Python",
        "mainClass": "",
        "commandLineArguments": "",
        "defaultLakehouseArtifactId": str(lakehouse_id),
        "additionalLakehouseIds": [],
        "additionalLibraryUris": [],
        "environmentArtifactId": str(environment_id),
    }
    return FabricItemDefinition(
        format="SparkJobDefinitionV2",
        parts=(
            _part_json("SparkJobDefinitionV1.json", config),
            FabricDefinitionPart(path="Main/main.py", payload=_b64_text(main_py)),
        ),
    )


def _copy_job_definition(
    *,
    workspace_id: UUID,
    lakehouse_id: UUID,
) -> FabricItemDefinition:
    lakehouse_connection = {
        "type": "Lakehouse",
        "typeProperties": {
            "workspaceId": str(workspace_id),
            "artifactId": str(lakehouse_id),
            "rootFolder": "Tables",
        },
    }
    activity_id = uuid5(
        NAMESPACE_URL,
        f"fabric-data-framework:certification:copy:{workspace_id}:{lakehouse_id}",
    )
    content = {
        "properties": {
            "jobMode": "Batch",
            "source": {
                "type": "LakehouseTable",
                "connectionSettings": lakehouse_connection,
            },
            "destination": {
                "type": "LakehouseTable",
                "connectionSettings": lakehouse_connection,
            },
            "policy": {"timeout": "0.12:00:00"},
        },
        "activities": [
            {
                "id": str(activity_id),
                "properties": {
                    "source": {
                        "datasetSettings": {
                            "table": "cert_copy_source",
                        }
                    },
                    "destination": {
                        "writeBehavior": "Overwrite",
                        "datasetSettings": {
                            "table": "cert_copy_landing",
                        },
                    },
                    "translator": {"type": "TabularTranslator"},
                    "typeConversionSettings": {
                        "typeConversion": {
                            "allowDataTruncation": False,
                            "treatBooleanAsNumber": False,
                        }
                    },
                },
            }
        ],
    }
    return FabricItemDefinition(
        format=None,
        parts=(_part_json("copyjob-content.json", content),),
    )


def _pipeline_argument_expression(name: str) -> str:
    if name not in _PIPELINE_PARAMETER_NAMES:
        raise ValueError(f"unsupported certification Pipeline parameter {name!r}")
    return f"@{{pipeline().parameters.{name}}}"


def _pipeline_definition(
    *,
    workspace_id: UUID,
    lakehouse_id: UUID,
    environment_id: UUID,
    spark_job_id: UUID,
    runtime_config_b64: str,
) -> FabricItemDefinition:
    parameter_defaults: dict[str, dict[str, object]] = {
        "framework_pipeline_run_id": {"type": "String", "defaultValue": ""},
        "framework_dataset_run_id": {"type": "String", "defaultValue": ""},
        "dataset_id": {"type": "String", "defaultValue": ""},
        "run_mode": {"type": "String", "defaultValue": ""},
        "attempt": {"type": "Int", "defaultValue": 1},
        "effective_config_hash": {"type": "String", "defaultValue": ""},
        "execution_plan_hash": {"type": "String", "defaultValue": ""},
    }
    arguments = [
        "--runtime-config-b64",
        runtime_config_b64,
        "--framework-pipeline-run-id",
        _pipeline_argument_expression("framework_pipeline_run_id"),
        "--framework-dataset-run-id",
        _pipeline_argument_expression("framework_dataset_run_id"),
        "--dataset-id",
        _pipeline_argument_expression("dataset_id"),
        "--run-mode",
        _pipeline_argument_expression("run_mode"),
        "--attempt",
        _pipeline_argument_expression("attempt"),
        "--effective-config-hash",
        _pipeline_argument_expression("effective_config_hash"),
        "--execution-plan-hash",
        _pipeline_argument_expression("execution_plan_hash"),
    ]
    content = {
        "properties": {
            "description": "Framework-owned certification child pipeline.",
            "parameters": parameter_defaults,
            "activities": [
                {
                    "name": "ExecuteFrameworkCertificationChild",
                    "type": "SparkJobDefinition",
                    "typeProperties": {
                        "sparkJobDefinitionId": str(spark_job_id),
                        "workspaceId": str(workspace_id),
                        "executableFile": "main.py",
                        "mainClass": "",
                        "additionalLibraryUris": [],
                        "commandLineArguments": " ".join(arguments),
                        "defaultLakehouse": {
                            "workspaceId": str(workspace_id),
                            "artifactId": str(lakehouse_id),
                        },
                        "additionalLakehouses": [],
                        "environmentId": str(environment_id),
                    },
                }
            ],
        }
    }
    return FabricItemDefinition(
        format=None,
        parts=(_part_json("pipeline-content.json", content),),
    )


def build_certification_fabric_asset_plan(
    *,
    workspace_id: UUID,
    lakehouse_id: UUID,
    candidate_manifest: CandidateArtifactManifest,
    candidate_wheel_path: str | Path,
    environment_id: UUID,
    spark_job_id: UUID,
    control_plane_sql_server: str,
    control_plane_sql_database: str,
    warehouse_sql_server: str,
    warehouse_sql_database: str,
    certification_root: str | Path,
    dependency_wheels: Iterable[str | Path] = (),
) -> CertificationFabricAssetPlan:
    """Build exact definitions for a known set of item identities."""

    wheel = _validate_candidate_wheel(candidate_wheel_path, candidate_manifest)
    runtime_blob = encode_certification_runtime_config(
        control_plane_sql_server=control_plane_sql_server,
        control_plane_sql_database=control_plane_sql_database,
        warehouse_sql_server=warehouse_sql_server,
        warehouse_sql_database=warehouse_sql_database,
        certification_root=certification_root,
    )
    return CertificationFabricAssetPlan(
        workspace_id=workspace_id,
        lakehouse_id=lakehouse_id,
        environment_definition=_environment_definition(
            wheel_path=wheel,
            dependency_wheels=dependency_wheels,
        ),
        spark_job_definition=_spark_job_definition(
            workspace_id=workspace_id,
            lakehouse_id=lakehouse_id,
            environment_id=environment_id,
        ),
        copy_job_definition=_copy_job_definition(
            workspace_id=workspace_id,
            lakehouse_id=lakehouse_id,
        ),
        pipeline_definition=_pipeline_definition(
            workspace_id=workspace_id,
            lakehouse_id=lakehouse_id,
            environment_id=environment_id,
            spark_job_id=spark_job_id,
            runtime_config_b64=runtime_blob,
        ),
        candidate_wheel_filename=wheel.name,
        candidate_wheel_sha256=candidate_manifest.wheel_sha256,
    )


def _header_value(headers: Any, name: str) -> str | None:
    if not hasattr(headers, "get"):
        return None
    value = headers.get(name)
    if value is None:
        value = headers.get(name.lower())
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _retry_after(headers: Any, default: float) -> float:
    value = _header_value(headers, "Retry-After")
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed >= 0 else default


def _parse_item_payload(
    payload: object,
    *,
    expected_workspace_id: UUID,
    expected_display_name: str,
    expected_item_type: str,
) -> FabricItem:
    if not isinstance(payload, dict):
        raise FabricRestError("Fabric create-item result must be a JSON object")
    try:
        item = FabricItem(
            id=UUID(str(payload["id"])),
            workspace_id=UUID(str(payload["workspaceId"])),
            display_name=str(payload["displayName"]).strip(),
            item_type=str(payload["type"]).strip(),
        )
    except (KeyError, ValueError) as exc:
        raise FabricRestError("Fabric create-item result has malformed identity fields") from exc
    if item.workspace_id != expected_workspace_id:
        raise FabricRestError("Fabric create-item result workspace identity mismatch")
    if item.display_name != expected_display_name:
        raise FabricRestError("Fabric create-item result displayName mismatch")
    if item.item_type != expected_item_type:
        raise FabricRestError("Fabric create-item result type mismatch")
    return item


def _decode_definition_part(part: FabricDefinitionPart) -> bytes:
    try:
        return base64.b64decode(part.payload.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError(f"definition part {part.path!r} is not valid base64") from exc


def _canonical_part_bytes(path: str, payload: bytes) -> bytes:
    if path.endswith(".json"):
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FabricRestError(f"Fabric read-back JSON part {path!r} is invalid") from exc
        return json.dumps(
            parsed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    return payload


def _definition_from_response(payload: object) -> FabricItemDefinition:
    if not isinstance(payload, dict) or not isinstance(payload.get("definition"), dict):
        raise FabricRestError("Fabric getDefinition result must contain a definition object")
    raw = payload["definition"]
    parts = raw.get("parts")
    if not isinstance(parts, list) or not parts:
        raise FabricRestError("Fabric getDefinition result must contain a non-empty parts array")
    observed: list[FabricDefinitionPart] = []
    for value in parts:
        if not isinstance(value, dict):
            raise FabricRestError("Fabric getDefinition part must be a JSON object")
        try:
            path = str(value["path"]).strip()
            encoded = str(value["payload"]).strip()
            payload_type = str(value["payloadType"]).strip()
        except KeyError as exc:
            raise FabricRestError("Fabric getDefinition part is missing required fields") from exc
        if not path or not encoded:
            raise FabricRestError("Fabric getDefinition part path/payload cannot be empty")
        if payload_type != _INLINE_BASE64:
            raise FabricRestError(
                f"Fabric getDefinition returned unsupported payloadType {payload_type!r}"
            )
        observed.append(
            FabricDefinitionPart(path=path, payload=encoded, payload_type=payload_type)
        )
    raw_format = raw.get("format")
    return FabricItemDefinition(
        format=None if raw_format in (None, "") else str(raw_format),
        parts=tuple(observed),
    )


def assert_definition_read_back_matches(
    expected: FabricItemDefinition,
    observed_payload: object,
) -> None:
    """Require every framework-owned definition part to read back unchanged."""

    observed = _definition_from_response(observed_payload)
    if expected.format is not None and observed.format not in {None, expected.format}:
        raise FabricRestError(
            "Fabric read-back definition format mismatch: "
            f"observed={observed.format!r}, expected={expected.format!r}"
        )
    expected_by_path = {part.path: part for part in expected.parts}
    observed_by_path: dict[str, FabricDefinitionPart] = {}
    for part in observed.parts:
        if part.path == ".platform":
            continue
        if part.path in observed_by_path:
            raise FabricRestError(f"Fabric read-back duplicated part {part.path!r}")
        observed_by_path[part.path] = part
    if set(observed_by_path) != set(expected_by_path):
        raise FabricRestError(
            "Fabric read-back definition part set mismatch: "
            f"missing={sorted(set(expected_by_path) - set(observed_by_path))}; "
            f"unexpected={sorted(set(observed_by_path) - set(expected_by_path))}"
        )
    for path in sorted(expected_by_path):
        expected_bytes = _canonical_part_bytes(
            path,
            _decode_definition_part(expected_by_path[path]),
        )
        observed_bytes = _canonical_part_bytes(
            path,
            _decode_definition_part(observed_by_path[path]),
        )
        if observed_bytes != expected_bytes:
            raise FabricRestError(f"Fabric read-back definition part {path!r} differs")


class FabricCertificationAssetClient(FabricItemCatalogClient):
    """Mutating certification bootstrap client with strict read-back verification."""

    def __init__(
        self,
        *args,
        lro_timeout_seconds: float = 1800.0,
        default_poll_seconds: float = 5.0,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if lro_timeout_seconds <= 0:
            raise ValueError("lro_timeout_seconds must be positive")
        if default_poll_seconds < 0:
            raise ValueError("default_poll_seconds must be >= 0")
        self._lro_timeout_seconds = lro_timeout_seconds
        self._default_poll_seconds = default_poll_seconds

    def _operation_id(self, headers: Any) -> UUID:
        value = _header_value(headers, "x-ms-operation-id")
        if value is None:
            location = _header_value(headers, "Location")
            if location is None:
                raise FabricRestError("Fabric LRO response omitted operation identity")
            parsed = urlparse(location)
            parts = [part for part in parsed.path.split("/") if part]
            try:
                value = parts[parts.index("operations") + 1]
            except (ValueError, IndexError) as exc:
                raise FabricRestError("Fabric LRO Location is not an operation URL") from exc
        try:
            return UUID(value)
        except ValueError as exc:
            raise FabricRestError("Fabric LRO operation id is not a UUID") from exc

    def _wait_operation(self, headers: Any, *, want_result: bool) -> object | None:
        operation_id = self._operation_id(headers)
        deadline = self._clock() + self._lro_timeout_seconds
        delay = _retry_after(headers, self._default_poll_seconds)
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise FabricRestError(
                    f"Fabric operation {operation_id} did not complete before timeout"
                )
            if delay > 0:
                self._sleeper(min(delay, remaining))
            payload, state_headers = self._request(
                "GET",
                f"operations/{operation_id}",
                expected_statuses=frozenset({200}),
            )
            if not isinstance(payload, dict):
                raise FabricRestError("Fabric LRO state response must be a JSON object")
            status = str(payload.get("status", "")).strip()
            if status in _SUPPORTED_LRO_RUNNING:
                delay = _retry_after(state_headers, self._default_poll_seconds)
                continue
            if status not in _SUPPORTED_LRO_TERMINAL:
                raise FabricRestError(f"Fabric LRO returned unsupported status {status!r}")
            if status == "Failed":
                raise FabricRestError(
                    f"Fabric operation {operation_id} failed",
                    payload=payload,
                )
            if not want_result:
                return None
            result, _ = self._request(
                "GET",
                f"operations/{operation_id}/result",
                expected_statuses=frozenset({200}),
            )
            return result

    def _create_item(
        self,
        *,
        workspace_id: UUID,
        display_name: str,
        item_type: str,
        definition: FabricItemDefinition,
    ) -> FabricItem:
        payload, headers = self._request(
            "POST",
            f"workspaces/{workspace_id}/items",
            payload={
                "displayName": display_name,
                "type": item_type,
                "definition": definition.as_dict(),
            },
            expected_statuses=frozenset({201, 202}),
        )
        if payload is None:
            payload = self._wait_operation(headers, want_result=True)
        return _parse_item_payload(
            payload,
            expected_workspace_id=workspace_id,
            expected_display_name=display_name,
            expected_item_type=item_type,
        )

    def _update_definition(
        self,
        *,
        workspace_id: UUID,
        item_id: UUID,
        definition: FabricItemDefinition,
    ) -> None:
        payload, headers = self._request(
            "POST",
            f"workspaces/{workspace_id}/items/{item_id}/updateDefinition?updateMetadata=false",
            payload={"definition": definition.as_dict()},
            expected_statuses=frozenset({200, 202}),
        )
        if payload is None and _header_value(headers, "x-ms-operation-id") is not None:
            self._wait_operation(headers, want_result=False)

    def _get_definition(
        self,
        *,
        workspace_id: UUID,
        item_id: UUID,
    ) -> object:
        payload, headers = self._request(
            "POST",
            f"workspaces/{workspace_id}/items/{item_id}/getDefinition",
            expected_statuses=frozenset({200, 202}),
        )
        if payload is None:
            payload = self._wait_operation(headers, want_result=True)
        if payload is None:
            raise FabricRestError("Fabric getDefinition completed without a result")
        return payload

    def _publish_environment(self, *, workspace_id: UUID, environment_id: UUID) -> None:
        payload, headers = self._request(
            "POST",
            f"workspaces/{workspace_id}/environments/{environment_id}/staging/publish?beta=false",
            expected_statuses=frozenset({200, 202}),
        )
        if payload is None and _header_value(headers, "x-ms-operation-id") is not None:
            self._wait_operation(headers, want_result=False)

    def _find_exact(
        self,
        *,
        workspace_id: UUID,
        display_name: str,
        item_type: str,
    ) -> FabricItem | None:
        matches = tuple(
            item
            for item in self.list_items(workspace_id=workspace_id, item_type=item_type)
            if item.display_name == display_name
        )
        if len(matches) > 1:
            raise FabricRestError(
                f"multiple Fabric {item_type} items use certification name {display_name!r}"
            )
        return matches[0] if matches else None

    def reconcile_item(
        self,
        *,
        workspace_id: UUID,
        display_name: str,
        item_type: str,
        definition: FabricItemDefinition,
        allow_item_mutation: bool,
    ) -> tuple[FabricItem, str]:
        existing = self._find_exact(
            workspace_id=workspace_id,
            display_name=display_name,
            item_type=item_type,
        )
        if not allow_item_mutation:
            if existing is None:
                raise PermissionError(
                    "Fabric certification item mutation is not authorized: "
                    f"missing {display_name}"
                )
            observed = self._get_definition(
                workspace_id=workspace_id,
                item_id=existing.id,
            )
            assert_definition_read_back_matches(definition, observed)
            return existing, "VERIFIED_EXISTING"

        if existing is None:
            item = self._create_item(
                workspace_id=workspace_id,
                display_name=display_name,
                item_type=item_type,
                definition=definition,
            )
            action = "CREATED"
        else:
            item = existing
            self._update_definition(
                workspace_id=workspace_id,
                item_id=item.id,
                definition=definition,
            )
            action = "UPDATED"
        observed = self._get_definition(
            workspace_id=workspace_id,
            item_id=item.id,
        )
        assert_definition_read_back_matches(definition, observed)
        return item, action

    def bootstrap(
        self,
        *,
        workspace_id: UUID,
        lakehouse_id: UUID,
        candidate_manifest: CandidateArtifactManifest,
        candidate_wheel_path: str | Path,
        control_plane_sql_server: str,
        control_plane_sql_database: str,
        warehouse_sql_server: str,
        warehouse_sql_database: str,
        certification_root: str | Path,
        allow_item_mutation: bool,
        dependency_wheels: Iterable[str | Path] = (),
    ) -> CertificationFabricBootstrapReport:
        """Create/update and read back all framework-owned certification Fabric items."""

        wheel = _validate_candidate_wheel(candidate_wheel_path, candidate_manifest)
        environment_definition = _environment_definition(
            wheel_path=wheel,
            dependency_wheels=dependency_wheels,
        )
        environment, env_action = self.reconcile_item(
            workspace_id=workspace_id,
            display_name=ENVIRONMENT_DISPLAY_NAME,
            item_type=ENVIRONMENT_ITEM_TYPE,
            definition=environment_definition,
            allow_item_mutation=allow_item_mutation,
        )
        if allow_item_mutation:
            self._publish_environment(
                workspace_id=workspace_id,
                environment_id=environment.id,
            )

        spark_definition = _spark_job_definition(
            workspace_id=workspace_id,
            lakehouse_id=lakehouse_id,
            environment_id=environment.id,
        )
        spark_job, spark_action = self.reconcile_item(
            workspace_id=workspace_id,
            display_name=SPARK_JOB_DISPLAY_NAME,
            item_type=SPARK_JOB_ITEM_TYPE,
            definition=spark_definition,
            allow_item_mutation=allow_item_mutation,
        )

        copy_definition = _copy_job_definition(
            workspace_id=workspace_id,
            lakehouse_id=lakehouse_id,
        )
        copy_job, copy_action = self.reconcile_item(
            workspace_id=workspace_id,
            display_name=COPY_JOB_DISPLAY_NAME,
            item_type=COPY_JOB_ITEM_TYPE,
            definition=copy_definition,
            allow_item_mutation=allow_item_mutation,
        )

        runtime_blob = encode_certification_runtime_config(
            control_plane_sql_server=control_plane_sql_server,
            control_plane_sql_database=control_plane_sql_database,
            warehouse_sql_server=warehouse_sql_server,
            warehouse_sql_database=warehouse_sql_database,
            certification_root=certification_root,
        )
        pipeline_definition = _pipeline_definition(
            workspace_id=workspace_id,
            lakehouse_id=lakehouse_id,
            environment_id=environment.id,
            spark_job_id=spark_job.id,
            runtime_config_b64=runtime_blob,
        )
        pipeline, pipeline_action = self.reconcile_item(
            workspace_id=workspace_id,
            display_name=PIPELINE_DISPLAY_NAME,
            item_type=PIPELINE_ITEM_TYPE,
            definition=pipeline_definition,
            allow_item_mutation=allow_item_mutation,
        )

        identities = (
            CertificationFabricAssetIdentity(
                display_name=ENVIRONMENT_DISPLAY_NAME,
                item_type=ENVIRONMENT_ITEM_TYPE,
                item_id=environment.id,
                definition_sha256=environment_definition.semantic_sha256,
                action=env_action,
            ),
            CertificationFabricAssetIdentity(
                display_name=SPARK_JOB_DISPLAY_NAME,
                item_type=SPARK_JOB_ITEM_TYPE,
                item_id=spark_job.id,
                definition_sha256=spark_definition.semantic_sha256,
                action=spark_action,
            ),
            CertificationFabricAssetIdentity(
                display_name=COPY_JOB_DISPLAY_NAME,
                item_type=COPY_JOB_ITEM_TYPE,
                item_id=copy_job.id,
                definition_sha256=copy_definition.semantic_sha256,
                action=copy_action,
            ),
            CertificationFabricAssetIdentity(
                display_name=PIPELINE_DISPLAY_NAME,
                item_type=PIPELINE_ITEM_TYPE,
                item_id=pipeline.id,
                definition_sha256=pipeline_definition.semantic_sha256,
                action=pipeline_action,
            ),
        )
        return CertificationFabricBootstrapReport(
            workspace_id=workspace_id,
            lakehouse_id=lakehouse_id,
            candidate_wheel_filename=wheel.name,
            candidate_wheel_sha256=candidate_manifest.wheel_sha256,
            assets=identities,
            definition_read_back_status=DEFINITION_READ_BACK_STATUS,
            pipeline_parameter_contract_status=PIPELINE_PARAMETER_CONTRACT_STATUS,
        )


__all__ = [
    "COPY_JOB_DISPLAY_NAME",
    "DEFINITION_READ_BACK_STATUS",
    "ENVIRONMENT_DISPLAY_NAME",
    "PIPELINE_DISPLAY_NAME",
    "PIPELINE_PARAMETER_CONTRACT_STATUS",
    "SPARK_JOB_DISPLAY_NAME",
    "CertificationFabricAssetPlan",
    "CertificationFabricBootstrapReport",
    "FabricCertificationAssetClient",
    "FabricDefinitionPart",
    "FabricItemDefinition",
    "assert_definition_read_back_matches",
    "build_certification_fabric_asset_plan",
]
