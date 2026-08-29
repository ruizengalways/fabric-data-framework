"""Concrete evidence builders for approved DEV integration checks.

The functions in this module bridge already-implemented provider/runtime contracts into
``IntegrationEvidenceCheckResult`` without creating a second semantic truth. They
retain only correlation identifiers and caller-supplied durable evidence references.
Credentials and raw provider payloads are deliberately excluded.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .adapters.fabric.adapter import FabricCaptureExecutionResult
from .adapters.fabric.pipeline import FabricPipelineInvocation
from .adapters.fabric.rest import FabricJobInstance, FabricJobStatus, FabricRestClient
from .control_plane_certification import ControlPlaneCertificationReport
from .contracts.execution_plan import ExecutionKind
from .integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceStatus,
)
from .recovery.fabric_warehouse import FabricWarehouseAtomicMutationResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _references(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(values)
    if not result:
        raise ValueError("integration PASS evidence requires retained evidence references")
    return result


def run_fabric_item_read_check(
    *,
    client: FabricRestClient,
    check_id: str,
    workspace_id: UUID,
    item_id: UUID,
    evidence_references: Iterable[str],
    now: Callable[[], datetime] = _utcnow,
) -> IntegrationEvidenceCheckResult:
    """Perform a read-only Fabric Core item authorization smoke check.

    The Core API currently documents ``GET /workspaces/{workspaceId}/items/{itemId}``
    for user, service-principal and managed-identity callers. The response identity is
    verified; HTTP 200 alone is not treated as sufficient evidence.

    ``FabricRestClient._request`` is intentionally reused here so authentication,
    provider errors, timeout behavior and credential handling stay in one HTTP path.
    The helper remains in the same framework package and does not duplicate a client.
    """

    started_at = now()
    payload, _ = client._request(  # package-internal reuse of the existing REST boundary
        "GET",
        f"workspaces/{workspace_id}/items/{item_id}",
        expected_statuses=frozenset({200}),
    )
    completed_at = now()
    if not isinstance(payload, dict):
        raise ValueError("Fabric item read response must be a JSON object")
    observed = payload.get("id")
    if observed is None:
        raise ValueError("Fabric item read response did not include item id")
    try:
        observed_id = UUID(str(observed))
    except ValueError as exc:
        raise ValueError("Fabric item read response contained malformed item id") from exc
    if observed_id != item_id:
        raise ValueError(
            f"Fabric item read returned item {observed_id}, expected {item_id}"
        )
    return IntegrationEvidenceCheckResult(
        check_id=check_id,
        kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
        status=IntegrationEvidenceStatus.PASS,
        started_at=started_at,
        completed_at=completed_at,
        workspace_id=workspace_id,
        item_id=item_id,
        evidence_references=_references(evidence_references),
        detail="read-only Fabric item identity and authorization verified",
    )


def build_fabric_pipeline_check_result(
    *,
    check_id: str,
    invocation: FabricPipelineInvocation,
    job: FabricJobInstance,
    evidence_references: Iterable[str],
) -> IntegrationEvidenceCheckResult:
    """Build retained Pipeline evidence from the exact invocation and native job."""

    if job.status is not FabricJobStatus.COMPLETED:
        raise ValueError("Fabric Pipeline evidence requires provider Completed status")
    if job.item_id != invocation.binding.pipeline_item_id:
        raise ValueError("Fabric Pipeline job item does not match invocation binding")
    if job.root_activity_id is None:
        raise ValueError("Fabric Pipeline PASS evidence requires root_activity_id")
    started_at = job.start_time_utc or _utcnow()
    completed_at = job.end_time_utc or started_at
    return IntegrationEvidenceCheckResult(
        check_id=check_id,
        kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
        status=IntegrationEvidenceStatus.PASS,
        started_at=started_at,
        completed_at=completed_at,
        framework_pipeline_run_id=invocation.pipeline_run_id,
        dataset_run_id=invocation.dataset_run_id,
        workspace_id=invocation.binding.workspace_id,
        item_id=invocation.binding.pipeline_item_id,
        native_job_instance_id=job.job_instance_id,
        root_activity_id=job.root_activity_id,
        evidence_references=_references(evidence_references),
        detail="Fabric Pipeline Completed with retained framework/native correlation",
    )


def _provider_uuid(provider: dict[str, Any], field_name: str) -> UUID:
    value = provider.get(field_name)
    if value in (None, ""):
        raise ValueError(f"Fabric capture native diagnostics missing {field_name}")
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ValueError(
            f"Fabric capture native diagnostics contain malformed {field_name}"
        ) from exc


def build_fabric_capture_check_result(
    *,
    check_id: str,
    result: FabricCaptureExecutionResult,
    evidence_references: Iterable[str],
) -> IntegrationEvidenceCheckResult:
    """Build Copy Job/Spark evidence from one verified adapter execution."""

    evidence = result.native_evidence
    receipt = result.receipt
    if evidence.execution_kind is ExecutionKind.FABRIC_COPY_JOB:
        kind = IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE
    elif evidence.execution_kind is ExecutionKind.SPARK_JOB_DEFINITION:
        kind = IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE
    else:
        raise ValueError(
            "DEV capture evidence builder supports Copy Job and Spark Job Definition only"
        )
    provider = evidence.diagnostics.get("provider")
    if not isinstance(provider, dict):
        raise ValueError("Fabric capture PASS requires provider diagnostics")
    workspace_id = _provider_uuid(provider, "workspace_id")
    item_id = _provider_uuid(provider, "item_id")
    job_instance_id = _provider_uuid(provider, "job_instance_id")
    root_activity_id = _provider_uuid(provider, "root_activity_id")
    if evidence.native_run_id != str(job_instance_id):
        raise ValueError("Fabric capture receipt/native job identity mismatch")
    if receipt.native_run_id != evidence.native_run_id:
        raise ValueError("CaptureReceipt native_run_id does not match native evidence")
    if provider.get("remote_status") != FabricJobStatus.COMPLETED.value:
        raise ValueError("Fabric capture PASS requires remote Completed status")
    return IntegrationEvidenceCheckResult(
        check_id=check_id,
        kind=kind,
        status=IntegrationEvidenceStatus.PASS,
        started_at=evidence.started_at,
        completed_at=evidence.completed_at,
        dataset_run_id=receipt.dataset_run_id,
        workspace_id=workspace_id,
        item_id=item_id,
        native_job_instance_id=job_instance_id,
        root_activity_id=root_activity_id,
        evidence_references=_references(evidence_references),
        detail=(
            f"verified {kind.value} receipt/native correlation; "
            f"rows_read={receipt.rows_read}; rows_written={receipt.rows_written}"
        ),
    )


def build_fabric_warehouse_commit_check_result(
    *,
    check_id: str,
    result: FabricWarehouseAtomicMutationResult,
    evidence_references: Iterable[str] = (),
) -> IntegrationEvidenceCheckResult:
    """Build target commit evidence from the committed same-transaction marker."""

    marker = result.marker
    references = (result.marker_reference, *tuple(evidence_references))
    return IntegrationEvidenceCheckResult(
        check_id=check_id,
        kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
        status=IntegrationEvidenceStatus.PASS,
        started_at=marker.recorded_at,
        completed_at=marker.recorded_at,
        dataset_run_id=marker.owner_dataset_run_id,
        operation_key=marker.operation_key,
        native_operation_id=marker.native_operation_id,
        evidence_references=_references(references),
        detail=(
            "target mutation and framework marker committed atomically; "
            f"executed={str(result.executed).lower()}"
        ),
    )


def build_control_plane_certification_check_result(
    *,
    check_id: str,
    report: ControlPlaneCertificationReport,
    evidence_references: Iterable[str],
    require_production_certified: bool = True,
) -> IntegrationEvidenceCheckResult:
    """Project one retained control-plane certification report into DEV evidence."""

    passed = (
        report.production_certified
        if require_production_certified
        else report.reference_certified
    )
    return IntegrationEvidenceCheckResult(
        check_id=check_id,
        kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
        status=(IntegrationEvidenceStatus.PASS if passed else IntegrationEvidenceStatus.FAIL),
        started_at=report.evaluated_at,
        completed_at=report.evaluated_at,
        evidence_references=(
            _references(evidence_references) if passed else tuple(evidence_references)
        ),
        detail=(
            f"profile={report.profile.profile_name}; dialect={report.observed_dialect}; "
            f"schema_version={report.schema_version}; "
            f"production_certified={str(report.production_certified).lower()}"
        ),
    )


__all__ = [
    "build_control_plane_certification_check_result",
    "build_fabric_capture_check_result",
    "build_fabric_pipeline_check_result",
    "build_fabric_warehouse_commit_check_result",
    "run_fabric_item_read_check",
]
