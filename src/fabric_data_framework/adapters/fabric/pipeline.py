"""Microsoft Fabric Data Pipeline invocation boundary for framework orchestration."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import Field

from ...config import FrozenModel, RunMode
from ...contracts.execution_plan import ExecutionPlan
from .rest import FabricJobInstance, FabricRestClient


class FabricPipelineBinding(FrozenModel):
    """Environment-local physical binding for one reusable child pipeline item."""

    workspace_id: UUID
    pipeline_item_id: UUID
    job_type: str = Field(default="Pipeline", min_length=1)


class FabricPipelineInvocation(FrozenModel):
    pipeline_run_id: UUID
    dataset_run_id: UUID
    dataset_id: str = Field(min_length=1)
    run_mode: RunMode
    attempt: int = Field(default=1, ge=1)
    effective_config_hash: str = Field(min_length=1)
    execution_plan: ExecutionPlan
    binding: FabricPipelineBinding

    @property
    def framework_parameters(self) -> dict[str, object]:
        """Stable correlation payload expected by a thin reusable Fabric child pipeline."""

        return {
            "framework_pipeline_run_id": str(self.pipeline_run_id),
            "framework_dataset_run_id": str(self.dataset_run_id),
            "dataset_id": self.dataset_id,
            "run_mode": self.run_mode.value,
            "attempt": self.attempt,
            "effective_config_hash": self.effective_config_hash,
            "execution_plan_hash": self.execution_plan.plan_hash,
        }


class FabricPipelineTransport(Protocol):
    def invoke(self, invocation: FabricPipelineInvocation) -> FabricJobInstance: ...


class FabricRestPipelineTransport:
    """Invoke and poll a parameterized Fabric child pipeline through the v1 job API."""

    def __init__(
        self,
        client: FabricRestClient,
        *,
        default_poll_seconds: float = 5.0,
    ) -> None:
        if default_poll_seconds < 0:
            raise ValueError("default_poll_seconds must be >= 0")
        self._client = client
        self._default_poll_seconds = default_poll_seconds

    def invoke(self, invocation: FabricPipelineInvocation) -> FabricJobInstance:
        timeout_seconds = float(sum(unit.timeout_seconds for unit in invocation.execution_plan.units))
        return self._client.run_and_wait_item_job(
            workspace_id=invocation.binding.workspace_id,
            item_id=invocation.binding.pipeline_item_id,
            job_type=invocation.binding.job_type,
            parameters=invocation.framework_parameters,
            timeout_seconds=timeout_seconds,
            default_poll_seconds=self._default_poll_seconds,
        )


__all__ = [
    "FabricPipelineBinding",
    "FabricPipelineInvocation",
    "FabricPipelineTransport",
    "FabricRestPipelineTransport",
]
