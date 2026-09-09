"""Source-controlled plan for the five representative live 0.4 business-path gates."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from pydantic import Field, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.deployment.contracts import ReleaseManifest
from fabric_data_framework.evidence.business_path_evidence import BusinessPathGate
from fabric_data_framework.evidence.safety import assert_safe_retained_text
from fabric_data_framework.metadata.config import canonical_hash


BUSINESS_PATH_PLAN_SCHEMA_VERSION = 1
_REQUIRED_GATES = frozenset(BusinessPathGate)


def _validate_relative_project_path(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValueError(f"{label} must be project-relative")
    if not value or value in {".", "./"}:
        raise ValueError(f"{label} must name a file")
    if "\\" in value or value != path.as_posix():
        raise ValueError(f"{label} must use canonical project-relative POSIX syntax")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} contains unsafe path traversal")
    return value


class BusinessPathCertificationPlanEntry(FrozenModel):
    gate_id: BusinessPathGate
    scenario_path: str = Field(min_length=1, max_length=1024)
    driver_config_path: str = Field(min_length=1, max_length=1024)
    pipeline_check_id: str = Field(
        default="fabric.pipeline",
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )

    @model_validator(mode="after")
    def validate_paths(self) -> "BusinessPathCertificationPlanEntry":
        _validate_relative_project_path(self.scenario_path, "scenario_path")
        _validate_relative_project_path(self.driver_config_path, "driver_config_path")
        return self


class ApprovedBusinessPathCertificationPlan(FrozenModel):
    plan_schema_version: int = Field(default=BUSINESS_PATH_PLAN_SCHEMA_VERSION, ge=1)
    plan_artifact_name: str = Field(min_length=1, max_length=512)
    entries: tuple[BusinessPathCertificationPlanEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_complete_gate_set(self) -> "ApprovedBusinessPathCertificationPlan":
        gates = [entry.gate_id for entry in self.entries]
        if len(gates) != len(set(gates)):
            raise ValueError("business path certification plan gate_id values must be unique")
        observed = frozenset(gates)
        if observed != _REQUIRED_GATES:
            missing = sorted(gate.value for gate in _REQUIRED_GATES - observed)
            unexpected = sorted(gate.value for gate in observed - _REQUIRED_GATES)
            raise ValueError(
                "business path certification plan must cover exactly all required gates: "
                f"missing={missing}, unexpected={unexpected}"
            )
        assert_safe_retained_text(self.model_dump_json(), "business path certification plan")
        return self

    @property
    def plan_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


def resolve_business_path_plan_file(project_root: str | Path, relative_path: str) -> Path:
    """Resolve a plan-owned path and fail closed if it escapes the exact project root."""

    _validate_relative_project_path(relative_path, "business path plan path")
    root = Path(project_root).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("business path plan path escapes project root") from exc
    return candidate


def load_approved_business_path_certification_plan(
    path: str | Path,
    *,
    release_manifest: ReleaseManifest,
) -> ApprovedBusinessPathCertificationPlan:
    """Load the exact plan only when its bytes are fingerprinted by the domain release."""

    source = Path(path)
    raw = source.read_bytes()
    plan = ApprovedBusinessPathCertificationPlan.model_validate_json(raw)
    expected_digest = release_manifest.artifact_sha256.get(plan.plan_artifact_name)
    if expected_digest is None:
        raise ValueError("business path certification plan is absent from release manifest")
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError("business path certification plan SHA256 mismatch")
    return plan


__all__ = [
    "BUSINESS_PATH_PLAN_SCHEMA_VERSION",
    "ApprovedBusinessPathCertificationPlan",
    "BusinessPathCertificationPlanEntry",
    "load_approved_business_path_certification_plan",
    "resolve_business_path_plan_file",
]
