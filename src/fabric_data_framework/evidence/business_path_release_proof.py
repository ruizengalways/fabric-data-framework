"""Exact customer/domain identity packaging for evaluated business-path proof.

The business-path evaluator remains the sole PASS authority. This module only binds an
already evaluated proof result to the exact customer ReleaseManifest used for the run.
"""

from __future__ import annotations

import json
from pathlib import Path

from fabric_data_framework.deployment.contracts import ReleaseManifest
from fabric_data_framework.evidence.approved_business_path_runner import (
    ApprovedBusinessPathExecutionReport,
)
from fabric_data_framework.evidence.release_readiness import ReleaseReadinessProofBundle


def build_business_path_partial_proof_bundle(
    report: ApprovedBusinessPathExecutionReport,
    release_manifest: ReleaseManifest,
) -> ReleaseReadinessProofBundle:
    if report.domain != release_manifest.domain:
        raise ValueError("business path report/release domain mismatch")
    if report.framework_version != release_manifest.bundle.framework_version:
        raise ValueError("business path report/release framework version mismatch")
    return ReleaseReadinessProofBundle(
        framework_version=report.framework_version,
        candidate_git_sha=report.candidate_git_sha,
        artifact_sha256=report.artifact_sha256,
        domain_release_hash=release_manifest.bundle.release_hash,
        results=(report.proof,),
    )


def write_business_path_release_proof_bundle(
    report: ApprovedBusinessPathExecutionReport,
    release_manifest: ReleaseManifest,
    path: str | Path,
) -> None:
    bundle = build_business_path_partial_proof_bundle(report, release_manifest)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "build_business_path_partial_proof_bundle",
    "write_business_path_release_proof_bundle",
]
