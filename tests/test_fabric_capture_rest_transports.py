from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest

from fabric_data_framework.adapters import (
    CopyJobCaptureAdapter,
    FabricAdapterExecutionError,
    FabricCaptureObservation,
    FabricCaptureRequest,
    FabricCopyJobBinding,
    FabricCopyJobCaptureTransport,
    FabricSparkJobDefinitionBinding,
    FabricSparkJobDefinitionCaptureTransport,
    SparkJobCaptureAdapter,
)
from fabric_data_framework.adapters.fabric.rest import (
    FabricJobInstance,
    FabricJobStatus,
    FabricRestClient,
)
from fabric_data_framework.config import (
    CaptureStrategy,
    ExecutionEngine,
    ProgressOwner,
)
from fabric_data_framework.contracts.execution_plan import (
    ExecutionKind,
    ExecutionRole,
    ExecutionUnit,
)


def _ts(minute: int) -> datetime:
    return datetime(2026, 8, 29, 10, minute, tzinfo=timezone.utc)


class _Response:
    def __init__(self, status: int, *, headers=None, payload=None) -> None:
        self.status = status
        self.headers = headers or {}
        self._raw = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def getcode(self):
        return self.status

    def read(self):
        return self._raw


class _QueueOpener:
    def __init__(self, responses) -> None:
        self.responses = deque(responses)
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append((request, timeout))
        return self.responses.popleft()


def _job_payload(*, job_id, item_id, root_id, status, job_type):
    return {
        "id": str(job_id),
        "itemId": str(item_id),
        "jobType": job_type,
        "invokeType": "Manual",
        "status": status,
        "rootActivityId": str(root_id),
        "startTimeUtc": "2026-08-29T10:00:00Z",
        "endTimeUtc": "2026-08-29T10:01:00Z" if status != "InProgress" else None,
        "failureReason": None,
    }


def test_copy_job_rest_uses_documented_execute_start_and_copyjob_instance_path():
    workspace_id = uuid4()
    copy_job_id = uuid4()
    job_id = uuid4()
    root_id = uuid4()
    location = (
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/"
        f"{copy_job_id}/jobs/instances/{job_id}"
    )
    opener = _QueueOpener(
        [
            _Response(202, headers={"Location": location, "Retry-After": "0"}),
            _Response(
                200,
                payload=_job_payload(
                    job_id=job_id,
                    item_id=copy_job_id,
                    root_id=root_id,
                    status="Completed",
                    job_type="CopyJob",
                ),
            ),
        ]
    )
    client = FabricRestClient(
        token_provider=lambda: "token",
        opener=opener,
        sleeper=lambda _: None,
        clock=lambda: 0.0,
    )

    result = client.run_and_wait_copy_job(
        workspace_id=workspace_id,
        copy_job_id=copy_job_id,
        timeout_seconds=30,
        default_poll_seconds=0,
    )

    assert result.status is FabricJobStatus.COMPLETED
    start_request = opener.requests[0][0]
    status_request = opener.requests[1][0]
    assert start_request.get_method() == "POST"
    assert start_request.data is None
    assert start_request.full_url.endswith(
        f"/workspaces/{workspace_id}/items/{copy_job_id}/jobs/instances?jobType=Execute"
    )
    assert status_request.full_url.endswith(
        f"/workspaces/{workspace_id}/copyJobs/{copy_job_id}/jobs/instances/{job_id}"
    )


def test_spark_job_definition_rest_uses_dedicated_endpoint_and_execution_data():
    workspace_id = uuid4()
    spark_job_id = uuid4()
    job_id = uuid4()
    root_id = uuid4()
    location = (
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/"
        f"{spark_job_id}/jobs/instances/{job_id}"
    )
    opener = _QueueOpener(
        [
            _Response(202, headers={"Location": location, "Retry-After": "0"}),
            _Response(
                200,
                payload=_job_payload(
                    job_id=job_id,
                    item_id=spark_job_id,
                    root_id=root_id,
                    status="Completed",
                    job_type="SparkJobDefinition",
                ),
            ),
        ]
    )
    client = FabricRestClient(
        token_provider=lambda: "token",
        opener=opener,
        sleeper=lambda _: None,
        clock=lambda: 0.0,
    )
    execution_data = {
        "commandLineArguments": "--lower 100 --upper 200",
        "mainClass": "",
    }

    result = client.run_and_wait_spark_job_definition(
        workspace_id=workspace_id,
        spark_job_definition_id=spark_job_id,
        execution_data=execution_data,
        timeout_seconds=30,
        default_poll_seconds=0,
    )

    assert result.status is FabricJobStatus.COMPLETED
    start_request = opener.requests[0][0]
    status_request = opener.requests[1][0]
    assert start_request.full_url.endswith(
        f"/workspaces/{workspace_id}/sparkJobDefinitions/{spark_job_id}/jobs/sparkjob/instances"
    )
    assert json.loads(start_request.data.decode("utf-8")) == {
        "executionData": execution_data
    }
    assert status_request.full_url.endswith(
        f"/workspaces/{workspace_id}/items/{spark_job_id}/jobs/instances/{job_id}"
    )


