"""Explicit rerun prerequisite projection from retained certified integration evidence.

Approved provider runners intentionally reject automatic reruns when a selected check
already has a result. Representative business-path drills need deliberate Pipeline
reruns, so this module creates a new non-certified prerequisite manifest only after the
source manifest is fully certified. It preserves all other retained results and marks
exactly one Pipeline check NOT_RUN. The original certified manifest remains immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    validate_integration_evidence_manifest,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def prepare_explicit_pipeline_rerun_prerequisite(
    spec: IntegrationEvidenceSpec,
    certified_manifest: IntegrationEvidenceManifest,
    *,
    check_id: str,
    now=_utcnow,
) -> IntegrationEvidenceManifest:
    """Return a new exact-spec prerequisite for one explicitly authorized Pipeline rerun."""

    validate_integration_evidence_manifest(
        spec,
        certified_manifest,
        require_certified=True,
    )
    specs = {item.check_id: item for item in spec.checks}
    selected = specs.get(check_id)
    if selected is None:
        raise ValueError("explicit Pipeline rerun check is absent from integration spec")
    if selected.kind is not IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN:
        raise ValueError("explicit rerun prerequisite only supports FABRIC_PIPELINE_RUN")

    by_id = {item.check_id: item for item in certified_manifest.results}
    original = by_id[check_id]
    if original.status is not IntegrationEvidenceStatus.PASS:
        raise ValueError("explicit Pipeline rerun requires retained PASS source evidence")

    at = now()
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("explicit Pipeline rerun projection time must be timezone-aware")
    replacement = IntegrationEvidenceCheckResult(
        check_id=selected.check_id,
        kind=selected.kind,
        status=IntegrationEvidenceStatus.NOT_RUN,
        started_at=at,
        completed_at=at,
        detail=(
            "explicit Pipeline rerun prerequisite projected from separately retained "
            f"certified manifest hash {certified_manifest.manifest_hash}"
        ),
    )
    projected = tuple(
        replacement if item.check_id == check_id else item
        for item in certified_manifest.results
    )
    result = IntegrationEvidenceManifest(
        evidence_schema_version=certified_manifest.evidence_schema_version,
        environment=certified_manifest.environment,
        domain=certified_manifest.domain,
        framework_version=certified_manifest.framework_version,
        release_hash=certified_manifest.release_hash,
        domain_release_hash=certified_manifest.domain_release_hash,
        started_at=at,
        completed_at=at,
        checks=certified_manifest.checks,
        results=projected,
    )
    validate_integration_evidence_manifest(spec, result)
    if result.certified:
        raise RuntimeError("explicit rerun prerequisite must not remain certified")
    return result


__all__ = ["prepare_explicit_pipeline_rerun_prerequisite"]
