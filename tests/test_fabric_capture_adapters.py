from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fabric_data_framework.adapters import (
    CopyActivityCaptureAdapter,
    CopyJobCaptureAdapter,
    DataflowGen2CaptureAdapter,
    FabricAdapterExecutionError,
    FabricAdapterRegistry,
    FabricCaptureRequest,
    FabricNativeRunEvidence,
    FabricNativeRunStatus,
    SparkJobCaptureAdapter,
)
from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    ExecutionEngine,
    ExecutionPolicy,
    LoadPolicy,
    OrchestrationPolicy,
    ProgressOwner,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
    resolve_effective_config,
)
from fabric_data_framework.contracts.execution_plan import (
    ExecutionKind,
    ExecutionRole,
    ExecutionUnit,
    compile_execution_plan,
)
from fabric_data_framework.metadata.capabilities import (
    DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
)


def _ts(minute: int) -> datetime:
    return datetime(2026, 8, 28, 13, minute, tzinfo=timezone.utc)


class StubTransport:
    def __init__(self, evidence: FabricNativeRunEvidence) -> None:
        self.evidence = evidence
        self.requests: list[FabricCaptureRequest] = []

    def invoke_capture(self, request: FabricCaptureRequest) -> FabricNativeRunEvidence:
        self.requests.append(request)
        return self.evidence


def _unit(
    kind: ExecutionKind,
    *,
    roles: tuple[ExecutionRole, ...] = (ExecutionRole.EXTRACT, ExecutionRole.STAGE),
) -> ExecutionUnit:
    return ExecutionUnit(unit_id="capture", roles=roles, execution_kind=kind)


def _request(
    *,
    engine: ExecutionEngine = ExecutionEngine.FABRIC_COPY_ACTIVITY,
    kind: ExecutionKind = ExecutionKind.FABRIC_COPY_ACTIVITY,
    strategy: CaptureStrategy = CaptureStrategy.WATERMARK,
    owner: ProgressOwner = ProgressOwner.FRAMEWORK,
    unit: ExecutionUnit | None = None,
    lower=100,
    upper=200,
    snapshot_id: str | None = None,
) -> FabricCaptureRequest:
    return FabricCaptureRequest(
        dataset_run_id=uuid4(),
        dataset_id="erp.order",
        execution_unit=unit or _unit(kind),
        capture_strategy=strategy,
        execution_engine=engine,
        progress_owner=owner,
        source_reference="erp.dbo.Order",
        landing_reference="bronze.erp_order",
        source_lower_bound=lower,
        source_upper_bound=upper,
        snapshot_id=snapshot_id,
    )


def _evidence(
    *,
    kind: ExecutionKind = ExecutionKind.FABRIC_COPY_ACTIVITY,
    status: FabricNativeRunStatus = FabricNativeRunStatus.SUCCEEDED,
    lower=100,
    upper=200,
    landing_reference: str = "bronze.erp_order",
    snapshot_id: str | None = None,
    complete_snapshot: bool | None = None,
) -> FabricNativeRunEvidence:
    return FabricNativeRunEvidence(
        native_run_id="fabric-run-42",
        execution_kind=kind,
        status=status,
        rows_read=12,
        rows_written=12,
        source_reference="erp.dbo.Order",
        landing_reference=landing_reference,
        source_lower_bound=lower,
        source_upper_bound=upper,
        snapshot_id=snapshot_id,
        complete_snapshot=complete_snapshot,
        started_at=_ts(0),
        completed_at=_ts(1),
    )


@pytest.mark.parametrize(
    ("factory", "engine", "kind"),
    [
        (CopyJobCaptureAdapter, ExecutionEngine.FABRIC_COPY_JOB, ExecutionKind.FABRIC_COPY_JOB),
        (
            CopyActivityCaptureAdapter,
            ExecutionEngine.FABRIC_COPY_ACTIVITY,
            ExecutionKind.FABRIC_COPY_ACTIVITY,
        ),
        (DataflowGen2CaptureAdapter, ExecutionEngine.DATAFLOW_GEN2, ExecutionKind.DATAFLOW_GEN2),
        (SparkJobCaptureAdapter, ExecutionEngine.SPARK, ExecutionKind.SPARK_JOB_DEFINITION),
    ],
)
def test_concrete_capture_adapters_bind_one_engine_and_execution_kind(factory, engine, kind):
    transport = StubTransport(_evidence(kind=kind))
    adapter = factory(transport)

    assert adapter.execution_engine is engine
    assert adapter.execution_kind is kind


