from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from fabric_data_framework.infrastructure import EnvironmentName
from fabric_data_framework.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    validate_integration_evidence_manifest,
)
from fabric_data_framework.integration_evidence_merge import (
    IntegrationEvidenceMergeConflict,
    merge_integration_evidence_manifests,
)


NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
ITEM_WORKSPACE = UUID("00000000-0000-0000-0000-000000000101")
ITEM_ID = UUID("00000000-0000-0000-0000-000000000102")
PIPELINE_RUN = UUID("00000000-0000-0000-0000-000000000201")
PIPELINE_ITEM = UUID("00000000-0000-0000-0000-000000000202")
PIPELINE_JOB = UUID("00000000-0000-0000-0000-000000000203")
PIPELINE_ROOT = UUID("00000000-0000-0000-0000-000000000204")


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
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="kafka.optional",
                kind=IntegrationEvidenceCheckKind.KAFKA_PROVIDER,
                required=False,
            ),
        ),
    )


def _not_run(check: IntegrationEvidenceCheckSpec, *, at: datetime = NOW):
    return IntegrationEvidenceCheckResult(
        check_id=check.check_id,
        kind=check.kind,
        status=IntegrationEvidenceStatus.NOT_RUN,
        started_at=at,
        completed_at=at,
        detail="not run in this stage",
    )


def _item_pass(*, reference: str = "fabric-item-read:dev:verified"):
    return IntegrationEvidenceCheckResult(
        check_id="fabric.item.read",
        kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
        status=IntegrationEvidenceStatus.PASS,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        workspace_id=ITEM_WORKSPACE,
        item_id=ITEM_ID,
        evidence_references=(reference,),
    )


def _pipeline_pass():
    return IntegrationEvidenceCheckResult(
        check_id="fabric.pipeline",
        kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        status=IntegrationEvidenceStatus.PASS,
        started_at=NOW + timedelta(minutes=1),
        completed_at=NOW + timedelta(minutes=1, seconds=2),
        framework_pipeline_run_id=PIPELINE_RUN,
        workspace_id=ITEM_WORKSPACE,
        item_id=PIPELINE_ITEM,
        native_job_instance_id=PIPELINE_JOB,
        root_activity_id=PIPELINE_ROOT,
        evidence_references=("pipeline:dev:verified",),
    )


def _item_fail(*, detail: str = "read failed"):
    return IntegrationEvidenceCheckResult(
        check_id="fabric.item.read",
        kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
        status=IntegrationEvidenceStatus.FAIL,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        detail=detail,
    )


def _manifest(
    spec: IntegrationEvidenceSpec,
    *,
    item=None,
    pipeline=None,
    kafka=None,
    started_at: datetime = NOW,
    completed_at: datetime = NOW + timedelta(minutes=2),
) -> IntegrationEvidenceManifest:
    by_id = {check.check_id: check for check in spec.checks}
    return IntegrationEvidenceManifest(
        evidence_schema_version=spec.evidence_schema_version,
        environment=spec.environment,
        domain=spec.domain,
        framework_version=spec.framework_version,
        release_hash=spec.release_hash,
        started_at=started_at,
        completed_at=completed_at,
        checks=spec.checks,
        results=(
            item or _not_run(by_id["fabric.item.read"]),
            pipeline or _not_run(by_id["fabric.pipeline"]),
            kafka or _not_run(by_id["kafka.optional"]),
        ),
    )


def _result(manifest: IntegrationEvidenceManifest, check_id: str):
    return next(item for item in manifest.results if item.check_id == check_id)


def test_merges_item_and_pipeline_partials_in_spec_order():
    spec = _spec()
    item_partial = _manifest(
        spec,
        item=_item_pass(),
        completed_at=NOW + timedelta(seconds=10),
    )
    pipeline_partial = _manifest(
        spec,
        pipeline=_pipeline_pass(),
        started_at=NOW + timedelta(minutes=1),
        completed_at=NOW + timedelta(minutes=3),
    )

    merged = merge_integration_evidence_manifests(spec, (item_partial, pipeline_partial))

    assert [item.check_id for item in merged.results] == [item.check_id for item in spec.checks]
    assert _result(merged, "fabric.item.read") == _item_pass()
    assert _result(merged, "fabric.pipeline") == _pipeline_pass()
    assert _result(merged, "kafka.optional").status is IntegrationEvidenceStatus.NOT_RUN
    assert merged.started_at == item_partial.started_at
    assert merged.completed_at == pipeline_partial.completed_at
    assert merged.certified is True
    validate_integration_evidence_manifest(spec, merged, require_certified=True)


