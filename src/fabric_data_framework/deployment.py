"""Provider-neutral release identity, promotion and deployment provenance contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .control_plane import ENVIRONMENT_LOCAL_STATE_TABLES, PROMOTABLE_DEFINITION_TABLES
from .infrastructure import EnvironmentName


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class DeploymentMechanism(str, Enum):
    FABRIC_DEPLOYMENT_PIPELINE = "FABRIC_DEPLOYMENT_PIPELINE"
    FABRIC_GIT_API = "FABRIC_GIT_API"
    FABRIC_ITEMS_API = "FABRIC_ITEMS_API"
    FABRIC_CICD = "FABRIC_CICD"
    FABRIC_CLI = "FABRIC_CLI"


class CIProvider(str, Enum):
    GITHUB_ACTIONS = "GITHUB_ACTIONS"
    AZURE_PIPELINES = "AZURE_PIPELINES"
    FABRIC_NATIVE = "FABRIC_NATIVE"
    MANUAL = "MANUAL"


class ControlPlaneRecordClass(str, Enum):
    RELEASE_DEFINITION = "RELEASE_DEFINITION"
    ENVIRONMENT_LOCAL_STATE = "ENVIRONMENT_LOCAL_STATE"


class ReleaseBundleIdentity(FrozenModel):
    domain_release_version: str = Field(min_length=1)
    domain_git_sha: str = Field(pattern=r"^[0-9a-fA-F]{7,64}$")
    framework_version: str = Field(min_length=1)
    config_bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_schema_version: int = Field(ge=1)
    control_plane_schema_version: int = Field(ge=1)
    fabric_item_manifest_version: str = Field(min_length=1)
    build_id: str = Field(min_length=1)

    @property
    def release_hash(self) -> str:
        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class DeploymentRequest(FrozenModel):
    target_environment: EnvironmentName
    bundle: ReleaseBundleIdentity
    logical_binding_profile: str = Field(min_length=1)


class DeploymentProvenance(FrozenModel):
    deployment_id: UUID = Field(default_factory=uuid4)
    environment: EnvironmentName
    domain: str = Field(min_length=1)
    bundle: ReleaseBundleIdentity
    deployment_mechanism: DeploymentMechanism
    ci_provider: CIProvider
    initiated_by: str = Field(min_length=1)
    approved_by: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    status: str = Field(min_length=1)
    previous_deployment_id: UUID | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "DeploymentProvenance":
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware")
        if self.completed_at is not None:
            if self.completed_at.tzinfo is None or self.completed_at.utcoffset() is None:
                raise ValueError("completed_at must be timezone-aware")
            if self.completed_at < self.started_at:
                raise ValueError("completed_at cannot be before started_at")
        return self


def classify_control_plane_record(table_name: str) -> ControlPlaneRecordClass:
    if table_name in PROMOTABLE_DEFINITION_TABLES:
        return ControlPlaneRecordClass.RELEASE_DEFINITION
    if table_name in ENVIRONMENT_LOCAL_STATE_TABLES:
        return ControlPlaneRecordClass.ENVIRONMENT_LOCAL_STATE
    raise ValueError(f"unknown control-plane table: {table_name}")


@runtime_checkable
class ControlPlaneDeploymentAdapter(Protocol):
    """CD adapter contract; implementation can be Fabric-native or external."""

    def migrate_schema(self, request: DeploymentRequest) -> None: ...

    def materialize_semantic_metadata(self, request: DeploymentRequest) -> None: ...

    def record_deployment(self, provenance: DeploymentProvenance) -> None: ...