def test_copy_activity_verified_success_returns_capture_receipt_with_native_correlation():
    request = _request()
    transport = StubTransport(_evidence())
    receipt = CopyActivityCaptureAdapter(transport).execute(request)

    assert transport.requests == [request]
    assert receipt.dataset_run_id == request.dataset_run_id
    assert receipt.dataset_id == "erp.order"
    assert receipt.execution_engine is ExecutionEngine.FABRIC_COPY_ACTIVITY
    assert receipt.progress_owner is ProgressOwner.FRAMEWORK
    assert receipt.native_run_id == "fabric-run-42"
    assert receipt.source_lower_bound == 100
    assert receipt.source_upper_bound == 200
    assert receipt.landing_reference == "bronze.erp_order"
    assert receipt.rows_read == receipt.rows_written == 12


@pytest.mark.parametrize(
    "status",
    [
        FabricNativeRunStatus.FAILED,
        FabricNativeRunStatus.CANCELLED,
        FabricNativeRunStatus.UNKNOWN,
    ],
)
def test_non_success_native_status_never_becomes_capture_receipt(status):
    request = _request()
    evidence = _evidence(status=status)

    with pytest.raises(FabricAdapterExecutionError, match=status.value) as exc_info:
        CopyActivityCaptureAdapter(StubTransport(evidence)).execute(request)

    assert exc_info.value.evidence == evidence


def test_execution_kind_mismatch_fails_even_when_native_status_is_success():
    request = _request()
    evidence = _evidence(kind=ExecutionKind.DATAFLOW_GEN2)

    with pytest.raises(FabricAdapterExecutionError, match="reported execution kind"):
        CopyActivityCaptureAdapter(StubTransport(evidence)).execute(request)


def test_landing_reference_mismatch_fails_closed():
    request = _request()
    evidence = _evidence(landing_reference="bronze.somewhere_else")

    with pytest.raises(FabricAdapterExecutionError, match="landed at"):
        CopyActivityCaptureAdapter(StubTransport(evidence)).execute(request)


def test_framework_owned_bounded_capture_requires_observed_bounds_to_match_request():
    request = _request(lower=100, upper=200)
    evidence = _evidence(lower=100, upper=201)

    with pytest.raises(FabricAdapterExecutionError, match="source_upper_bound"):
        CopyActivityCaptureAdapter(StubTransport(evidence)).execute(request)


def test_capture_adapter_rejects_engine_mismatch_before_transport_invocation():
    request = _request(
        engine=ExecutionEngine.DATAFLOW_GEN2,
        kind=ExecutionKind.DATAFLOW_GEN2,
        owner=ProgressOwner.FABRIC_NATIVE,
        lower=None,
        upper=None,
    )
    transport = StubTransport(_evidence())

    with pytest.raises(ValueError, match="does not match adapter engine"):
        CopyActivityCaptureAdapter(transport).execute(request)

    assert transport.requests == []


def test_capture_adapter_rejects_combined_unit_that_owns_apply_or_state_commit():
    unit = _unit(
        ExecutionKind.SPARK_JOB_DEFINITION,
        roles=(
            ExecutionRole.EXTRACT,
            ExecutionRole.STAGE,
            ExecutionRole.APPLY,
            ExecutionRole.COMMIT_STATE,
        ),
    )
    request = _request(
        engine=ExecutionEngine.SPARK,
        kind=ExecutionKind.SPARK_JOB_DEFINITION,
        owner=ProgressOwner.FRAMEWORK,
        unit=unit,
    )
    transport = StubTransport(_evidence(kind=ExecutionKind.SPARK_JOB_DEFINITION))

    with pytest.raises(ValueError, match="downstream lifecycle roles"):
        SparkJobCaptureAdapter(transport).execute(request)

    assert transport.requests == []


