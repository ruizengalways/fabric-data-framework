from __future__ import annotations

from uuid import uuid4

import pytest

from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    PipelineStatus,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.contracts.dispatch import DatasetDispatchOutcome
from fabric_data_framework.dispatcher import (
    OrchestrationIntegrityError,
    dispatch_datasets_with_backend,
)
from fabric_data_framework.repository import InMemoryControlPlane


class _Backend:
    def __init__(self, *, omit=False, unexpected=False) -> None:
        self.omit = omit
        self.unexpected = unexpected
        self.waves = []

    def execute_ready_wave(
        self,
        *,
        repository,
        pipeline_run_id,
        effective_by_id,
        dataset_ids,
        run_mode,
        max_concurrency,
    ):
        del repository, pipeline_run_id, effective_by_id, run_mode
        selected = tuple(dataset_ids)
        self.waves.append((selected, max_concurrency))
        result = {
            dataset_id: DatasetDispatchOutcome(
                dataset_run_id=uuid4(),
                status=DatasetStatus.SUCCEEDED,
            )
            for dataset_id in selected
        }
        if self.omit and selected:
            result.pop(selected[0])
        if self.unexpected:
            result["not-selected"] = DatasetDispatchOutcome(
                dataset_run_id=uuid4(),
                status=DatasetStatus.SUCCEEDED,
            )
        return result


def _config(dataset_id, *, dependencies=()):
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(system="crm", object=dataset_id),
        target=TargetConfig(layer="silver", object=dataset_id),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(
            execution_group="daily",
            dependencies=dependencies,
            max_concurrency=3,
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
    )


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


def test_pluggable_backend_uses_framework_dependency_waves():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("source"))
    repository.deploy_dataset(_config("dependent", dependencies=("source",)))
    backend = _Backend()

    result = _dispatch(repository, backend)

    assert result.status is PipelineStatus.SUCCESS
    assert backend.waves == [(('source',), 2), (('dependent',), 2)]
    assert result.outcome_for("source").status is DatasetStatus.SUCCEEDED
    assert result.outcome_for("dependent").status is DatasetStatus.SUCCEEDED


@pytest.mark.parametrize("backend", [_Backend(omit=True), _Backend(unexpected=True)])
def test_backend_must_return_exactly_the_ready_wave(backend):
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("customer"))

    with pytest.raises(OrchestrationIntegrityError, match="invalid ready-wave result"):
        _dispatch(repository, backend)

    assert repository.pipeline_runs[-1].status is PipelineStatus.FAILED
