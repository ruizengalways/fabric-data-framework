"""Fail-closed merge for exact-candidate partial release proof bundles.

Release proof is intentionally produced in stages. Portable source/wheel/customer
checks and representative live business-path drills may be retained by different
workflows. This module combines those partial bundles without inventing evidence and
without applying timestamp, PASS-wins, or latest-wins precedence.
"""

from __future__ import annotations

from collections.abc import Iterable

from fabric_data_framework.evidence.release_readiness import (
    ReleaseReadinessProofBundle,
    ReleaseReadinessProofResult,
    ReleaseReadinessSpec,
    ReleaseReadinessStatus,
)
from fabric_data_framework.evidence.safety import assert_safe_retained_text


class ReleaseReadinessProofMergeConflict(RuntimeError):
    """Raised when partial bundles disagree on substantive proof for one gate."""


def _same_result(
    left: ReleaseReadinessProofResult,
    right: ReleaseReadinessProofResult,
) -> bool:
    return left.model_dump(mode="json") == right.model_dump(mode="json")


def _validate_partial_bundle(
    spec: ReleaseReadinessSpec,
    bundle: ReleaseReadinessProofBundle,
) -> None:
    if bundle.readiness_schema_version != spec.readiness_schema_version:
        raise ValueError("release proof readiness schema version does not match readiness spec")
    if bundle.framework_version != spec.framework_version:
        raise ValueError("release proof framework version does not match readiness spec")
    if bundle.artifact_sha256 is None:
        raise ValueError("partial release proof bundle must bind exact artifact_sha256")

    gates = {gate.gate_id: gate for gate in spec.gates}
    for result in bundle.results:
        gate = gates.get(result.gate_id)
        if gate is None:
            raise ValueError(f"release proof references unknown gate {result.gate_id}")
        if gate.integration_check_id is not None:
            raise ValueError(
                f"integration-backed gate {result.gate_id} cannot be supplied by release proof bundle"
            )
        if result.kind is not gate.kind:
            raise ValueError(f"release proof kind mismatch for {result.gate_id}")
        for reference in result.evidence_references:
            assert_safe_retained_text(reference, "release evidence reference")
        if result.detail is not None:
            assert_safe_retained_text(result.detail, "release evidence detail")


def merge_release_readiness_proof_bundles(
    spec: ReleaseReadinessSpec,
    bundles: Iterable[ReleaseReadinessProofBundle],
) -> ReleaseReadinessProofBundle:
    """Merge staged proof for one exact source/wheel candidate.

    Rules are deliberately strict:

    - every input must match the readiness schema/framework and bind the same
      candidate SHA and exact wheel SHA;
    - every proof result must match the source-controlled readiness spec;
    - integration-backed gates are rejected because IntegrationEvidenceManifest owns them;
    - retained evidence text is secret-scanned before it can enter merged output;
    - omitted/NOT_RUN results mean no proof and do not override substantive evidence;
    - one substantive PASS/FAIL/OUT_OF_SCOPE result is retained unchanged;
    - model-identical duplicate substantive results are harmless;
    - different substantive results for the same gate conflict, even if both are PASS.

    A conflicting rerun must be explicitly selected by the operator before merge.
    """

    items = tuple(bundles)
    if not items:
        raise ValueError("at least one partial release proof bundle is required")

    for bundle in items:
        _validate_partial_bundle(spec, bundle)

    first = items[0]
    assert first.artifact_sha256 is not None
    for bundle in items[1:]:
        if bundle.candidate_git_sha != first.candidate_git_sha:
            raise ValueError("partial release proof candidate git SHA mismatch")
        if bundle.artifact_sha256 != first.artifact_sha256:
            raise ValueError("partial release proof artifact SHA256 mismatch")

    result_maps = [{item.gate_id: item for item in bundle.results} for bundle in items]
    merged: list[ReleaseReadinessProofResult] = []

    for gate in spec.gates:
        if gate.integration_check_id is not None:
            continue
        substantive: list[ReleaseReadinessProofResult] = []
        for by_id in result_maps:
            result = by_id.get(gate.gate_id)
            if result is not None and result.status is not ReleaseReadinessStatus.NOT_RUN:
                substantive.append(result)

        if not substantive:
            continue

        chosen = substantive[0]
        for other in substantive[1:]:
            if not _same_result(chosen, other):
                raise ReleaseReadinessProofMergeConflict(
                    "conflicting substantive release proof for "
                    f"gate {gate.gate_id!r}; explicitly choose one rerun result before merge"
                )
        merged.append(chosen)

    return ReleaseReadinessProofBundle(
        readiness_schema_version=spec.readiness_schema_version,
        framework_version=spec.framework_version,
        candidate_git_sha=first.candidate_git_sha,
        artifact_sha256=first.artifact_sha256,
        results=tuple(merged),
    )


__all__ = [
    "ReleaseReadinessProofMergeConflict",
    "merge_release_readiness_proof_bundles",
]