def test_registry_is_explicit_and_rejects_duplicate_or_unknown_engine():
    copy = CopyActivityCaptureAdapter(StubTransport(_evidence()))
    registry = FabricAdapterRegistry((copy,))

    assert registry.supported_engines == frozenset({ExecutionEngine.FABRIC_COPY_ACTIVITY})
    assert registry.resolve(ExecutionEngine.FABRIC_COPY_ACTIVITY) is copy

    with pytest.raises(ValueError, match="already registered"):
        registry.register(CopyActivityCaptureAdapter(StubTransport(_evidence())))
    with pytest.raises(KeyError, match="no Fabric capture adapter registered"):
        registry.resolve(ExecutionEngine.DATAFLOW_GEN2)


def test_complete_full_snapshot_evidence_is_preserved_in_receipt():
    request = _request(
        engine=ExecutionEngine.FABRIC_COPY_JOB,
        kind=ExecutionKind.FABRIC_COPY_JOB,
        strategy=CaptureStrategy.FULL,
        owner=ProgressOwner.FABRIC_NATIVE,
        lower=None,
        upper=None,
        snapshot_id="snapshot-2026-08-28T13:00Z",
    )
    evidence = _evidence(
        kind=ExecutionKind.FABRIC_COPY_JOB,
        lower=None,
        upper=None,
        snapshot_id="snapshot-2026-08-28T13:00Z",
        complete_snapshot=True,
    )

    receipt = CopyJobCaptureAdapter(StubTransport(evidence)).execute(request)

    assert receipt.snapshot_id == "snapshot-2026-08-28T13:00Z"
    assert receipt.complete_snapshot is True


def test_dataflow_native_progress_can_return_receipt_without_framework_watermark():
    request = _request(
        engine=ExecutionEngine.DATAFLOW_GEN2,
        kind=ExecutionKind.DATAFLOW_GEN2,
        owner=ProgressOwner.FABRIC_NATIVE,
        lower=None,
        upper=None,
    )
    evidence = _evidence(
        kind=ExecutionKind.DATAFLOW_GEN2,
        lower=None,
        upper=None,
    )

    receipt = DataflowGen2CaptureAdapter(StubTransport(evidence)).execute(request)

    assert receipt.progress_owner is ProgressOwner.FABRIC_NATIVE
    assert receipt.source_lower_bound is None
    assert receipt.source_upper_bound is None


def test_compiled_dataflow_capture_unit_is_directly_compatible_with_adapter_contract():
    config = DatasetConfig(
        dataset_id="erp.customer",
        source=SourceConfig(system="erp", object="dbo.Customer", connection_ref="erp_sql"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.UPSERT,
            merge_key=("customer_id",),
            watermark=WatermarkConfig(column="modified_at", overlap_window_seconds=60),
            event_time_column="modified_at",
        ),
        orchestration=OrchestrationPolicy(execution_group="erp_current"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
        execution=ExecutionPolicy(
            engine=ExecutionEngine.DATAFLOW_GEN2,
            progress_owner=ProgressOwner.FABRIC_NATIVE,
            capability_profile=DATAFLOW_GEN2_INCREMENTAL_BUCKET_PROFILE,
        ),
    )
    plan = compile_execution_plan(resolve_effective_config(config), run_mode=RunMode.NORMAL)
    capture_unit = plan.units[0]
    request = FabricCaptureRequest(
        dataset_run_id=uuid4(),
        dataset_id=config.dataset_id,
        execution_unit=capture_unit,
        capture_strategy=plan.capture_strategy,
        execution_engine=plan.capture_engine,
        progress_owner=config.execution.progress_owner,
        source_reference="erp.dbo.Customer",
        landing_reference="bronze.erp_customer",
    )
    evidence = FabricNativeRunEvidence(
        native_run_id="dataflow-run-99",
        execution_kind=ExecutionKind.DATAFLOW_GEN2,
        status=FabricNativeRunStatus.SUCCEEDED,
        rows_read=7,
        rows_written=7,
        source_reference="erp.dbo.Customer",
        landing_reference="bronze.erp_customer",
        started_at=_ts(0),
        completed_at=_ts(1),
    )

    receipt = DataflowGen2CaptureAdapter(StubTransport(evidence)).execute(request)

    assert capture_unit.roles == (ExecutionRole.EXTRACT, ExecutionRole.STAGE)
    assert receipt.execution_engine is plan.capture_engine
    assert receipt.native_run_id == "dataflow-run-99"
