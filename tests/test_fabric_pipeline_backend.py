from __future__ import annotations

from uuid import uuid4

from fabric_data_framework.adapters.fabric.pipeline import FabricPipelineBinding
from fabric_data_framework.adapters.fabric.rest import FabricJobInstance, FabricJobStatus
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)
from fabric_data_framework.contracts.dispatch import DatasetDispatchOutcome
from fabric_data_framework.execution.backends.fabric_pipeline import FabricPipelineBackend
from fabric_data_framework.control_plane.repository import InMemoryControlPlane


def _effective():
    config = DatasetConfig(
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
            retry_count=2,
            timeout_seconds=120,
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(
            policy_name="count",
            required_for_state_commit=True,
        ),
    )
    return resolve_effective_config(config)


class _Transport:
    def __init__(self, status: FabricJobStatus) -> None:
        self.status = status
        self.invocations = []
        self.job_id = uuid4()
        self.root_id = uuid4()

    def invoke(self, invocation):
        self.invocations.append(invocation)
        return FabricJobInstance(
            job_instance_id=self.job_id,
            item_id=invocation.binding.pipeline_item_id,
            job_type=invocation.binding.job_type,
            status=self.status,
            root_activity_id=self.root_id,
            start_time_utc=None,
            end_time_utc=None,
            failure_reason={"errorCode": "REMOTE"}
            if self.status is FabricJobStatus.FAILED
            else None,
        )


def _binding(_):
    return FabricPipelineBinding(
        workspace_id=uuid4(),
        pipeline_item_id=uuid4(),
    )


def _assert_native_step(repository, transport, *, expected_status):
    assert len(repository.step_runs) == 1
    step = repository.step_runs[0]
    assert step.step_name == "fabric_pipeline_remote_job"
    assert step.status.value == expected_status
    assert step.details is not None
    assert step.details["job_instance_id"] == str(transport.job_id)
    assert step.details["root_activity_id"] == str(transport.root_id)
    assert step.details["remote_status"] == transport.status.value
    assert step.details["execution_plan_hash"]


def test_completed_fabric_job_requires_matching_durable_framework_outcome():
    repository = InMemoryControlPlane()
    effective = _effective()
    repository.deploy_dataset(effective.config)
    transport = _Transport(FabricJobStatus.COMPLETED)

    def outcome_reader(dataset_run_id):
        return DatasetDispatchOutcome(
            dataset_run_id=dataset_run_id,
            status=DatasetStatus.SUCCEEDED,
        )

    backend = FabricPipelineBackend(
        transport=transport,
        binding_resolver=_binding,
        outcome_reader=outcome_reader,
    )
    pipeline_run_id = uuid4()

    outcome = backend.execute_one(
        repository=repository,
        pipeline_run_id=pipeline_run_id,
        effective=effective,
        run_mode=RunMode.NORMAL,
    )

    assert outcome.status is DatasetStatus.SUCCEEDED
    invocation = transport.invocations[0]
    assert invocation.pipeline_run_id == pipeline_run_id
    assert invocation.dataset_id == "crm.customer"
    assert invocation.framework_parameters["framework_dataset_run_id"] == outcome.dataset_run_id
    assert (
        invocation.framework_parameters["execution_plan_hash"]
        == invocation.execution_plan.plan_hash
    )
    assert repository.dataset_runs == []
    _assert_native_step(repository, transport, expected_status="SUCCEEDED")


def test_completed_remote_job_without_framework_outcome_fails_closed():
    repository = InMemoryControlPlane()
    effective = _effective()
    repository.deploy_dataset(effective.config)
    transport = _Transport(FabricJobStatus.COMPLETED)
    backend = FabricPipelineBackend(
        transport=transport,
        binding_resolver=_binding,
        outcome_reader=lambda _: None,
    )

    outcome = backend.execute_one(
        repository=repository,
        pipeline_run_id=uuid4(),
        effective=effective,
        run_mode=RunMode.NORMAL,
    )

    assert outcome.status is DatasetStatus.FAILED
    assert outcome.error_code == "FABRIC_PIPELINE_RESULT_MISSING"
    assert len(repository.dataset_runs) == 1
    assert repository.dataset_runs[0].error_code == "FABRIC_PIPELINE_RESULT_MISSING"
    assert repository.step_runs[0].dataset_run_id == repository.dataset_runs[0].dataset_run_id
    _assert_native_step(repository, transport, expected_status="SUCCEEDED")


def test_failed_fabric_job_records_provider_correlation_and_failure():
    repository = InMemoryControlPlane()
    effective = _effective()
    repository.deploy_dataset(effective.config)
    transport = _Transport(FabricJobStatus.FAILED)
    backend = FabricPipelineBackend(
        transport=transport,
        binding_resolver=_binding,
        outcome_reader=lambda _: None,
    )

    outcome = backend.execute_one(
        repository=repository,
        pipeline_run_id=uuid4(),
        effective=effective,
        run_mode=RunMode.NORMAL,
    )

    assert outcome.status is DatasetStatus.FAILED
    assert outcome.error_code == "FABRIC_PIPELINE_FAILED"
    assert str(transport.job_id) in outcome.error_message
    assert str(transport.root_id) in outcome.error_message
    assert repository.dataset_runs[0].dataset_run_id == repository.step_runs[0].dataset_run_id
    _assert_native_step(repository, transport, expected_status="FAILED")


def test_deduped_fabric_job_is_blocked_not_misreported_as_success():
    repository = InMemoryControlPlane()
    effective = _effective()
    repository.deploy_dataset(effective.config)
    transport = _Transport(FabricJobStatus.DEDUPED)
    backend = FabricPipelineBackend(
        transport=transport,
        binding_resolver=_binding,
        outcome_reader=lambda _: None,
    )

    outcome = backend.execute_one(
        repository=repository,
        pipeline_run_id=uuid4(),
        effective=effective,
        run_mode=RunMode.NORMAL,
    )

    assert outcome.status is DatasetStatus.BLOCKED
    assert outcome.retryable is True
    assert outcome.error_code == "FABRIC_PIPELINE_DEDUPED"
    _assert_native_step(repository, transport, expected_status="SKIPPED")


def test_wave_executes_all_selected_datasets_with_bounded_backend_contract():
    repository = InMemoryControlPlane()
    effective = _effective()
    repository.deploy_dataset(effective.config)
    transport = _Transport(FabricJobStatus.COMPLETED)
    backend = FabricPipelineBackend(
        transport=transport,
        binding_resolver=_binding,
        outcome_reader=lambda dataset_run_id: DatasetDispatchOutcome(
            dataset_run_id=dataset_run_id,
            status=DatasetStatus.SUCCEEDED,
        ),
    )

    outcomes = backend.execute_ready_wave(
        repository=repository,
        pipeline_run_id=uuid4(),
        effective_by_id={"crm.customer": effective},
        dataset_ids=("crm.customer",),
        run_mode=RunMode.NORMAL,
        max_concurrency=2,
    )

    assert outcomes["crm.customer"].status is DatasetStatus.SUCCEEDED
    assert len(transport.invocations) == 1
    assert len(repository.step_runs) == 1
