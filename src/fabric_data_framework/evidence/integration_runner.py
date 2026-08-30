"""Credential-free configuration and preflight for approved provider evidence runs.

The source-controlled runner configuration contains only immutable release identity,
physical item IDs and *names* of runtime environment variables. Secret values remain
process-local. Preflight never serializes environment-variable values.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from pydantic import Field, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from ..control_plane.certification import CONTROL_PLANE_BACKEND_PROFILES
from ..infrastructure import EnvironmentName
from .integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckSpec,
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

_WAREHOUSE_RUNTIME_KINDS = frozenset(
    {
        IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
        IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL,
    }
)

_MUTATING_KINDS = frozenset(
    {
        IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
        IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE,
        *_WAREHOUSE_RUNTIME_KINDS,
        IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
        IntegrationEvidenceCheckKind.KAFKA_PROVIDER,
        IntegrationEvidenceCheckKind.DELTA_CDF_PROVIDER,
    }
)

_CONTROL_PLANE_RUNTIME_KINDS = frozenset(
    {
        IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
        IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        *_WAREHOUSE_RUNTIME_KINDS,
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
    """Source-controlled configuration for one exact approved-environment run.

    ``warehouse_admin_database_url_env_var`` is deliberately separate from the ordinary
    Warehouse target connection. It names the runtime credential used only for explicit
    Admin/session-control evidence such as ``KILL``. Supplying the same environment
    variable name for both paths is rejected so routine Warehouse mutation credentials
    cannot silently inherit session-termination authority.
    """

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
    warehouse_admin_database_url_env_var: str | None = Field(
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
        if (
            self.warehouse_admin_database_url_env_var is not None
            and self.warehouse_database_url_env_var is None
        ):
            raise ValueError(
                "warehouse_admin_database_url_env_var requires warehouse_database_url_env_var"
            )
        if (
            self.warehouse_admin_database_url_env_var is not None
            and self.warehouse_admin_database_url_env_var
            == self.warehouse_database_url_env_var
        ):
            raise ValueError(
                "Warehouse Admin and ordinary Warehouse database URL env vars must differ"
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


def _selected_checks(
    spec: IntegrationEvidenceSpec,
    selected_check_ids: Iterable[str] | None,
) -> tuple[IntegrationEvidenceCheckSpec, ...]:
    if selected_check_ids is None:
        return tuple(item for item in spec.checks if item.required)
    requested = tuple(selected_check_ids)
    if not requested:
        raise ValueError("selected_check_ids cannot be empty")
    if len(set(requested)) != len(requested):
        raise ValueError("selected_check_ids must be unique")
    by_id = {item.check_id: item for item in spec.checks}
    unknown = [check_id for check_id in requested if check_id not in by_id]
    if unknown:
        raise ValueError(
            "selected integration checks are not declared in evidence spec: "
            + ", ".join(unknown)
        )
    return tuple(by_id[check_id] for check_id in requested)


def _validate_bindings(
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
    checks: tuple[IntegrationEvidenceCheckSpec, ...],
) -> dict[str, IntegrationCheckPhysicalBinding]:
    specs = {item.check_id: item for item in spec.checks}
    bindings = {item.check_id: item for item in config.bindings}
    unexpected = sorted(set(bindings) - set(specs))
    if unexpected:
        raise ValueError(
            "integration runner bindings are not declared in evidence spec: "
            + ", ".join(unexpected)
        )
    for check in checks:
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
    checks: tuple[IntegrationEvidenceCheckSpec, ...],
    *,
    environ: Mapping[str, str],
) -> tuple[RuntimeEnvironmentRequirement, ...]:
    kinds = {item.kind for item in checks}
    requirements: list[tuple[str, str]] = []
    if kinds.intersection(_FABRIC_ITEM_KINDS):
        requirements.append(("Fabric REST access token", config.fabric_access_token_env_var))
    if kinds.intersection(_CONTROL_PLANE_RUNTIME_KINDS):
        if config.control_plane_database_url_env_var is None:
            raise ValueError(
                "CONTROL_PLANE_CERTIFICATION/FABRIC_PIPELINE_RUN/Warehouse evidence check "
                "needs control-plane runtime configuration"
            )
        if IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION in kinds:
            purpose = "control-plane database URL"
        elif IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN in kinds:
            purpose = "Pipeline durable-outcome control-plane database URL"
        else:
            purpose = "Warehouse target-operation journal control-plane database URL"
        requirements.append((purpose, config.control_plane_database_url_env_var))
    if kinds.intersection(_WAREHOUSE_RUNTIME_KINDS):
        if config.warehouse_database_url_env_var is None:
            raise ValueError("Warehouse evidence check needs warehouse_database_url_env_var")
        requirements.append(
            ("Warehouse SQL database URL", config.warehouse_database_url_env_var)
        )

    # Admin/session-control credentials are intentionally not included automatically.
    # Whether they are required is an exact run-recipe decision, and the approved
    # Warehouse fault runner adds that requirement only when session termination
    # recovery is explicitly enabled and separately authorized.
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
    selected_check_ids: Iterable[str] | None = None,
    allow_mutating_checks: bool = False,
) -> ApprovedIntegrationRunPlan:
    """Validate exact-release bindings and runtime prerequisites without reading secrets.

    By default all *required* evidence checks are planned. ``selected_check_ids`` can
    stage a safer subset, for example the read-only Fabric item smoke before database
    credentials or mutating provider checks are authorized.

    The environment mapping is inspected only for presence/non-empty values. Secret
    values are never copied into the returned plan.
    """

    _require_same_release(config, spec)
    checks = _selected_checks(spec, selected_check_ids)
    bindings = _validate_bindings(config, spec, checks)
    runtime_requirements = _runtime_requirements(config, checks, environ=environ)
    missing = tuple(item.env_var for item in runtime_requirements if not item.present)
    mutating = tuple(item.check_id for item in checks if item.kind in _MUTATING_KINDS)
    selected_bindings = tuple(
        bindings[item.check_id] for item in checks if item.check_id in bindings
    )
    return ApprovedIntegrationRunPlan(
        environment=config.environment,
        domain=config.domain,
        framework_version=config.framework_version,
        release_hash=config.release_hash,
        check_ids=tuple(item.check_id for item in checks),
        bindings=selected_bindings,
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
