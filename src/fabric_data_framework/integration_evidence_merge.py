"""Fail-closed merge of staged integration-evidence manifests.

Real approved-environment checks are intentionally staged. A read-only Fabric item
smoke may run hours or days before control-plane certification or mutating provider
checks. This module combines those retained partial manifests without re-running prior
checks and without silently choosing between contradictory evidence.
"""

from __future__ import annotations

from collections.abc import Iterable

from .integration_evidence import (
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    validate_integration_evidence_manifest,
)


class IntegrationEvidenceMergeConflict(RuntimeError):
    """Raised when staged manifests contain different substantive results for a check."""


def _same_result(
    left: IntegrationEvidenceCheckResult,
    right: IntegrationEvidenceCheckResult,
) -> bool:
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def merge_integration_evidence_manifests(
    spec: IntegrationEvidenceSpec,
    manifests: Iterable[IntegrationEvidenceManifest],
) -> IntegrationEvidenceManifest:
    """Merge exact-spec staged evidence into one ordinary manifest.

    Rules are deliberately strict:

    - every input must match the exact evidence spec/environment/domain/framework/release;
    - ``NOT_RUN`` is absence of evidence and may be filled by another partial manifest;
    - one substantive result (PASS/FAIL/EXTERNAL_REQUIRED) is retained unchanged;
    - byte-for-model identical duplicate substantive results are harmless;
    - two different substantive results for the same check are a conflict and are not
      ordered by timestamp or status.

    The caller must explicitly choose the intended rerun manifest before merging when
    a check has been executed more than once with different evidence.
    """

    items = tuple(manifests)
    if not items:
        raise ValueError("at least one integration evidence manifest is required")

    for manifest in items:
        validate_integration_evidence_manifest(spec, manifest)

    results_by_manifest = [
        {result.check_id: result for result in manifest.results} for manifest in items
    ]
    merged_results: list[IntegrationEvidenceCheckResult] = []
    merged_completed_at = max(manifest.completed_at for manifest in items)

    for check in spec.checks:
        substantive: list[tuple[IntegrationEvidenceManifest, IntegrationEvidenceCheckResult]] = []
        for manifest, by_id in zip(items, results_by_manifest, strict=True):
            result = by_id[check.check_id]
            if result.status is not IntegrationEvidenceStatus.NOT_RUN:
                substantive.append((manifest, result))

        if not substantive:
            merged_results.append(
                IntegrationEvidenceCheckResult(
                    check_id=check.check_id,
                    kind=check.kind,
                    status=IntegrationEvidenceStatus.NOT_RUN,
                    started_at=merged_completed_at,
                    completed_at=merged_completed_at,
                    detail="check was NOT_RUN in every merged partial manifest",
                )
            )
            continue

        chosen_manifest, chosen = substantive[0]
        for other_manifest, other in substantive[1:]:
            if not _same_result(chosen, other):
                raise IntegrationEvidenceMergeConflict(
                    "conflicting substantive integration evidence for "
                    f"check {check.check_id!r}: evidence_id="
                    f"{chosen_manifest.evidence_id} differs from evidence_id="
                    f"{other_manifest.evidence_id}; explicitly choose one rerun result"
                )
        merged_results.append(chosen)

    return IntegrationEvidenceManifest(
        evidence_schema_version=spec.evidence_schema_version,
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        started_at=min(manifest.started_at for manifest in items),
        completed_at=merged_completed_at,
        checks=spec.checks,
        results=tuple(merged_results),
    )


__all__ = [
    "IntegrationEvidenceMergeConflict",
    "merge_integration_evidence_manifests",
]
