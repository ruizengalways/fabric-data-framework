"""Provider-neutral release identity, promotion and deployment provenance contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..control_plane.schema import ENVIRONMENT_LOCAL_STATE_TABLES, PROMOTABLE_DEFINITION_TABLES
from ..infrastructure import EnvironmentName, ResolvedResource


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class DeploymentMechanism(str, Enum):
    FABRIC_DEPLOYMENT_PIPELINE = "FABRIC_DEPLOYMENT_PIPELINE"
    FABRIC_GIT_API = "FABRIC_GIT_API"
    FABRIC_ITEMS_API = "FABRIC_ITEMS_API"
    FABRIC_CICD = "FABRIC_CICD"
    FABRIC_CLI = "FABRIC_CLI"
    DRY_RUN = "DRY_RUN"


class CIProvider(str, Enum):
    GITHUB_ACTIONS = "GITHUB_ACTIONS"
    AZURE_PIPELINES = "AZURE_PIPELINES"
    FABRIC_NATIVE = "FABRIC_NATIVE"
    MANUAL = "MANUAL"


class ControlPlaneRecordClass(str, Enum):
    RELEASE_DEFINITION = "RELEASE_DEFINITION"
    ENVIRONMENT_LOCAL_STATE = "ENVIRONMENT_LOCAL_STATE"


class DeploymentStep(str, Enum):
    VALIDATE_RELEASE = "VALIDATE_RELEASE"
    RESOLVE_BINDINGS = "RESOLVE_BINDINGS"
    MIGRATE_CONTROL_PLANE = "MIGRATE_CONTROL_PLANE"
    DEPLOY_FABRIC_ITEMS = "DEPLOY_FABRIC_ITEMS"
    MATERIALIZE_SEMANTIC_METADATA = "MATERIALIZE_SEMANTIC_METADATA"
    RUN_SMOKE_CHECKS = "RUN_SMOKE_CHECKS"
    RECORD_DEPLOYMENT = "RECORD_DEPLOYMENT"


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


class ReleaseManifest(FrozenModel):
    """Immutable domain release description shared by all environment promotions."""

    domain: str = Field(min_length=1)
    bundle: ReleaseBundleIdentity
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    artifact_sha256: dict[str, str] = Field(default_factory=dict)
    promotable_control_plane_tables: tuple[str, ...] = Field(
        default_factory=lambda: tuple(sorted(PROMOTABLE_DEFINITION_TABLES))
    )
    environment_local_state_tables: tuple[str, ...] = Field(
        default_factory=lambda: tuple(sorted(ENVIRONMENT_LOCAL_STATE_TABLES))
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> "ReleaseManifest":
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        for name, digest in self.artifact_sha256.items():
            if not name:
                raise ValueError("artifact names must be non-empty")
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
                raise ValueError(f"artifact digest for {name} must be SHA-256")
        if set(self.promotable_control_plane_tables) != set(PROMOTABLE_DEFINITION_TABLES):
            raise ValueError("manifest promotable table classification does not match framework")
        if set(self.environment_local_state_tables) != set(ENVIRONMENT_LOCAL_STATE_TABLES):
            raise ValueError("manifest environment-local table classification does not match framework")
        return self


class DeploymentRequest(FrozenModel):
    target_environment: EnvironmentName
    bundle: ReleaseBundleIdentity
    logical_binding_profile: str = Field(min_length=1)


class EnvironmentBindings(FrozenModel):
    """Environment-local resolved resources. Never part of the immutable release identity."""

    profile_name: str = Field(min_length=1)
    environment: EnvironmentName
    domain: str = Field(min_length=1)
    resources: tuple[ResolvedResource, ...] = ()

    @model_validator(mode="after")
    def validate_resources(self) -> "EnvironmentBindings":
        seen: set[tuple[str, str]] = set()
        for resource in self.resources:
            if resource.environment is not self.environment:
                raise ValueError("resolved resource environment does not match binding environment")
            if resource.domain != self.domain:
                raise ValueError("resolved resource domain does not match binding domain")
            key = (resource.ref.kind.value, resource.ref.logical_name)
            if key in seen:
                raise ValueError(f"duplicate logical resource binding: {key}")
            seen.add(key)
        return self


class DeploymentPlan(FrozenModel):
    """Credential-free deployment plan suitable for CI validation and approval gates."""

    request: DeploymentRequest
    domain: str
    release_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    bindings: EnvironmentBindings
    steps: tuple[DeploymentStep, ...]
    protected_environment_local_state_tables: tuple[str, ...]

    @model_validator(mode="after")
    def validate_plan(self) -> "DeploymentPlan":
        if self.bindings.environment is not self.request.target_environment:
            raise ValueError("deployment request and binding environment differ")
        if self.bindings.profile_name != self.request.logical_binding_profile:
            raise ValueError("deployment request and binding profile differ")
        if self.bindings.domain != self.domain:
            raise ValueError("deployment plan domain and binding domain differ")
        if set(self.protected_environment_local_state_tables) != set(
            ENVIRONMENT_LOCAL_STATE_TABLES
        ):
            raise ValueError("deployment plan must protect all environment-local state tables")
        return self


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


def build_deployment_plan(
    manifest: ReleaseManifest,
    bindings: EnvironmentBindings,
) -> DeploymentPlan:
    """Build the same ordered deployment contract for DEV/UAT/PROD without credentials."""

    if bindings.domain != manifest.domain:
        raise ValueError("release manifest and environment bindings target different domains")
    request = DeploymentRequest(
        target_environment=bindings.environment,
        bundle=manifest.bundle,
        logical_binding_profile=bindings.profile_name,
    )
    return DeploymentPlan(
        request=request,
        domain=manifest.domain,
        release_hash=manifest.bundle.release_hash,
        bindings=bindings,
        steps=(
            DeploymentStep.VALIDATE_RELEASE,
            DeploymentStep.RESOLVE_BINDINGS,
            DeploymentStep.MIGRATE_CONTROL_PLANE,
            DeploymentStep.DEPLOY_FABRIC_ITEMS,
            DeploymentStep.MATERIALIZE_SEMANTIC_METADATA,
            DeploymentStep.RUN_SMOKE_CHECKS,
            DeploymentStep.RECORD_DEPLOYMENT,
        ),
        protected_environment_local_state_tables=tuple(sorted(ENVIRONMENT_LOCAL_STATE_TABLES)),
    )


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
