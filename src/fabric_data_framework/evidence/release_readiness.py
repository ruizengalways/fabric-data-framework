"""Fail-closed release-candidate readiness aggregation.

This module does not execute Fabric or invent proof. It evaluates retained release
proofs and the existing IntegrationEvidenceManifest against a source-controlled
readiness specification for an exact framework version, candidate git SHA, framework
artifact SHA256 and, when supplied, exact customer/domain release SHA256.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Mapping

from pydantic import Field, field_validator, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceManifest,
    IntegrationEvidenceStatus,
)


RELEASE_READINESS_SCHEMA_VERSION = 1


class ReleaseReadinessGateKind(str, Enum):
    SOURCE_VERIFICATION = "SOURCE_VERIFICATION"
    WHEEL_INTEGRITY = "WHEEL_INTEGRITY"
    CUSTOMER_COMPATIBILITY = "CUSTOMER_COMPATIBILITY"
    FABRIC_IDENTITY = "FABRIC_IDENTITY"
    CONTROL_PLANE = "CONTROL_PLANE"
    FABRIC_PIPELINE = "FABRIC_PIPELINE"
    FABRIC_COPY_CAPTURE = "FABRIC_COPY_CAPTURE"
    FABRIC_SPARK_CAPTURE = "FABRIC_SPARK_CAPTURE"
    FULL_REPLACE = "FULL_REPLACE"
    WATERMARK_SCD1 = "WATERMARK_SCD1"
    WATERMARK_SCD2 = "WATERMARK_SCD2"
    RETRY_IDEMPOTENCY = "RETRY_IDEMPOTENCY"
    RECONCILIATION_FAIL_CLOSED = "RECONCILIATION_FAIL_CLOSED"
    STATE_COMMIT_SAFETY = "STATE_COMMIT_SAFETY"
    AMBIGUOUS_COMMIT_RECOVERY = "AMBIGUOUS_COMMIT_RECOVERY"
    EXTERNAL_CDC = "EXTERNAL_CDC"


class ReleaseReadinessStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ReleaseReadinessResultSource(str, Enum):
    PROOF_BUNDLE = "PROOF_BUNDLE"
    INTEGRATION_EVIDENCE = "INTEGRATION_EVIDENCE"
    MISSING = "MISSING"


class ReleaseReadinessGateSpec(FrozenModel):
    gate_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    kind: ReleaseReadinessGateKind
    required: bool = True
    description: str | None = Field(default=None, max_length=1000)
    integration_check_id: str | None = Field(
        default=None,
        max_length=128,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )


class ReleaseReadinessSpec(FrozenModel):
    readiness_schema_version: int = Field(default=RELEASE_READINESS_SCHEMA_VERSION, ge=1)
    framework_version: str = Field(min_length=1, max_length=64)
    gates: tuple[ReleaseReadinessGateSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_gates(self) -> "ReleaseReadinessSpec":
        ids = [gate.gate_id for gate in self.gates]
        if len(ids) != len(set(ids)):
            raise ValueError("release readiness gate_id values must be unique")
        integration_ids = [
            gate.integration_check_id
            for gate in self.gates
            if gate.integration_check_id is not None
        ]
        if len(integration_ids) != len(set(integration_ids)):
            raise ValueError("integration_check_id values must be unique across readiness gates")
        return self


class ReleaseReadinessProofResult(FrozenModel):
    gate_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    kind: ReleaseReadinessGateKind
    status: ReleaseReadinessStatus
    evidence_references: tuple[str, ...] = ()
    detail: str | None = Field(default=None, max_length=4000)

    @field_validator("evidence_references")
    @classmethod
    def validate_references(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("release evidence_references must be unique")
        for value in values:
            if not value.strip():
                raise ValueError("release evidence references must be non-empty")
            if len(value) > 2048:
                raise ValueError("release evidence reference exceeds 2048 characters")
        return values

    @model_validator(mode="after")
    def validate_status(self) -> "ReleaseReadinessProofResult":
        if self.status is ReleaseReadinessStatus.PASS and not self.evidence_references:
            raise ValueError("release readiness PASS requires retained evidence_references")
        return self


class ReleaseReadinessProofBundle(FrozenModel):
    readiness_schema_version: int = Field(default=RELEASE_READINESS_SCHEMA_VERSION, ge=1)
    framework_version: str = Field(min_length=1, max_length=64)
    candidate_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    domain_release_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    results: tuple[ReleaseReadinessProofResult, ...] = ()

    @model_validator(mode="after")
    def validate_results(self) -> "ReleaseReadinessProofBundle":
        ids = [result.gate_id for result in self.results]
        if len(ids) != len(set(ids)):
            raise ValueError("release proof gate_id values must be unique")
        return self


class ReleaseReadinessGateResult(FrozenModel):
    gate_id: str
    kind: ReleaseReadinessGateKind
    required: bool
    status: ReleaseReadinessStatus
    source: ReleaseReadinessResultSource
    evidence_references: tuple[str, ...] = ()
    detail: str | None = None


class ReleaseReadinessReport(FrozenModel):
    readiness_schema_version: int = Field(default=RELEASE_READINESS_SCHEMA_VERSION, ge=1)
    framework_version: str
    candidate_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    domain_release_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime
    release_ready: bool
    blockers: tuple[str, ...]
    results: tuple[ReleaseReadinessGateResult, ...]

    @model_validator(mode="after")
    def validate_report(self) -> "ReleaseReadinessReport":
        if self.release_ready != (not self.blockers):
            raise ValueError("release_ready must exactly match blocker presence")
        return self


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _missing_result(gate: ReleaseReadinessGateSpec) -> ReleaseReadinessGateResult:
    return ReleaseReadinessGateResult(
        gate_id=gate.gate_id,
        kind=gate.kind,
        required=gate.required,
        status=ReleaseReadinessStatus.NOT_RUN,
        source=ReleaseReadinessResultSource.MISSING,
        detail="no retained release proof was supplied",
    )


def _from_proof(
    gate: ReleaseReadinessGateSpec,
    proof: ReleaseReadinessProofResult,
) -> ReleaseReadinessGateResult:
    return ReleaseReadinessGateResult(
        gate_id=gate.gate_id,
        kind=gate.kind,
        required=gate.required,
        status=proof.status,
        source=ReleaseReadinessResultSource.PROOF_BUNDLE,
        evidence_references=proof.evidence_references,
        detail=proof.detail,
    )


def _from_integration(
    gate: ReleaseReadinessGateSpec,
    manifest: IntegrationEvidenceManifest,
) -> ReleaseReadinessGateResult:
    assert gate.integration_check_id is not None
    by_id = {result.check_id: result for result in manifest.results}
    result = by_id.get(gate.integration_check_id)
    if result is None:
        return ReleaseReadinessGateResult(
            gate_id=gate.gate_id,
            kind=gate.kind,
            required=gate.required,
            status=ReleaseReadinessStatus.NOT_RUN,
            source=ReleaseReadinessResultSource.INTEGRATION_EVIDENCE,
            detail=f"integration evidence check {gate.integration_check_id} is absent",
        )
    status_map: Mapping[IntegrationEvidenceStatus, ReleaseReadinessStatus] = {
        IntegrationEvidenceStatus.PASS: ReleaseReadinessStatus.PASS,
        IntegrationEvidenceStatus.FAIL: ReleaseReadinessStatus.FAIL,
        IntegrationEvidenceStatus.NOT_RUN: ReleaseReadinessStatus.NOT_RUN,
        IntegrationEvidenceStatus.EXTERNAL_REQUIRED: ReleaseReadinessStatus.NOT_RUN,
    }
    return ReleaseReadinessGateResult(
        gate_id=gate.gate_id,
        kind=gate.kind,
        required=gate.required,
        status=status_map[result.status],
        source=ReleaseReadinessResultSource.INTEGRATION_EVIDENCE,
        evidence_references=result.evidence_references,
        detail=result.detail,
    )


def evaluate_release_readiness(
    spec: ReleaseReadinessSpec,
    *,
    candidate_git_sha: str,
    artifact_sha256: str | None = None,
    proofs: ReleaseReadinessProofBundle | None = None,
    integration_evidence: IntegrationEvidenceManifest | None = None,
    now=_utcnow,
) -> ReleaseReadinessReport:
    """Evaluate an exact release candidate without inferring missing evidence.

    Integration-backed gates may only be satisfied by IntegrationEvidenceManifest.
    Other gates may only be satisfied by the explicit proof bundle. Missing evidence is
    NOT_RUN. Required gates are ready only when PASS.

    When both proof and integration evidence carry a customer/domain release identity,
    they must match exactly. The resolved identity is retained in the readiness report
    so exact-byte promotion can re-verify the same business release.
    """

    if not __import__("re").fullmatch(r"[0-9a-f]{40}", candidate_git_sha):
        raise ValueError("candidate_git_sha must be a 40-character lowercase git SHA")
    if artifact_sha256 is not None and not __import__("re").fullmatch(
        r"[0-9a-f]{64}", artifact_sha256
    ):
        raise ValueError("artifact_sha256 must be a 64-character lowercase SHA256")

    gate_by_id = {gate.gate_id: gate for gate in spec.gates}
    proof_by_id: dict[str, ReleaseReadinessProofResult] = {}
    domain_release_hash: str | None = None
    if proofs is not None:
        if proofs.framework_version != spec.framework_version:
            raise ValueError("release proof framework version mismatch")
        if proofs.candidate_git_sha != candidate_git_sha:
            raise ValueError("release proof candidate git SHA mismatch")
        if artifact_sha256 is not None and proofs.artifact_sha256 != artifact_sha256:
            raise ValueError("release proof artifact SHA256 mismatch")
        if artifact_sha256 is None and proofs.artifact_sha256 is not None:
            artifact_sha256 = proofs.artifact_sha256
        domain_release_hash = proofs.domain_release_hash
        for proof in proofs.results:
            gate = gate_by_id.get(proof.gate_id)
            if gate is None:
                raise ValueError(f"release proof references unknown gate {proof.gate_id}")
            if gate.integration_check_id is not None:
                raise ValueError(
                    f"integration-backed gate {proof.gate_id} cannot be satisfied by proof bundle"
                )
            if proof.kind is not gate.kind:
                raise ValueError(f"release proof kind mismatch for {proof.gate_id}")
            proof_by_id[proof.gate_id] = proof

    if integration_evidence is not None:
        if integration_evidence.framework_version != spec.framework_version:
            raise ValueError("integration evidence framework version mismatch")
        if artifact_sha256 is None:
            raise ValueError(
                "artifact_sha256 is required when integration evidence is supplied"
            )
        if integration_evidence.release_hash != artifact_sha256:
            raise ValueError("integration evidence release hash does not match artifact SHA256")
        if proofs is not None and (
            proofs.domain_release_hash != integration_evidence.domain_release_hash
        ):
            raise ValueError("release proof domain release hash mismatch")
        if domain_release_hash is None:
            domain_release_hash = integration_evidence.domain_release_hash

    results: list[ReleaseReadinessGateResult] = []
    for gate in spec.gates:
        if gate.integration_check_id is not None:
            if integration_evidence is None:
                result = _missing_result(gate)
            else:
                result = _from_integration(gate, integration_evidence)
        else:
            proof = proof_by_id.get(gate.gate_id)
            result = _missing_result(gate) if proof is None else _from_proof(gate, proof)
        if gate.required and result.status is ReleaseReadinessStatus.OUT_OF_SCOPE:
            result = result.model_copy(
                update={
                    "status": ReleaseReadinessStatus.FAIL,
                    "detail": "required release gate cannot be OUT_OF_SCOPE",
                }
            )
        results.append(result)

    blockers = tuple(
        result.gate_id
        for result in results
        if result.required and result.status is not ReleaseReadinessStatus.PASS
    )
    generated_at = now()
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    return ReleaseReadinessReport(
        framework_version=spec.framework_version,
        candidate_git_sha=candidate_git_sha,
        artifact_sha256=artifact_sha256,
        domain_release_hash=domain_release_hash,
        generated_at=generated_at,
        release_ready=not blockers,
        blockers=blockers,
        results=tuple(results),
    )


def load_release_readiness_spec(path: str | Path) -> ReleaseReadinessSpec:
    return ReleaseReadinessSpec.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_release_readiness_proofs(path: str | Path) -> ReleaseReadinessProofBundle:
    return ReleaseReadinessProofBundle.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def write_release_readiness_report(report: ReleaseReadinessReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "RELEASE_READINESS_SCHEMA_VERSION",
    "ReleaseReadinessGateKind",
    "ReleaseReadinessGateResult",
    "ReleaseReadinessGateSpec",
    "ReleaseReadinessProofBundle",
    "ReleaseReadinessProofResult",
    "ReleaseReadinessReport",
    "ReleaseReadinessResultSource",
    "ReleaseReadinessSpec",
    "ReleaseReadinessStatus",
    "evaluate_release_readiness",
    "load_release_readiness_proofs",
    "load_release_readiness_spec",
    "write_release_readiness_report",
]
