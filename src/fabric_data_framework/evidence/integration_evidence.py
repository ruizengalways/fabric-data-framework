"""Credential-free evidence contracts and runner for approved integration checks.

This module is intentionally provider-execution agnostic: concrete check callables may
invoke the existing Fabric Pipeline, Copy Job, Spark, Warehouse and control-plane
certification APIs. The harness aggregates only sanitized evidence references and
correlation identifiers. It never accepts or persists access tokens, passwords or
connection secrets.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.environment import EnvironmentName


INTEGRATION_EVIDENCE_SCHEMA_VERSION = 1


class IntegrationEvidenceCheckKind(str, Enum):
    FABRIC_ITEM_READ = "FABRIC_ITEM_READ"
    FABRIC_PIPELINE_RUN = "FABRIC_PIPELINE_RUN"
    FABRIC_COPY_JOB_CAPTURE = "FABRIC_COPY_JOB_CAPTURE"
    FABRIC_SPARK_CAPTURE = "FABRIC_SPARK_CAPTURE"
    FABRIC_WAREHOUSE_TARGET_COMMIT = "FABRIC_WAREHOUSE_TARGET_COMMIT"
    FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL = "FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL"
    CONTROL_PLANE_CERTIFICATION = "CONTROL_PLANE_CERTIFICATION"
    KAFKA_PROVIDER = "KAFKA_PROVIDER"
    DELTA_CDF_PROVIDER = "DELTA_CDF_PROVIDER"


class IntegrationEvidenceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    EXTERNAL_REQUIRED = "EXTERNAL_REQUIRED"


_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(client[_-]?secret|password|passwd|access[_-]?token|refresh[_-]?token)\b"),
    re.compile(r"(?i)\bauthorization\s*[:=]"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)([?&](sig|token|secret|password|client_secret)=)"),
)


def _reject_secret_material(value: str, field_name: str) -> str:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(value):
            raise ValueError(f"{field_name} appears to contain credential material")
    if "://" in value:
        authority = value.split("://", 1)[1].split("/", 1)[0]
        if "@" in authority and ":" in authority.split("@", 1)[0]:
            raise ValueError(f"{field_name} must not contain URI user-info credentials")
    return value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class IntegrationEvidenceCheckSpec(FrozenModel):
    check_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    kind: IntegrationEvidenceCheckKind
    required: bool = True
    description: str | None = Field(default=None, max_length=1000)


class IntegrationEvidenceSpec(FrozenModel):
    evidence_schema_version: int = Field(default=INTEGRATION_EVIDENCE_SCHEMA_VERSION, ge=1)
    environment: EnvironmentName
    domain: str = Field(min_length=1, max_length=128)
    framework_version: str = Field(min_length=1, max_length=64)
    # release_hash is the exact framework artifact SHA256 used by candidate readiness.
    release_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    # domain_release_hash is the independent DatasetConfig/domain release identity.
    domain_release_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    checks: tuple[IntegrationEvidenceCheckSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_checks(self) -> "IntegrationEvidenceSpec":
        ids = [item.check_id for item in self.checks]
        if len(set(ids)) != len(ids):
            raise ValueError("integration evidence check_id values must be unique")
        return self


class IntegrationEvidenceCheckResult(FrozenModel):
    check_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    kind: IntegrationEvidenceCheckKind
    status: IntegrationEvidenceStatus
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime = Field(default_factory=_utcnow)
    framework_pipeline_run_id: UUID | None = None
    dataset_run_id: UUID | None = None
    operation_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    workspace_id: UUID | None = None
    item_id: UUID | None = None
    native_job_instance_id: UUID | None = None
    root_activity_id: UUID | None = None
    native_operation_id: str | None = Field(default=None, max_length=1024)
    evidence_references: tuple[str, ...] = ()
    detail: str | None = Field(default=None, max_length=4000)

    @field_validator("native_operation_id", "detail")
    @classmethod
    def reject_sensitive_text(cls, value: str | None, info):
        if value is None:
            return value
        return _reject_secret_material(value, info.field_name)

    @field_validator("evidence_references")
    @classmethod
    def validate_references(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("evidence_references must be unique")
        for value in values:
            if not value.strip():
                raise ValueError("evidence references must be non-empty")
            if len(value) > 2048:
                raise ValueError("evidence reference exceeds 2048 characters")
            _reject_secret_material(value, "evidence_reference")
        return values

    @model_validator(mode="after")
    def validate_result(self) -> "IntegrationEvidenceCheckResult":
        _aware(self.started_at, "started_at")
        _aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")
        if self.status is IntegrationEvidenceStatus.PASS:
            self._validate_pass_evidence()
        return self

    def _validate_pass_evidence(self) -> None:
        if self.kind is IntegrationEvidenceCheckKind.FABRIC_ITEM_READ:
            if self.workspace_id is None or self.item_id is None:
                raise ValueError("FABRIC_ITEM_READ PASS requires workspace_id and item_id")
        elif self.kind is IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN:
            if (
                self.framework_pipeline_run_id is None
                or self.workspace_id is None
                or self.item_id is None
                or self.native_job_instance_id is None
                or self.root_activity_id is None
            ):
                raise ValueError(
                    "FABRIC_PIPELINE_RUN PASS requires framework pipeline, workspace, item, native job and root activity IDs"
                )
        elif self.kind in {
            IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
            IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE,
        }:
            if (
                self.dataset_run_id is None
                or self.workspace_id is None
                or self.item_id is None
                or self.native_job_instance_id is None
                or self.root_activity_id is None
            ):
                raise ValueError(
                    f"{self.kind.value} PASS requires dataset, workspace, item, native job and root activity IDs"
                )
        elif self.kind is IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT:
            if self.operation_key is None:
                raise ValueError(
                    "FABRIC_WAREHOUSE_TARGET_COMMIT PASS requires operation_key"
                )
        elif self.kind is IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL:
            if self.operation_key is None or self.dataset_run_id is None:
                raise ValueError(
                    "FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL PASS requires operation_key and dataset_run_id"
                )
        if not self.evidence_references:
            raise ValueError(f"{self.kind.value} PASS requires retained evidence_references")


IntegrationEvidenceCheckRunner = Callable[[], IntegrationEvidenceCheckResult]


class IntegrationEvidenceManifest(FrozenModel):
    evidence_schema_version: int = Field(default=INTEGRATION_EVIDENCE_SCHEMA_VERSION, ge=1)
    evidence_id: UUID = Field(default_factory=uuid4)
    environment: EnvironmentName
    domain: str = Field(min_length=1, max_length=128)
    framework_version: str = Field(min_length=1, max_length=64)
    release_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    domain_release_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    started_at: datetime
    completed_at: datetime
    checks: tuple[IntegrationEvidenceCheckSpec, ...]
    results: tuple[IntegrationEvidenceCheckResult, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> "IntegrationEvidenceManifest":
        _aware(self.started_at, "started_at")
        _aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")
        specs = {item.check_id: item for item in self.checks}
        results = {item.check_id: item for item in self.results}
        if len(specs) != len(self.checks):
            raise ValueError("manifest check IDs must be unique")
        if len(results) != len(self.results):
            raise ValueError("manifest result check IDs must be unique")
        if set(specs) != set(results):
            missing = sorted(set(specs) - set(results))
            unexpected = sorted(set(results) - set(specs))
            raise ValueError(
                "manifest result membership must exactly match spec: "
                f"missing={missing}, unexpected={unexpected}"
            )
        for check_id, spec in specs.items():
            if results[check_id].kind is not spec.kind:
                raise ValueError(
                    f"manifest result kind mismatch for {check_id}: "
                    f"expected={spec.kind.value}, observed={results[check_id].kind.value}"
                )
        return self

    @property
    def certified(self) -> bool:
        by_id = {item.check_id: item for item in self.results}
        return all(
            (not spec.required)
            or by_id[spec.check_id].status is IntegrationEvidenceStatus.PASS
            for spec in self.checks
        )

    @property
    def manifest_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"evidence_id"})
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _not_run(spec: IntegrationEvidenceCheckSpec, *, at: datetime) -> IntegrationEvidenceCheckResult:
    return IntegrationEvidenceCheckResult(
        check_id=spec.check_id,
        kind=spec.kind,
        status=IntegrationEvidenceStatus.NOT_RUN,
        started_at=at,
        completed_at=at,
        detail="no integration check runner was registered",
    )


def _failed_runner(
    spec: IntegrationEvidenceCheckSpec,
    *,
    started_at: datetime,
    completed_at: datetime,
    exc: Exception,
) -> IntegrationEvidenceCheckResult:
    # Exception messages are deliberately excluded because provider/driver exceptions
    # may contain credential-bearing URLs or connection strings.
    return IntegrationEvidenceCheckResult(
        check_id=spec.check_id,
        kind=spec.kind,
        status=IntegrationEvidenceStatus.FAIL,
        started_at=started_at,
        completed_at=completed_at,
        detail=f"integration check runner raised {type(exc).__name__}",
    )


def run_integration_evidence(
    spec: IntegrationEvidenceSpec,
    *,
    runners: Mapping[str, IntegrationEvidenceCheckRunner],
    now: Callable[[], datetime] = _utcnow,
) -> IntegrationEvidenceManifest:
    """Run registered checks in spec order and aggregate credential-free evidence.

    Missing runners become NOT_RUN. Exceptions become FAIL without copying exception
    text into the retained manifest. A runner must return the exact check_id/kind it
    was registered for; mismatches fail closed. Runner IDs not present in the spec are
    rejected rather than silently ignored.
    """

    expected_ids = {item.check_id for item in spec.checks}
    unexpected_runner_ids = sorted(set(runners) - expected_ids)
    if unexpected_runner_ids:
        raise ValueError(
            "integration runners are not declared in evidence spec: "
            + ", ".join(unexpected_runner_ids)
        )

    started_at = now()
    _aware(started_at, "started_at")
    results: list[IntegrationEvidenceCheckResult] = []
    for check in spec.checks:
        runner = runners.get(check.check_id)
        if runner is None:
            results.append(_not_run(check, at=now()))
            continue
        check_started = now()
        try:
            result = runner()
            if result.check_id != check.check_id or result.kind is not check.kind:
                raise ValueError(
                    "integration runner result identity does not match registered check"
                )
            results.append(result)
        except Exception as exc:
            results.append(
                _failed_runner(
                    check,
                    started_at=check_started,
                    completed_at=now(),
                    exc=exc,
                )
            )
    completed_at = now()
    return IntegrationEvidenceManifest(
        evidence_schema_version=spec.evidence_schema_version,
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        domain_release_hash=spec.domain_release_hash,
        started_at=started_at,
        completed_at=completed_at,
        checks=spec.checks,
        results=tuple(results),
    )


def validate_integration_evidence_manifest(
    spec: IntegrationEvidenceSpec,
    manifest: IntegrationEvidenceManifest,
    *,
    require_certified: bool = False,
) -> None:
    """Validate a retained manifest against the exact requested evidence spec."""

    if manifest.evidence_schema_version != spec.evidence_schema_version:
        raise ValueError("evidence schema version mismatch")
    if manifest.environment is not spec.environment:
        raise ValueError("evidence environment mismatch")
    if manifest.domain != spec.domain:
        raise ValueError("evidence domain mismatch")
    if manifest.framework_version != spec.framework_version:
        raise ValueError("evidence framework version mismatch")
    if manifest.release_hash != spec.release_hash:
        raise ValueError("evidence framework artifact release hash mismatch")
    if manifest.domain_release_hash != spec.domain_release_hash:
        raise ValueError("evidence domain release hash mismatch")
    if manifest.checks != spec.checks:
        raise ValueError("retained evidence check specification does not match requested spec")
    if require_certified and not manifest.certified:
        by_id = {item.check_id: item for item in manifest.results}
        failed = [
            item.check_id
            for item in manifest.checks
            if item.required
            and by_id[item.check_id].status is not IntegrationEvidenceStatus.PASS
        ]
        raise ValueError(
            "integration evidence is not certified; required checks not PASS: "
            + ", ".join(failed)
        )


def load_integration_evidence_spec(path: str | Path) -> IntegrationEvidenceSpec:
    return IntegrationEvidenceSpec.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_integration_evidence_manifest(path: str | Path) -> IntegrationEvidenceManifest:
    return IntegrationEvidenceManifest.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def write_integration_evidence_manifest(
    manifest: IntegrationEvidenceManifest,
    path: str | Path,
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "INTEGRATION_EVIDENCE_SCHEMA_VERSION",
    "IntegrationEvidenceCheckKind",
    "IntegrationEvidenceCheckResult",
    "IntegrationEvidenceCheckRunner",
    "IntegrationEvidenceCheckSpec",
    "IntegrationEvidenceManifest",
    "IntegrationEvidenceSpec",
    "IntegrationEvidenceStatus",
    "load_integration_evidence_manifest",
    "load_integration_evidence_spec",
    "run_integration_evidence",
    "validate_integration_evidence_manifest",
    "write_integration_evidence_manifest",
]