def _unit(kind: ExecutionKind) -> ExecutionUnit:
    return ExecutionUnit(
        unit_id="capture",
        roles=(ExecutionRole.EXTRACT, ExecutionRole.STAGE),
        execution_kind=kind,
    )


def _copy_request(**updates) -> FabricCaptureRequest:
    values = {
        "dataset_run_id": uuid4(),
        "dataset_id": "erp.customer",
        "execution_unit": _unit(ExecutionKind.FABRIC_COPY_JOB),
        "capture_strategy": CaptureStrategy.WATERMARK,
        "execution_engine": ExecutionEngine.FABRIC_COPY_JOB,
        "progress_owner": ProgressOwner.FABRIC_NATIVE,
        "source_reference": "erp.dbo.Customer",
        "landing_reference": "bronze.erp_customer",
    }
    values.update(updates)
    return FabricCaptureRequest(**values)


def _spark_request(**updates) -> FabricCaptureRequest:
    values = {
        "dataset_run_id": uuid4(),
        "dataset_id": "erp.customer",
        "execution_unit": _unit(ExecutionKind.SPARK_JOB_DEFINITION),
        "capture_strategy": CaptureStrategy.WATERMARK,
        "execution_engine": ExecutionEngine.SPARK,
        "progress_owner": ProgressOwner.FRAMEWORK,
        "source_reference": "erp.dbo.Customer",
        "landing_reference": "bronze.erp_customer",
        "source_lower_bound": 100,
        "source_upper_bound": 200,
    }
    values.update(updates)
    return FabricCaptureRequest(**values)


def _job(*, item_id, status=FabricJobStatus.COMPLETED) -> FabricJobInstance:
    return FabricJobInstance(
        job_instance_id=uuid4(),
        item_id=item_id,
        job_type="CopyJob" if status is not None else "Unknown",
        status=status,
        root_activity_id=uuid4(),
        start_time_utc=_ts(0),
        end_time_utc=_ts(1),
        failure_reason=None if status is FabricJobStatus.COMPLETED else {"message": "failed"},
    )


class _StubClient:
    def __init__(self, job: FabricJobInstance) -> None:
        self.job = job
        self.copy_calls = []
        self.spark_calls = []

    def run_and_wait_copy_job(self, **kwargs):
        self.copy_calls.append(kwargs)
        return self.job

    def run_and_wait_spark_job_definition(self, **kwargs):
        self.spark_calls.append(kwargs)
        return self.job


def test_copy_job_completed_requires_observation_then_becomes_capture_receipt():
    request = _copy_request()
    binding = FabricCopyJobBinding(workspace_id=uuid4(), copy_job_id=uuid4())
    client = _StubClient(_job(item_id=binding.copy_job_id))

    transport = FabricCopyJobCaptureTransport(
        client=client,
        binding_resolver=lambda _: binding,
        observation_resolver=lambda _, __: FabricCaptureObservation(
            rows_read=12,
            rows_written=12,
            source_reference="erp.dbo.Customer",
            landing_reference="bronze.erp_customer",
            external_checkpoint_reference="copyjob-native-progress:run-42",
            diagnostics={"observer": "copyjob-output-manifest"},
        ),
    )
    receipt = CopyJobCaptureAdapter(transport).execute(request)

    assert receipt.native_run_id == str(client.job.job_instance_id)
    assert receipt.progress_owner is ProgressOwner.FABRIC_NATIVE
    assert receipt.external_checkpoint_reference == "copyjob-native-progress:run-42"
    assert receipt.rows_read == receipt.rows_written == 12
    assert client.copy_calls[0]["copy_job_id"] == binding.copy_job_id


def test_copy_job_failed_remote_status_never_calls_success_observer_or_returns_receipt():
    request = _copy_request()
    binding = FabricCopyJobBinding(workspace_id=uuid4(), copy_job_id=uuid4())
    client = _StubClient(_job(item_id=binding.copy_job_id, status=FabricJobStatus.FAILED))
    observed = []
    transport = FabricCopyJobCaptureTransport(
        client=client,
        binding_resolver=lambda _: binding,
        observation_resolver=lambda capture_request, job: observed.append((capture_request, job)),
    )

    with pytest.raises(FabricAdapterExecutionError, match="FAILED"):
        CopyJobCaptureAdapter(transport).execute(request)

    assert observed == []


