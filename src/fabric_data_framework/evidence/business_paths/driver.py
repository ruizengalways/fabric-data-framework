"""Bounded mutating driver contract for representative live business-path drills.

A business-path driver may prepare deterministic source fixtures or controlled failure
conditions, but it never decides whether a readiness gate passed. The exact driver
recipe and driver extension artifact are fingerprinted by the immutable domain release
manifest. The framework-owned evaluator remains the sole PASS/FAIL authority.
"""

from __future__ import annotations

from enum import Enum
import hashlib
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.deployment.contracts import ReleaseManifest
from fabric_data_framework.evidence.business_path_evidence import BusinessPathGate
from fabric_data_framework.evidence.safety import assert_safe_retained_text
from fabric_data_framework.metadata.config import canonical_hash


class BusinessPathDriverPhase(str, Enum):
    PREPARE_BASELINE = "PREPARE_BASELINE"
    PREPARE_ATTEMPT_1 = "PREPARE_ATTEMPT_1"
    PREPARE_ATTEMPT_2 = "PREPARE_ATTEMPT_2"
    CLEANUP = "CLEANUP"


class ApprovedBusinessPathDriverConfig(FrozenModel):
    """Source-controlled exact-release recipe for one mutating scenario driver."""

    scenario_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    driver_extension: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    extension_artifact_name: str = Field(min_length=1, max_length=512)
    driver_config_artifact_name: str = Field(min_length=1, max_length=512)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_safe_recipe(self) -> "ApprovedBusinessPathDriverConfig":
        assert_safe_retained_text(self.model_dump_json(), "business path driver config")
        return self

    @property
    def driver_config_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))


class BusinessPathDriverRequest(FrozenModel):
    gate_id: BusinessPathGate
    dataset_id: str = Field(min_length=1, max_length=256)
    scenario_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase: BusinessPathDriverPhase
    parameters: dict[str, Any] = Field(default_factory=dict)


class BusinessPathDriverReceipt(FrozenModel):
    """Credential-free mutation receipt; intentionally contains no PASS/FAIL field."""

    gate_id: BusinessPathGate
    dataset_id: str = Field(min_length=1, max_length=256)
    scenario_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase: BusinessPathDriverPhase
    evidence_references: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_safe_receipt(self) -> "BusinessPathDriverReceipt":
        if len(set(self.evidence_references)) != len(self.evidence_references):
            raise ValueError("business path driver evidence references must be unique")
        for index, reference in enumerate(self.evidence_references):
            assert_safe_retained_text(reference, f"driver evidence_references[{index}]")
        return self


def load_approved_business_path_driver_config(
    path: str | Path,
    *,
    release_manifest: ReleaseManifest,
    expected_scenario_hash: str,
) -> ApprovedBusinessPathDriverConfig:
    """Load an exact-release driver recipe and reject un-fingerprinted mutation code."""

    source = Path(path)
    raw = source.read_bytes()
    config = ApprovedBusinessPathDriverConfig.model_validate_json(raw)
    if config.scenario_hash != expected_scenario_hash:
        raise ValueError("business path driver config scenario hash mismatch")

    expected_config_digest = release_manifest.artifact_sha256.get(
        config.driver_config_artifact_name
    )
    if expected_config_digest is None:
        raise ValueError("business path driver config artifact is absent from release manifest")
    if hashlib.sha256(raw).hexdigest() != expected_config_digest:
        raise ValueError("business path driver config artifact SHA256 mismatch")
    if config.extension_artifact_name not in release_manifest.artifact_sha256:
        raise ValueError(
            "business path driver extension artifact is not fingerprinted in exact release manifest"
        )
    return config


def validate_driver_receipt(
    request: BusinessPathDriverRequest,
    receipt: BusinessPathDriverReceipt,
) -> None:
    if receipt.gate_id is not request.gate_id:
        raise ValueError("business path driver receipt gate mismatch")
    if receipt.dataset_id != request.dataset_id:
        raise ValueError("business path driver receipt dataset mismatch")
    if receipt.scenario_hash != request.scenario_hash:
        raise ValueError("business path driver receipt scenario hash mismatch")
    if receipt.phase is not request.phase:
        raise ValueError("business path driver receipt phase mismatch")


__all__ = [
    "ApprovedBusinessPathDriverConfig",
    "BusinessPathDriverPhase",
    "BusinessPathDriverReceipt",
    "BusinessPathDriverRequest",
    "load_approved_business_path_driver_config",
    "validate_driver_receipt",
]
