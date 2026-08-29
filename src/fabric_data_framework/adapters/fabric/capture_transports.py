"""Concrete Microsoft Fabric REST capture transports.

These transports own provider invocation mechanics and native job correlation. They do
not invent semantic capture evidence that the Fabric job-instance API does not expose.
A successful remote job therefore requires an injected post-run observation resolver
before a ``FabricNativeRunEvidence`` can be returned to ``FabricCaptureAdapter``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from ...config import ExecutionEngine, FrozenModel, ProgressOwner
from ...contracts.execution_plan import ExecutionKind
from .contracts import (
    FabricCaptureRequest,
    FabricNativeRunEvidence,
    FabricNativeRunStatus,
)
from .rest import FabricJobInstance, FabricJobStatus, FabricRestClient


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FabricCopyJobBinding(FrozenModel):
    """Environment-local binding for one preconfigured Fabric Copy Job item."""

    workspace_id: UUID
    copy_job_id: UUID
    timeout_seconds: float = Field(default=3600.0, gt=0)
    default_poll_seconds: float = Field(default=5.0, ge=0)


class FabricSparkJobDefinitionBinding(FrozenModel):
    """Environment-local binding for one Fabric Spark Job Definition item."""

    workspace_id: UUID
    spark_job_definition_id: UUID
    timeout_seconds: float = Field(default=3600.0, gt=0)
    default_poll_seconds: float = Field(default=5.0, ge=0)


class FabricCaptureObservation(FrozenModel):
    """Post-run facts required to turn provider completion into capture evidence.

    Fabric job-instance status provides job identity/status/timestamps, but not generic
    row counts, actual landing identity, framework source bounds or native incremental
    checkpoint details. A provider/item-specific observer must supply those facts.
    """

    rows_read: int = Field(ge=0)
    rows_written: int = Field(ge=0)
    landing_reference: str = Field(min_length=1)
    source_reference: str | None = None
    source_lower_bound: Any | None = None
    source_upper_bound: Any | None = None
    snapshot_id: str | None = None
    complete_snapshot: bool | None = None
    external_checkpoint_reference: str | None = None
    schema_version: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_counts(self) -> "FabricCaptureObservation":
        if self.rows_written > self.rows_read:
            raise ValueError("rows_written cannot exceed rows_read")
        return self


FabricCopyJobBindingResolver = Callable[[FabricCaptureRequest], FabricCopyJobBinding]
FabricSparkJobDefinitionBindingResolver = Callable[
    [FabricCaptureRequest], FabricSparkJobDefinitionBinding
]
FabricCaptureObservationResolver = Callable[
    [FabricCaptureRequest, FabricJobInstance], FabricCaptureObservation
]
FabricSparkExecutionDataResolver = Callable[
    [FabricCaptureRequest, FabricSparkJobDefinitionBinding], Mapping[str, object] | None
]


_STATUS_MAP = {
    FabricJobStatus.COMPLETED: FabricNativeRunStatus.SUCCEEDED,
    FabricJobStatus.FAILED: FabricNativeRunStatus.FAILED,
    FabricJobStatus.CANCELLED: FabricNativeRunStatus.CANCELLED,
    FabricJobStatus.DEDUPED: FabricNativeRunStatus.UNKNOWN,
}


def _provider_times(
    job: FabricJobInstance,
    *,
    invoked_at: datetime,
    observed_at: datetime,
) -> tuple[datetime, datetime]:
    started_at = job.start_time_utc or invoked_at
    completed_at = job.end_time_utc or observed_at
    if completed_at < started_at:
        completed_at = started_at
    return started_at, completed_at


def _provider_diagnostics(
    *,
    workspace_id: UUID,
    item_id: UUID,
    job: FabricJobInstance,
) -> dict[str, Any]:
    return {
        "workspace_id": str(workspace_id),
        "item_id": str(item_id),
        "job_instance_id": str(job.job_instance_id),
        "root_activity_id": str(job.root_activity_id) if job.root_activity_id else None,
        "job_type": job.job_type,
        "remote_status": job.status.value,
        "failure_reason": job.failure_reason,
        "provider_start_time_present": job.start_time_utc is not None,
        "provider_end_time_present": job.end_time_utc is not None,
    }


def _failure_evidence(
    request: FabricCaptureRequest,
    *,
    workspace_id: UUID,
    item_id: UUID,
    execution_kind: ExecutionKind,
    job: FabricJobInstance,
    invoked_at: datetime,
    observed_at: datetime,
) -> FabricNativeRunEvidence:
    started_at, completed_at = _provider_times(
        job,
        invoked_at=invoked_at,
        observed_at=observed_at,
    )
    return FabricNativeRunEvidence(
        native_run_id=str(job.job_instance_id),
        execution_kind=execution_kind,
        status=_STATUS_MAP.get(job.status, FabricNativeRunStatus.UNKNOWN),
        rows_read=0,
        rows_written=0,
        source_reference=request.source_reference,
        landing_reference=request.landing_reference,
        started_at=started_at,
        completed_at=completed_at,
        diagnostics={
            "provider": _provider_diagnostics(
                workspace_id=workspace_id,
                item_id=item_id,
                job=job,
            ),
            "observation": None,
        },
    )


def _success_evidence(
    request: FabricCaptureRequest,
    *,
    workspace_id: UUID,
    item_id: UUID,
    execution_kind: ExecutionKind,
    job: FabricJobInstance,
    observation: FabricCaptureObservation,
    invoked_at: datetime,
    observed_at: datetime,
) -> FabricNativeRunEvidence:
    started_at, completed_at = _provider_times(
        job,
        invoked_at=invoked_at,
        observed_at=observed_at,
    )
    return FabricNativeRunEvidence(
        native_run_id=str(job.job_instance_id),
        execution_kind=execution_kind,
        status=FabricNativeRunStatus.SUCCEEDED,
        rows_read=observation.rows_read,
        rows_written=observation.rows_written,
        source_reference=observation.source_reference or request.source_reference,
        landing_reference=observation.landing_reference,
        source_lower_bound=observation.source_lower_bound,
        source_upper_bound=observation.source_upper_bound,
        snapshot_id=observation.snapshot_id,
        complete_snapshot=observation.complete_snapshot,
        external_checkpoint_reference=observation.external_checkpoint_reference,
        schema_version=observation.schema_version,
        started_at=started_at,
        completed_at=completed_at,
        diagnostics={
            "provider": _provider_diagnostics(
                workspace_id=workspace_id,
                item_id=item_id,
                job=job,
            ),
            "observation": dict(observation.diagnostics),
        },
    )


class FabricCopyJobCaptureTransport:
    """Run a preconfigured Copy Job while preserving Fabric-native progress ownership."""

    def __init__(
        self,
        *,
        client: FabricRestClient,
        binding_resolver: FabricCopyJobBindingResolver,
        observation_resolver: FabricCaptureObservationResolver,
    ) -> None:
        self._client = client
        self._binding_resolver = binding_resolver
        self._observation_resolver = observation_resolver

    def invoke_capture(self, request: FabricCaptureRequest) -> FabricNativeRunEvidence:
        if request.execution_engine is not ExecutionEngine.FABRIC_COPY_JOB:
            raise ValueError("Copy Job transport requires FABRIC_COPY_JOB execution engine")
        if request.execution_unit.execution_kind is not ExecutionKind.FABRIC_COPY_JOB:
            raise ValueError("Copy Job transport requires FABRIC_COPY_JOB execution kind")
        if request.progress_owner is not ProgressOwner.FABRIC_NATIVE:
            raise ValueError("Copy Job transport requires FABRIC_NATIVE progress ownership")
        if request.source_lower_bound is not None or request.source_upper_bound is not None:
            raise ValueError(
                "Copy Job native progress cannot accept framework-supplied source bounds"
            )
        if request.parameters:
            raise ValueError(
                "Copy Job capture transport does not support per-run framework parameters"
            )

        binding = self._binding_resolver(request)
        invoked_at = _utcnow()
        job = self._client.run_and_wait_copy_job(
            workspace_id=binding.workspace_id,
            copy_job_id=binding.copy_job_id,
            timeout_seconds=binding.timeout_seconds,
            default_poll_seconds=binding.default_poll_seconds,
        )
        observed_at = _utcnow()
        if job.status is not FabricJobStatus.COMPLETED:
            return _failure_evidence(
                request,
                workspace_id=binding.workspace_id,
                item_id=binding.copy_job_id,
                execution_kind=ExecutionKind.FABRIC_COPY_JOB,
                job=job,
                invoked_at=invoked_at,
                observed_at=observed_at,
            )

        observation = self._observation_resolver(request, job)
        return _success_evidence(
            request,
            workspace_id=binding.workspace_id,
            item_id=binding.copy_job_id,
            execution_kind=ExecutionKind.FABRIC_COPY_JOB,
            job=job,
            observation=observation,
            invoked_at=invoked_at,
            observed_at=observed_at,
        )


class FabricSparkJobDefinitionCaptureTransport:
    """Run framework-bounded capture through a Spark Job Definition item."""

    def __init__(
        self,
        *,
        client: FabricRestClient,
        binding_resolver: FabricSparkJobDefinitionBindingResolver,
        observation_resolver: FabricCaptureObservationResolver,
        execution_data_resolver: FabricSparkExecutionDataResolver | None = None,
    ) -> None:
        self._client = client
        self._binding_resolver = binding_resolver
        self._observation_resolver = observation_resolver
        self._execution_data_resolver = execution_data_resolver

    def invoke_capture(self, request: FabricCaptureRequest) -> FabricNativeRunEvidence:
        if request.execution_engine is not ExecutionEngine.SPARK:
            raise ValueError("Spark Job Definition transport requires SPARK execution engine")
        if request.execution_unit.execution_kind is not ExecutionKind.SPARK_JOB_DEFINITION:
            raise ValueError(
                "Spark Job Definition transport requires SPARK_JOB_DEFINITION execution kind"
            )
        if request.progress_owner is not ProgressOwner.FRAMEWORK:
            raise ValueError(
                "Spark Job Definition capture transport requires FRAMEWORK progress ownership"
            )

        binding = self._binding_resolver(request)
        needs_runtime_data = (
            request.source_lower_bound is not None
            or request.source_upper_bound is not None
            or bool(request.parameters)
        )
        if needs_runtime_data and self._execution_data_resolver is None:
            raise ValueError(
                "framework-bounded Spark capture requires an execution_data_resolver"
            )
        execution_data = (
            self._execution_data_resolver(request, binding)
            if self._execution_data_resolver is not None
            else None
        )
        if needs_runtime_data and not execution_data:
            raise ValueError(
                "framework-bounded Spark capture resolver returned no executionData"
            )

        invoked_at = _utcnow()
        job = self._client.run_and_wait_spark_job_definition(
            workspace_id=binding.workspace_id,
            spark_job_definition_id=binding.spark_job_definition_id,
            execution_data=execution_data,
            timeout_seconds=binding.timeout_seconds,
            default_poll_seconds=binding.default_poll_seconds,
        )
        observed_at = _utcnow()
        if job.status is not FabricJobStatus.COMPLETED:
            return _failure_evidence(
                request,
                workspace_id=binding.workspace_id,
                item_id=binding.spark_job_definition_id,
                execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
                job=job,
                invoked_at=invoked_at,
                observed_at=observed_at,
            )

        observation = self._observation_resolver(request, job)
        return _success_evidence(
            request,
            workspace_id=binding.workspace_id,
            item_id=binding.spark_job_definition_id,
            execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
            job=job,
            observation=observation,
            invoked_at=invoked_at,
            observed_at=observed_at,
        )


__all__ = [
    "FabricCaptureObservation",
    "FabricCaptureObservationResolver",
    "FabricCopyJobBinding",
    "FabricCopyJobBindingResolver",
    "FabricCopyJobCaptureTransport",
    "FabricSparkExecutionDataResolver",
    "FabricSparkJobDefinitionBinding",
    "FabricSparkJobDefinitionBindingResolver",
    "FabricSparkJobDefinitionCaptureTransport",
]