def test_required_checks_must_all_be_covered_before_merge_certifies():
    spec = _spec()
    merged = merge_integration_evidence_manifests(spec, (_manifest(spec, item=_item_pass()),))

    assert merged.certified is False
    with pytest.raises(ValueError, match="fabric.pipeline"):
        validate_integration_evidence_manifest(spec, merged, require_certified=True)


def test_pass_plus_not_run_resolves_to_pass_and_fail_plus_not_run_resolves_to_fail():
    spec = _spec()
    pass_merged = merge_integration_evidence_manifests(
        spec,
        (_manifest(spec, item=_item_pass()), _manifest(spec)),
    )
    assert _result(pass_merged, "fabric.item.read").status is IntegrationEvidenceStatus.PASS

    fail_merged = merge_integration_evidence_manifests(
        spec,
        (_manifest(spec, item=_item_fail()), _manifest(spec)),
    )
    assert _result(fail_merged, "fabric.item.read").status is IntegrationEvidenceStatus.FAIL


def test_identical_duplicate_substantive_result_is_accepted():
    spec = _spec()
    first = _manifest(spec, item=_item_pass())
    second = _manifest(spec, item=_item_pass())

    merged = merge_integration_evidence_manifests(spec, (first, second))

    assert _result(merged, "fabric.item.read") == _item_pass()


def test_different_pass_evidence_for_same_check_is_conflict():
    spec = _spec()
    first = _manifest(spec, item=_item_pass(reference="fabric-item-read:first"))
    second = _manifest(spec, item=_item_pass(reference="fabric-item-read:second"))

    with pytest.raises(IntegrationEvidenceMergeConflict, match="explicitly choose one rerun"):
        merge_integration_evidence_manifests(spec, (first, second))


def test_pass_vs_fail_and_different_fail_vs_fail_are_conflicts():
    spec = _spec()
    pass_manifest = _manifest(spec, item=_item_pass())
    fail_manifest = _manifest(spec, item=_item_fail())
    with pytest.raises(IntegrationEvidenceMergeConflict, match="fabric.item.read"):
        merge_integration_evidence_manifests(spec, (pass_manifest, fail_manifest))

    first_fail = _manifest(spec, item=_item_fail(detail="first failure"))
    second_fail = _manifest(spec, item=_item_fail(detail="second failure"))
    with pytest.raises(IntegrationEvidenceMergeConflict, match="fabric.item.read"):
        merge_integration_evidence_manifests(spec, (first_fail, second_fail))


def test_all_not_run_becomes_one_canonical_not_run_result():
    spec = _spec()
    first = _manifest(spec, completed_at=NOW + timedelta(minutes=1))
    second = _manifest(spec, completed_at=NOW + timedelta(minutes=4))

    merged = merge_integration_evidence_manifests(spec, (first, second))
    result = _result(merged, "fabric.item.read")

    assert result.status is IntegrationEvidenceStatus.NOT_RUN
    assert result.started_at == second.completed_at
    assert result.completed_at == second.completed_at
    assert result.detail == "check was NOT_RUN in every merged partial manifest"


def test_each_input_must_match_exact_spec_identity_and_check_spec():
    spec = _spec()
    manifest = _manifest(spec)

    for changed in (
        manifest.model_copy(update={"domain": "other"}),
        manifest.model_copy(update={"framework_version": "9.9.9"}),
        manifest.model_copy(update={"release_hash": "b" * 64}),
    ):
        with pytest.raises(ValueError):
            merge_integration_evidence_manifests(spec, (changed,))

    changed_checks = spec.checks[:-1]
    with pytest.raises(ValueError, match="check specification"):
        merge_integration_evidence_manifests(
            spec,
            (manifest.model_copy(update={"checks": changed_checks}),),
        )


def test_merge_requires_at_least_one_input_manifest():
    with pytest.raises(ValueError, match="at least one"):
        merge_integration_evidence_manifests(_spec(), ())
