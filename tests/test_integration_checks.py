from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fabric_data_framework.adapters.fabric.adapter import FabricCaptureExecutionResult
from fabric_data_framework.adapters.fabric.contracts import (
    FabricNativeRunEvidence,
    FabricNativeRunStatus,
)
from fabric_data_framework.adapters.fabric.pipeline import (
    FabricPipelineBinding,
    FabricPipelineInvocation,
)
from fabric_data_framework.adapters.fabric.rest import FabricJobInstance, FabricJobStatus
from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    ExecutionEngine,
    LoadPolicy,
    OrchestrationPolicy,
    ProgressOwner,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)
from fabric_data_framework.contracts.capture_receipt import CaptureReceipt
from fabric_data_framework.contracts.execution_plan import (
    ExecutionKind,
    compile_execution_plan,
)
from fabric_data_framework.control_plane_certification import (
    CertificationCheckStatus,
    ControlPlaneCertificationCheck,
    ControlPlaneCertificationReport,
    FABRIC_SQL_DATABASE_V1,
)
from fabric_data_framework.integration_checks import (
    build_control_plane_certification_check_result,
    build_fabric_capture_check_result,
    build_fabric_pipeline_check_result,
    build_fabric_warehouse_commit_check_result,
    run_fabric_item_read_check,
)
from fabric_data_framework.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceStatus,
)
from fabric_data_framework.recovery.fabric_warehouse import (
    FabricWarehouseAtomicMutationResult,
    FabricWarehouseOperationMarker,
)
from fabric_data_framework.target_operations import (
    TargetOperationIntent,
    fingerprint_semantic_payload,
)


NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


class _ItemClient:
    def __init__(self, item_id):
        self.item_id = item_id
        self.calls = []

    def _request(self, method, path, *, expected_statuses):
        self.calls.append((method, path, expected_statuses))
        return {"id": str(self.item_id), "displayName": "DEV evidence item"}, {}


def test_read_only_item_check_requires_response_identity():
    workspace_id = uuid4()
    item_id = uuid4()
    client = _ItemClient(item_id)

    result = run_fabric_item_read_check(
        client=client,
        check_id="fabric.item.read",
        workspace_id=workspace_id,
        item_id=item_id,
        evidence_references=("dev-evidence:item-read.json",),
        now=lambda: NOW,
    )

    assert result.status is IntegrationEvidenceStatus.PASS
    assert result.workspace_id == workspace_id
    assert result.item_id == item_id
    assert client.calls[0][1] == f"workspaces/{workspace_id}/items/{item_id}"

    wrong = _ItemClient(uuid4())
    with pytest.raises(ValueError, match="expected"):
        run_fabric_item_read_check(
            client=wrong,
            check_id="fabric.item.read",
            workspace_id=workspace_id,
            item_id=item_id,
            evidence_references=("dev-evidence:item-read.json",),
            now=lambda: NOW,
        )


def _effective():
    return resolve_effective_config(
        DatasetConfig(
            dataset_id="crm.customer",
            source=SourceConfig(
                system="crm",
                object="dbo.Customer",
                connection_ref="crm-readonly",
            ),
            target=TargetConfig(layer="silver", object="customer"),
            load=LoadPolicy(
                capture_strategy=CaptureStrategy.FULL,
                apply_strategy=ApplyStrategy.REPLACE,
            ),
            orchestration=OrchestrationPolicy(
                execution_group="daily",
                criticality=Criticality.HIGH,
                timeout_seconds=120,
            ),
            quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
            reconciliation=ReconciliationPolicy(policy_name="count"),
        )
    )


def test_pipeline_builder_requires_completed_job_and_root_correlation():
    effective = _effective()
    binding = FabricPipelineBinding(workspace_id=uuid4(), pipeline_item_id=uuid4())
    invocation = FabricPipelineInvocation(
        pipeline_run_id=uuid4(),
        dataset_run_id=uuid4(),
        dataset_id=effective.config.dataset_id,
        run_mode=RunMode.NORMAL,
        effective_config_hash=effective.effective_config_hash,
        execution_plan=compile_execution_plan(effective, run_mode=RunMode.NORMAL),
        binding=binding,
    )
    root_id = uuid4()
    job = FabricJobInstance(
        job_instance_id=uuid4(),
        item_id=binding.pipeline_item_id,
        job_type="Pipeline",
        status=FabricJobStatus.COMPLETED,
        root_activity_id=root_id,
        start_time_utc=NOW,
        end_time_utc=NOW,
        failure_reason=None,
    )

    result = build_fabric_pipeline_check_result(
        check_id="fabric.pipeline",
        invocation=invocation,
        job=job,
        evidence_references=("control-plane:dataset-run:retained",),
    )
    assert result.framework_pipeline_run_id == invocation.pipeline_run_id
    assert result.dataset_run_id == invocation.dataset_run_id
    assert result.native_job_instance_id == job.job_instance_id
    assert result.root_activity_id == root_id

    with pytest.raises(ValueError, match="root_activity_id"):
        build_fabric_pipeline_check_result(
            check_id="fabric.pipeline",
            invocation=invocation,
            job=job.__class__(
                **{**job.__dict__, "root_activity_id": None}
            ),
            evidence_references=("control-plane:dataset-run:retained",),
        )


