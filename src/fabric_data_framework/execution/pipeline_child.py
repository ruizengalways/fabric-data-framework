"""Durable semantic handoff for a reusable Fabric Pipeline child worker.

A parent :class:`FabricPipelineBackend` invokes a real Fabric Data Pipeline with seven
stable correlation parameters.  The remote child must validate those parameters
against the exact deployed DatasetConfig, perform the bounded dataset mutation through
an environment/domain executor, and persist one exact ``DatasetRunAudit`` before the
Fabric job returns ``Completed``.

This module owns that generic HOW contract.  Domain/customer code owns the physical
source/target mutation and returns semantic execution facts only; it cannot author
release-readiness PASS.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from fabric_data_framework.contracts.audit import DatasetRunAudit, MutationCounts, RowAccounting
from fabric_data_framework.contracts.base import FrozenModel
from fabric_data_framework.contracts.dispatch import DatasetDispatchOutcome
from fabric_data_framework.control_plane.repository import ControlPlaneRepository
from fabric_data_framework.contracts.execution_plan import compile_execution_plan
from fabric_data_framework.metadata.config import (
    DatasetConfig,
    DatasetStatus,
    RunMode,
    resolve_effective_config,
)


_TERMINAL_STATUSES = frozenset(
    {
        DatasetStatus.SUCCEEDED,
        DatasetStatus.FAILED,
        DatasetStatus.QUARANTINED,
        DatasetStatus.SKIPPED,
        DatasetStatus.BLOCKED,
        DatasetStatus.CANCELLED,
    }
)


class FabricPipelineChildRequest(FrozenModel):
    """Exact seven-parameter contract passed by :class:`FabricPipelineInvocation`."""

    framework_pipeline_run_id: UUID
    framework_dataset_run_id: UUID
    dataset_id: str = Field(min_length=1, max_length=256)
    run_mode: RunMode
    attempt: int = Field(ge=1)
    effective_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class FabricPipelineChildResult(FrozenModel):
    """Semantic facts returned by the physical child executor before durable audit."""

    status: DatasetStatus
    row_accounting: RowAccounting | None = None
    mutations: MutationCounts = Field(default_factory=MutationCounts)
    error_code: str | None = Field(default=None, max_length=1024)
    error_message: str | None = Field(default=None, max_length=4096)
    retryable: bool | None = None

    @model_validator(mode="after")
    def validate_terminal_result(self) -> "FabricPipelineChildResult":
        if self.status not in _TERMINAL_STATUSES:
            raise ValueError("Fabric Pipeline child result must be terminal")
        if self.status is DatasetStatus.SUCCEEDED:
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("successful Fabric Pipeline child result cannot carry an error")
        return self


FabricPipelineChildExecutor = Callable[
    [FabricPipelineChildRequest, DatasetConfig, ControlPlaneRepository],
    FabricPipelineChildResult,
]


def validate_pipeline_child_request(
    repository: ControlPlaneRepository,
    request: FabricPipelineChildRequest,
) -> DatasetConfig:
    """Bind a remote invocation to exact deployed config and execution-plan identity."""

    config = repository.get_dataset(request.dataset_id)
    effective = resolve_effective_config(config)
    if effective.effective_config_hash != request.effective_config_hash:
        raise ValueError(
            "Fabric Pipeline child effective config hash mismatch: "
            f"observed={effective.effective_config_hash}, expected={request.effective_config_hash}"
        )
    plan = compile_execution_plan(effective, run_mode=request.run_mode)
    if plan.plan_hash != request.execution_plan_hash:
        raise ValueError(
            "Fabric Pipeline child execution plan hash mismatch: "
            f"observed={plan.plan_hash}, expected={request.execution_plan_hash}"
        )
    return config


def execute_pipeline_child(
    *,
    repository: ControlPlaneRepository,
    request: FabricPipelineChildRequest,
    executor: FabricPipelineChildExecutor,
) -> DatasetDispatchOutcome:
    """Execute one remote child request and persist the exact durable Framework outcome.

    The physical executor may mutate only its approved environment/domain fixture and
    may record lower-level Framework evidence (for example reconciliation).  This
    wrapper exclusively owns the terminal ``DatasetRunAudit`` identity required by the
    parent Fabric Pipeline backend.
    """

    config = validate_pipeline_child_request(repository, request)
    result = executor(request, config, repository)
    if not isinstance(result, FabricPipelineChildResult):
        raise TypeError("Fabric Pipeline child executor must return FabricPipelineChildResult")

    repository.record_dataset_run(
        DatasetRunAudit(
            dataset_run_id=request.framework_dataset_run_id,
            pipeline_run_id=request.framework_pipeline_run_id,
            dataset_id=request.dataset_id,
            attempt=request.attempt,
            run_mode=request.run_mode,
            status=result.status,
            effective_config_hash=request.effective_config_hash,
            row_accounting=result.row_accounting,
            mutations=result.mutations,
            error_code=result.error_code,
            error_message=result.error_message,
            retryable=result.retryable,
        )
    )
    outcome = repository.get_dataset_outcome(request.framework_dataset_run_id)
    if outcome is None:
        raise RuntimeError("Fabric Pipeline child durable outcome was not persisted")
    if outcome.dataset_run_id != request.framework_dataset_run_id:
        raise RuntimeError("Fabric Pipeline child durable outcome identity mismatch")
    return outcome


def pipeline_child_request_from_parameters(parameters: dict[str, Any]) -> FabricPipelineChildRequest:
    """Parse the exact external parameter bag without accepting silent aliases."""

    expected = {
        "framework_pipeline_run_id",
        "framework_dataset_run_id",
        "dataset_id",
        "run_mode",
        "attempt",
        "effective_config_hash",
        "execution_plan_hash",
    }
    observed = set(parameters)
    if observed != expected:
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        raise ValueError(
            f"Fabric Pipeline child parameter contract mismatch; missing={missing}; "
            f"unexpected={unexpected}"
        )
    return FabricPipelineChildRequest.model_validate(parameters)


__all__ = [
    "FabricPipelineChildExecutor",
    "FabricPipelineChildRequest",
    "FabricPipelineChildResult",
    "execute_pipeline_child",
    "pipeline_child_request_from_parameters",
    "validate_pipeline_child_request",
]
