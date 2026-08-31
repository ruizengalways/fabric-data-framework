from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
)
from fabric_data_framework.evidence.integration_evidence_rerun import (
    prepare_explicit_pipeline_rerun_prerequisite,
)


NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)


def _spec() -> IntegrationEvidenceSpec:
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="control.cert",
                kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            ),
        ),
    )


def _certified(spec: IntegrationEvidenceSpec) -> IntegrationEvidenceManifest:
    return IntegrationEvidenceManifest(
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        started_at=NOW,
        completed_at=NOW,
        checks=spec.checks,
        results=(
            IntegrationEvidenceCheckResult(
                check_id="fabric.item.read",
                kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
                status=IntegrationEvidenceStatus.PASS,
                started_at=NOW,
                completed_at=NOW,
                workspace_id=uuid4(),
                item_id=uuid4(),
                evidence_references=("artifact:item-read",),
            ),
            IntegrationEvidenceCheckResult(
                check_id="control.cert",
                kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
                status=IntegrationEvidenceStatus.PASS,
                started_at=NOW,
                completed_at=NOW,
                evidence_references=("artifact:control-cert",),
            ),
            IntegrationEvidenceCheckResult(
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
                status=IntegrationEvidenceStatus.PASS,
                started_at=NOW,
                completed_at=NOW,
                framework_pipeline_run_id=uuid4(),
                dataset_run_id=uuid4(),
                workspace_id=uuid4(),
                item_id=uuid4(),
                native_job_instance_id=uuid4(),
                root_activity_id=uuid4(),
                evidence_references=("artifact:pipeline",),
            ),
        ),
    )


def test_explicit_pipeline_rerun_preserves_prerequisites_and_resets_only_selected_check():
    spec = _spec()
    source = _certified(spec)
    projected = prepare_explicit_pipeline_rerun_prerequisite(
        spec,
        source,
        check_id="fabric.pipeline",
        now=lambda: NOW,
    )

    assert source.certified is True
    assert projected.certified is False
    source_by_id = {item.check_id: item for item in source.results}
    projected_by_id = {item.check_id: item for item in projected.results}
    assert projected_by_id["fabric.item.read"] == source_by_id["fabric.item.read"]
    assert projected_by_id["control.cert"] == source_by_id["control.cert"]
    assert projected_by_id["fabric.pipeline"].status is IntegrationEvidenceStatus.NOT_RUN
    assert source_by_id["fabric.pipeline"].status is IntegrationEvidenceStatus.PASS
    assert source.evidence_id != projected.evidence_id
    assert source.manifest_hash in projected_by_id["fabric.pipeline"].detail


def test_explicit_pipeline_rerun_requires_fully_certified_source():
    spec = _spec()
    source = _certified(spec)
    results = tuple(
        item.model_copy(update={"status": IntegrationEvidenceStatus.NOT_RUN})
        if item.check_id == "control.cert"
        else item
        for item in source.results
    )
    incomplete = source.model_copy(update={"results": results})

    with pytest.raises(ValueError, match="not certified"):
        prepare_explicit_pipeline_rerun_prerequisite(
            spec,
            incomplete,
            check_id="fabric.pipeline",
        )


def test_explicit_rerun_rejects_unknown_or_non_pipeline_check():
    spec = _spec()
    source = _certified(spec)

    with pytest.raises(ValueError, match="absent"):
        prepare_explicit_pipeline_rerun_prerequisite(
            spec,
            source,
            check_id="missing.check",
        )

    with pytest.raises(ValueError, match="only supports"):
        prepare_explicit_pipeline_rerun_prerequisite(
            spec,
            source,
            check_id="fabric.item.read",
        )