@pytest.mark.parametrize(
    "capture_request",
    [
        _copy_request(progress_owner=ProgressOwner.FRAMEWORK),
        _copy_request(source_lower_bound=100),
        _copy_request(parameters={"lower": 100}),
    ],
)
def test_copy_job_rejects_framework_owned_runtime_progress_inputs(capture_request):
    binding = FabricCopyJobBinding(workspace_id=uuid4(), copy_job_id=uuid4())
    client = _StubClient(_job(item_id=binding.copy_job_id))
    transport = FabricCopyJobCaptureTransport(
        client=client,
        binding_resolver=lambda _: binding,
        observation_resolver=lambda _, __: FabricCaptureObservation(
            rows_read=1,
            rows_written=1,
            landing_reference="bronze.erp_customer",
        ),
    )

    with pytest.raises(ValueError):
        transport.invoke_capture(capture_request)

    assert client.copy_calls == []


def test_spark_bounded_capture_requires_execution_data_resolver():
    request = _spark_request()
    binding = FabricSparkJobDefinitionBinding(
        workspace_id=uuid4(), spark_job_definition_id=uuid4()
    )
    client = _StubClient(_job(item_id=binding.spark_job_definition_id))
    transport = FabricSparkJobDefinitionCaptureTransport(
        client=client,
        binding_resolver=lambda _: binding,
        observation_resolver=lambda _, __: FabricCaptureObservation(
            rows_read=1,
            rows_written=1,
            landing_reference="bronze.erp_customer",
            source_lower_bound=100,
            source_upper_bound=200,
        ),
    )

    with pytest.raises(ValueError, match="execution_data_resolver"):
        transport.invoke_capture(request)

    assert client.spark_calls == []


def test_spark_bounded_capture_passes_execution_data_and_observed_bounds_to_receipt():
    request = _spark_request(parameters={"mode": "capture"})
    binding = FabricSparkJobDefinitionBinding(
        workspace_id=uuid4(), spark_job_definition_id=uuid4()
    )
    client = _StubClient(_job(item_id=binding.spark_job_definition_id))
    resolver_calls = []

    def execution_data_resolver(observed_request, observed_binding):
        resolver_calls.append((observed_request, observed_binding))
        return {"commandLineArguments": "--lower 100 --upper 200 --mode capture"}

    transport = FabricSparkJobDefinitionCaptureTransport(
        client=client,
        binding_resolver=lambda _: binding,
        execution_data_resolver=execution_data_resolver,
        observation_resolver=lambda _, __: FabricCaptureObservation(
            rows_read=9,
            rows_written=9,
            source_reference="erp.dbo.Customer",
            landing_reference="bronze.erp_customer",
            source_lower_bound=100,
            source_upper_bound=200,
            diagnostics={"manifest": "abfss://.../manifest.json"},
        ),
    )
    receipt = SparkJobCaptureAdapter(transport).execute(request)

    assert receipt.source_lower_bound == 100
    assert receipt.source_upper_bound == 200
    assert receipt.rows_written == 9
    assert resolver_calls == [(request, binding)]
    assert client.spark_calls[0]["execution_data"] == {
        "commandLineArguments": "--lower 100 --upper 200 --mode capture"
    }


def test_spark_observation_with_wrong_bound_fails_closed_in_capture_adapter():
    request = _spark_request()
    binding = FabricSparkJobDefinitionBinding(
        workspace_id=uuid4(), spark_job_definition_id=uuid4()
    )
    client = _StubClient(_job(item_id=binding.spark_job_definition_id))
    transport = FabricSparkJobDefinitionCaptureTransport(
        client=client,
        binding_resolver=lambda _: binding,
        execution_data_resolver=lambda *_: {"commandLineArguments": "--bounded"},
        observation_resolver=lambda _, __: FabricCaptureObservation(
            rows_read=9,
            rows_written=9,
            landing_reference="bronze.erp_customer",
            source_lower_bound=100,
            source_upper_bound=201,
        ),
    )

    with pytest.raises(FabricAdapterExecutionError, match="source_upper_bound"):
        SparkJobCaptureAdapter(transport).execute(request)


def test_transport_native_diagnostics_retain_job_and_root_correlation():
    request = _copy_request()
    binding = FabricCopyJobBinding(workspace_id=uuid4(), copy_job_id=uuid4())
    job = _job(item_id=binding.copy_job_id)
    client = _StubClient(job)
    transport = FabricCopyJobCaptureTransport(
        client=client,
        binding_resolver=lambda _: binding,
        observation_resolver=lambda _, __: FabricCaptureObservation(
            rows_read=1,
            rows_written=1,
            landing_reference="bronze.erp_customer",
        ),
    )

    evidence = transport.invoke_capture(request)

    provider = evidence.diagnostics["provider"]
    assert provider["workspace_id"] == str(binding.workspace_id)
    assert provider["item_id"] == str(binding.copy_job_id)
    assert provider["job_instance_id"] == str(job.job_instance_id)
    assert provider["root_activity_id"] == str(job.root_activity_id)
    assert provider["remote_status"] == "Completed"
