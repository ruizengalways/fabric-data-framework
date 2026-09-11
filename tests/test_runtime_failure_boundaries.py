from __future__ import annotations

from uuid import uuid4

import pytest

import fabric_data_framework.execution.backends.fabric_pipeline as fabric_backend_module
from fabric_data_framework.adapters.fabric.pipeline import FabricPipelineBinding
from fabric_data_framework.adapters.fabric.rest import FabricJobInstance, FabricJobStatus
from fabric_data_framework.contracts.dispatch import DatasetDispatchOutcome
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.execution.backends.fabric_pipeline import FabricPipelineBackend
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    PipelineStatus,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)
from fabric_data_framework.orchestration.dispatcher import (
    BackendReadyWaveError,
    PipelineFinalizationError,
    dispatch_datasets_with_backend,
)


def _config(dataset_id: str = "crm.customer") -> DatasetConfig:
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(system="crm", object=dataset_id),
        target=TargetConfig(layer="silver", object=dataset_id),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
    )


class _ExplodingBackend:
    def execute_ready_wave(self, **_kwargs):
        raise RuntimeError("backend failed password=backend-secret")


def _dispatch(repository, backend):
    return dispatch_datasets_with_backend(
        repository=repository,
        backend=backend,
        environment="dev",
        domain="customer",
        domain_git_sha="abcdef0",
        framework_version="0.4.0",
        config_bundle_hash="a" * 64,
        max_concurrency=2,
    )


def test_backend_exception_finalizes_running_pipeline_as_failed_and_redacts_message():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config())

    with pytest.raises(BackendReadyWaveError):
        _dispatch(repository, _ExplodingBackend())

    audit = repository.pipeline_runs[-1]
    assert audit.status is PipelineStatus.FAILED
    assert audit.completed_at is not None
    assert audit.error_code == "BACKEND_READY_WAVE_FAILED"
    assert "backend-secret" not in (audit.error_message or "")
    assert "[REDACTED]" in (audit.error_message or "")


class _FinalizationFailingRepository(InMemoryControlPlane):
    def record_pipeline_run(self, audit):
        if audit.status is PipelineStatus.FAILED:
            raise OSError("control plane unavailable")
        return super().record_pipeline_run(audit)


def test_terminal_audit_failure_preserves_primary_and_finalization_errors():
    repository = _FinalizationFailingRepository()
    repository.deploy_dataset(_config())

    with pytest.raises(PipelineFinalizationError) as raised:
        _dispatch(repository, _ExplodingBackend())

    assert isinstance(raised.value.primary_error, BackendReadyWaveError)
    assert isinstance(raised.value.finalization_error, OSError)
    assert repository.pipeline_runs[-1].status is PipelineStatus.RUNNING


class _FailedTransport:
    def __init__(self, reason):
        self.reason = reason

    def invoke(self, invocation):
        return FabricJobInstance(
            job_instance_id=uuid4(),
            item_id=invocation.binding.pipeline_item_id,
            job_type=invocation.binding.job_type,
            status=FabricJobStatus.FAILED,
            root_activity_id=uuid4(),
            start_time_utc=None,
            end_time_utc=None,
            failure_reason=self.reason,
        )


def _binding(_effective):
    return FabricPipelineBinding(workspace_id=uuid4(), pipeline_item_id=uuid4())


def test_nested_fabric_failure_reason_is_redacted_before_audit_persistence():
    repository = InMemoryControlPlane()
    effective = resolve_effective_config(_config())
    repository.deploy_dataset(effective.config)
    secret = "demo-secret-value"
    backend = FabricPipelineBackend(
        transport=_FailedTransport(
            {
                "message": f"password={secret}",
                "nested": [
                    {"authorization": "Bearer abc.def.ghi"},
                    {"token": secret},
                ],
            }
        ),
        binding_resolver=_binding,
        outcome_reader=lambda _run_id: None,
    )

    outcome = backend.execute_one(
        repository=repository,
        pipeline_run_id=uuid4(),
        effective=effective,
        run_mode=RunMode.NORMAL,
    )

    assert outcome.status is DatasetStatus.FAILED
    retained = repr(repository.step_runs[0].details) + (outcome.error_message or "")
    assert secret not in retained
    assert "abc.def.ghi" not in retained
    assert "[REDACTED]" in retained


def test_binding_resolver_exception_becomes_terminal_dataset_failure():
    repository = InMemoryControlPlane()
    effective = resolve_effective_config(_config())
    repository.deploy_dataset(effective.config)

    def bad_binding(_effective):
        raise RuntimeError("connection_string=server;password=secret-binding")

    backend = FabricPipelineBackend(
        transport=_FailedTransport(None),
        binding_resolver=bad_binding,
        outcome_reader=lambda _run_id: None,
    )
    outcome = backend.execute_one(
        repository=repository,
        pipeline_run_id=uuid4(),
        effective=effective,
        run_mode=RunMode.NORMAL,
    )

    assert outcome.status is DatasetStatus.FAILED
    assert outcome.error_code == "FABRIC_PIPELINE_BINDING_ERROR"
    assert "secret-binding" not in (outcome.error_message or "")
    assert repository.dataset_runs[-1].status is DatasetStatus.FAILED


def test_plan_compiler_exception_becomes_terminal_dataset_failure(monkeypatch):
    repository = InMemoryControlPlane()
    effective = resolve_effective_config(_config())
    repository.deploy_dataset(effective.config)

    def explode(*_args, **_kwargs):
        raise ValueError("invalid plan token=plan-secret")

    monkeypatch.setattr(fabric_backend_module, "compile_execution_plan", explode)
    backend = FabricPipelineBackend(
        transport=_FailedTransport(None),
        binding_resolver=_binding,
        outcome_reader=lambda _run_id: None,
    )
    outcome = backend.execute_one(
        repository=repository,
        pipeline_run_id=uuid4(),
        effective=effective,
        run_mode=RunMode.NORMAL,
    )

    assert outcome.status is DatasetStatus.FAILED
    assert outcome.error_code == "FABRIC_PIPELINE_PLAN_ERROR"
    assert "plan-secret" not in (outcome.error_message or "")


def test_ready_wave_future_exception_isolated_from_sibling_dataset():
    repository = InMemoryControlPlane()
    first = resolve_effective_config(_config("crm.first"))
    second = resolve_effective_config(_config("crm.second"))
    repository.deploy_dataset(first.config)
    repository.deploy_dataset(second.config)

    class Backend(FabricPipelineBackend):
        def execute_one(self, *, repository, pipeline_run_id, effective, run_mode):
            if effective.config.dataset_id == "crm.first":
                raise RuntimeError("worker exploded secret=worker-secret")
            return DatasetDispatchOutcome(
                dataset_run_id=uuid4(),
                status=DatasetStatus.SUCCEEDED,
            )

    backend = Backend(
        transport=_FailedTransport(None),
        binding_resolver=_binding,
        outcome_reader=lambda _run_id: None,
    )
    outcomes = backend.execute_ready_wave(
        repository=repository,
        pipeline_run_id=uuid4(),
        effective_by_id={
            "crm.first": first,
            "crm.second": second,
        },
        dataset_ids=("crm.first", "crm.second"),
        run_mode=RunMode.NORMAL,
        max_concurrency=2,
    )

    assert outcomes["crm.first"].status is DatasetStatus.FAILED
    assert outcomes["crm.first"].error_code == "FABRIC_PIPELINE_WORKER_EXCEPTION"
    assert "worker-secret" not in (outcomes["crm.first"].error_message or "")
    assert outcomes["crm.second"].status is DatasetStatus.SUCCEEDED
