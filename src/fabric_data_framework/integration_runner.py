"""Credential-free configuration and preflight for approved provider evidence runs.

The source-controlled runner configuration contains only immutable release identity,
physical item IDs and *names* of runtime environment variables. Secret values remain
process-local. Preflight never serializes environment-variable values.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from pydantic import Field, model_validator

from .config import FrozenModel
from .control_plane_certification import CONTROL_PLANE_BACKEND_PROFILES
from .infrastructure import EnvironmentName
from .integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceSpec,
)


_ENV_NAME_PATTERN = r"^[A-Z][A-Z0-9_]{0,127}$"

_FABRIC_ITEM_KINDS = frozenset(
    {
        IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
        IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE,
    }
)

_MUTATING_KINDS = frozenset(
    {
        IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE,
        IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
        IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
        IntegrationEvidenceCheckKind.KAFKA_PROVIDER,
        IntegrationEvidenceCheckKind.DELTA_CDF_PROVIDER,
    }
)


class IntegrationCheckPhysicalBinding(FrozenModel):
    """Environment-local physical IDs for one evidence check.

    No connection string, access token or secret-bearing endpoint belongs here.
    """

    check_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    workspace_id: UUID | None = None
    item_id: UUID | None = None


class ApprovedIntegrationRunnerConfig(FrozenModel):
    """Source-controlled configuration for one exact approved-environment run."""

    environment: EnvironmentName
    domain: str = Field(min_length=1, max_length=128)
    framework_version: str = Field(min_length=1, max_length=64)
    release_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    fabric_access_token_env_var: str = Field(
        default="FABRIC_ACCESS_TOKEN", pattern=_ENV_NAME_PATTERN
    )
    control_plane_database_url_env_var: str | None = Field(
        default=None, pattern=_ENV_NAME_PATTERN
    )
    warehouse_database_url_env_var: str | None = Field(
        default=None, pattern=_ENV_NAME_PATTERN
    )
    control_plane_profile: str | None = None
    bindings: tuple[IntegrationCheckPhysicalBinding, ...] = ()

    supported_control_plane_profiles: ClassVar[frozenset[str]] = frozenset(
        CONTROL_PLANE_BACKEND_PROFILES
    )

    @model_validator(mode="after")
    def validate_config(self) -> "ApprovedIntegrationRunnerConfig":
        ids = [item.check_id for item in self.bindings]
        if len(set(ids)) != len(ids):
            raise ValueError("integration runner physical binding check_id values must be unique")
        if (
            self.control_plane_profile is not None
            and self.control_plane_profile not in self.supported_control_plane_profiles
        ):
            raise ValueError(
                f"unknown control-plane profile {self.control_plane_profile!r}"
            )
        if (
            self.control_plane_profile is None
            and self.control_plane_database_url_env_var is not None
        ):
            raise ValueError(
                "control_plane_database_url_env_var requires control_plane_profile"
            )
        if (
            self.control_plane_profile is not None
            and self.control_plane_database_url_env_var is None
        ):
            raise ValueError(
                "control_plane_profile requires control_plane_database_url_env_var"
            )
        return self


class RuntimeEnvironmentRequirement(FrozenModel):
    purpose: str = Field(min_length=1, max_length=256)
    env_var: str = Field(pattern=_ENV_NAME_PATTERN)
    present: bool


class ApprovedIntegrationRunPlan(FrozenModel):
    """Credential-free preflight result safe to retain as CI/deployment evidence."""

    environment: EnvironmentName
    domain: str
    framework_version: str
    release_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    check_ids: tuple[str, ...]
    bindings: tuple[IntegrationCheckPhysicalBinding, ...]
    runtime_requirements: tuple[RuntimeEnvironmentRequirement, ...]
    missing_runtime_env_vars: tuple[str, ...]
    mutating_check_ids: tuple[str, ...]
    mutating_checks_authorized: bool

    @property
    def ready(self) -> bool:
        return not self.missing_runtime_env_vars and (
            not self.mutating_check_ids or self.mutating_checks_authorized
        )


def _require_same_release(
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
) -> None:
    if config.environment is not spec.environment:
        raise ValueError("integration runner config and evidence spec environment differ")
    if config.domain != spec.domain:
        raise ValueError("integration runner config and evidence spec domain differ")
    if config.framework_version != spec.framework_version:
        raise ValueError("integration runner config and evidence spec framework version differ")
    if config.release_hash != spec.release_hash:
        raise ValueError("integration runner config and evidence spec release hash differ")


def _validate_bindings(
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
) -> dict[str, IntegrationCheckPhysicalBinding]:
    specs = {item.check_id: item for item in spec.checks}
    bindings = {item.check_id: item for item in config.bindings}
    unexpected = sorted(set(bindings) - set(specs))
    if unexpected:
        raise ValueError(
            "integration runner bindings are not declared in evidence spec: "
            + ", ".join(unexpected)
        )
    for check in spec.checks:
        if check.kind in _FABRIC_ITEM_KINDS:
            binding = bindings.get(check.check_id)
            if binding is None:
                raise ValueError(
                    f"{check.kind.value} check {check.check_id!r} requires a physical binding"
                )
            if binding.workspace_id is None or binding.item_id is None:
                raise ValueError(
                    f"{check.kind.value} check {check.check_id!r} requires workspace_id and item_id"
                )
    return bindings


def _runtime_requirements(
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
    *,
    environ: Mapping[str, str],
) -> tuple[RuntimeEnvironmentRequirement, ...]:
    kinds = {item.kind for item in spec.checks if item.required}
    requirements: list[tuple[str, str]] = []
    if kinds.intersection(_FABRIC_ITEM_KINDS):
        requirements.append(("Fabric REST access token", config.fabric_access_token_env_var))
    if IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION in kinds:
        if config.control_plane_database_url_env_var is None:
            raise ValueError(
                "required CONTROL_PLANE_CERTIFICATION check needs control-plane runtime configuration"
            )
        requirements.append(
            ("control-plane database URL", config.control_plane_database_url_env_var)
        )
    if IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT in kinds:
        if config.warehouse_database_url_env_var is None:
            raise ValueError(
                "required FABRIC_WAREHOUSE_TARGET_COMMIT check needs warehouse_database_url_env_var"
            )
        requirements.append(
            ("Warehouse SQL database URL", config.warehouse_database_url_env_var)
        )

    seen: set[str] = set()
    result: list[RuntimeEnvironmentRequirement] = []
    for purpose, env_var in requirements:
        if env_var in seen:
            continue
        seen.add(env_var)
        value = environ.get(env_var)
        result.append(
            RuntimeEnvironmentRequirement(
                purpose=purpose,
                env_var=env_var,
                present=bool(value and value.strip()),
            )
        )
    return tuple(result)


def build_approved_integration_run_plan(
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
    *,
    environ: Mapping[str, str],
    allow_mutating_checks: bool = False,
) -> ApprovedIntegrationRunPlan:
    """Validate exact-release bindings and runtime prerequisites without reading secrets.

    The environment mapping is inspected only for presence/non-empty values. Secret
    values are never copied into the returned plan.
    """

    _require_same_release(config, spec)
    _validate_bindings(config, spec)
    runtime_requirements = _runtime_requirements(config, spec, environ=environ)
    missing = tuple(
        item.env_var for item in runtime_requirements if not item.present
    )
    mutating = tuple(
        item.check_id for item in spec.checks if item.required and item.kind in _MUTATING_KINDS
    )
    return ApprovedIntegrationRunPlan(
        environment=config.environment,
        domain=config.domain,
        framework_version=config.framework_version,
        release_hash=config.release_hash,
        check_ids=tuple(item.check_id for item in spec.checks),
        bindings=config.bindings,
        runtime_requirements=runtime_requirements,
        missing_runtime_env_vars=missing,
        mutating_check_ids=mutating,
        mutating_checks_authorized=allow_mutating_checks,
    )


def load_approved_integration_runner_config(
    path: str | Path,
) -> ApprovedIntegrationRunnerConfig:
    return ApprovedIntegrationRunnerConfig.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


__all__ = [
    "ApprovedIntegrationRunPlan",
    "ApprovedIntegrationRunnerConfig",
    "IntegrationCheckPhysicalBinding",
    "RuntimeEnvironmentRequirement",
    "build_approved_integration_run_plan",
    "load_approved_integration_runner_config",
]
