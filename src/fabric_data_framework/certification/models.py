"""Unified Fabric certification report contracts.

These models are intentionally credential-free.  The unified runner records only
safe status/detail text and durable evidence references; secret-bearing runtime
values stay process-local.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import Field, computed_field

from fabric_data_framework.contracts.base import FrozenModel


class CertificationCheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    BLOCKED = "BLOCKED"


class CertificationOverallStatus(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class CertificationCheckResult(FrozenModel):
    check_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    status: CertificationCheckStatus
    detail: str = Field(min_length=1, max_length=4000)
    evidence_references: tuple[str, ...] = ()


class UnifiedCertificationReport(FrozenModel):
    report_schema_version: int = Field(default=1, ge=1)
    framework_version: str = Field(min_length=1, max_length=64)
    candidate_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    environment: str = Field(min_length=1, max_length=32)
    started_at: datetime
    completed_at: datetime
    checks: tuple[CertificationCheckResult, ...]
    blockers: tuple[str, ...] = ()
    integration_evidence_path: str | None = None
    business_path_proofs_path: str | None = None
    release_authorized: Literal[False] = False

    @computed_field
    @property
    def overall_status(self) -> CertificationOverallStatus:
        required = tuple(self.checks)
        if any(item.status is CertificationCheckStatus.FAIL for item in required):
            return CertificationOverallStatus.FAIL
        if any(item.status is CertificationCheckStatus.BLOCKED for item in required):
            if any(item.status is CertificationCheckStatus.PASS for item in required):
                return CertificationOverallStatus.PARTIAL
            return CertificationOverallStatus.BLOCKED
        if any(item.status is CertificationCheckStatus.NOT_RUN for item in required):
            return CertificationOverallStatus.PARTIAL
        return CertificationOverallStatus.PASS

    @computed_field
    @property
    def passed(self) -> bool:
        return self.overall_status is CertificationOverallStatus.PASS


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "CertificationCheckResult",
    "CertificationCheckStatus",
    "CertificationOverallStatus",
    "UnifiedCertificationReport",
    "utcnow",
]