def _capture_execution(kind: ExecutionKind):
    dataset_run_id = uuid4()
    workspace_id = uuid4()
    item_id = uuid4()
    job_id = uuid4()
    root_id = uuid4()
    engine = (
        ExecutionEngine.FABRIC_COPY_JOB
        if kind is ExecutionKind.FABRIC_COPY_JOB
        else ExecutionEngine.SPARK
    )
    progress = (
        ProgressOwner.FABRIC_NATIVE
        if kind is ExecutionKind.FABRIC_COPY_JOB
        else ProgressOwner.FRAMEWORK
    )
    receipt = CaptureReceipt(
        dataset_run_id=dataset_run_id,
        dataset_id="crm.customer",
        capture_strategy=CaptureStrategy.WATERMARK,
        execution_engine=engine,
        progress_owner=progress,
        native_run_id=str(job_id),
        source_reference="crm.dbo.Customer",
        landing_reference="bronze.crm_customer",
        rows_read=10,
        rows_written=10,
        started_at=NOW,
        completed_at=NOW,
    )
    native = FabricNativeRunEvidence(
        native_run_id=str(job_id),
        execution_kind=kind,
        status=FabricNativeRunStatus.SUCCEEDED,
        rows_read=10,
        rows_written=10,
        source_reference="crm.dbo.Customer",
        landing_reference="bronze.crm_customer",
        started_at=NOW,
        completed_at=NOW,
        diagnostics={
            "provider": {
                "workspace_id": str(workspace_id),
                "item_id": str(item_id),
                "job_instance_id": str(job_id),
                "root_activity_id": str(root_id),
                "remote_status": "Completed",
            }
        },
    )
    return FabricCaptureExecutionResult(receipt=receipt, native_evidence=native), root_id


@pytest.mark.parametrize(
    ("execution_kind", "expected_kind"),
    [
        (ExecutionKind.FABRIC_COPY_JOB, IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE),
        (ExecutionKind.SPARK_JOB_DEFINITION, IntegrationEvidenceCheckKind.FABRIC_SPARK_CAPTURE),
    ],
)
def test_capture_builder_retains_provider_root_and_receipt_identity(execution_kind, expected_kind):
    execution, root_id = _capture_execution(execution_kind)
    result = build_fabric_capture_check_result(
        check_id="fabric.capture",
        result=execution,
        evidence_references=("control-plane:capture-receipt:retained",),
    )

    assert result.kind is expected_kind
    assert result.dataset_run_id == execution.receipt.dataset_run_id
    assert result.root_activity_id == root_id
    assert str(result.native_job_instance_id) == execution.receipt.native_run_id


def test_warehouse_builder_uses_same_transaction_marker_as_primary_reference():
    intent = TargetOperationIntent(
        dataset_id="crm.customer",
        operation_kind="SCD2",
        target_reference="silver.customer",
        effective_config_hash="a" * 64,
        input_fingerprint=fingerprint_semantic_payload({"receipt": "r1"}),
    )
    marker = FabricWarehouseOperationMarker(
        operation_key=intent.operation_key,
        dataset_id=intent.dataset_id,
        operation_kind=intent.operation_kind,
        target_reference=intent.target_reference,
        effective_config_hash=intent.effective_config_hash,
        input_fingerprint=intent.input_fingerprint,
        semantic_version=intent.semantic_version,
        owner_dataset_run_id=uuid4(),
        attempt=1,
        native_operation_id="distributed-statement-123",
        recorded_at=NOW,
    )
    atomic = FabricWarehouseAtomicMutationResult(
        marker=marker,
        marker_reference=f"fabric-warehouse-marker:dbo.marker:{intent.operation_key}",
        executed=True,
    )

    result = build_fabric_warehouse_commit_check_result(
        check_id="warehouse.commit",
        result=atomic,
    )
    assert result.operation_key == intent.operation_key
    assert result.native_operation_id == "distributed-statement-123"
    assert result.evidence_references == (atomic.marker_reference,)


def test_control_plane_builder_can_gate_production_certification():
    required = (
        "transaction_rollback",
        "target_operation_cas",
        "cdc_checkpoint_cas",
    )
    checks = tuple(
        ControlPlaneCertificationCheck(
            check_id=check_id,
            status=CertificationCheckStatus.PASS,
            detail="ok",
        )
        for check_id in required
    )
    report = ControlPlaneCertificationReport(
        profile=FABRIC_SQL_DATABASE_V1,
        observed_dialect="mssql",
        schema_version=4,
        conformance_requested=True,
        checks=checks,
        evaluated_at=NOW,
    )

    result = build_control_plane_certification_check_result(
        check_id="control.cert",
        report=report,
        evidence_references=("dev-evidence:control-plane-certification.json",),
        require_production_certified=True,
    )
    assert result.status is IntegrationEvidenceStatus.FAIL

    reference = build_control_plane_certification_check_result(
        check_id="control.cert",
        report=report,
        evidence_references=("dev-evidence:control-plane-certification.json",),
        require_production_certified=False,
    )
    assert reference.status is IntegrationEvidenceStatus.PASS
