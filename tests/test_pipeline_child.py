from uuid import uuid4

import pytest

from fabric_data_framework.contracts.audit import MutationCounts, RowAccounting
from fabric_data_framework.contracts.execution_plan import compile_execution_plan
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.execution.pipeline_child import (
    FabricPipelineChildRequest,
    FabricPipelineChildResult,
    execute_pipeline_child,
    pipeline_child_request_from_parameters,
)
from fabric_data_framework.metadata.config import (
    DatasetConfig,
    DatasetStatus,
    RunMode,
    resolve_effective_config,
)


def _config() -> DatasetConfig:
    return DatasetConfig.model_validate(
        {
            "dataset_id": "cert.full_replace",
            "source": {
                "system": "certification",
                "object": "dbo.cert_full_source",
                "connection_ref": "cert_source",
            },
            "target": {"layer": "silver", "object": "cert_full_target"},
            "load": {
                "capture_strategy": "FULL",
                "apply_strategy": "REPLACE",
                "business_key": [],
                "merge_key": [],
                "append_identity": [],
                "tracked_columns": [],
                "delete_policy": "IGNORE",
            },
            "orchestration": {
                "execution_group": "cert_business_path",
                "criticality": "HIGH",
                "dependencies": [],
                "priority": 10,
                "retry_count": 1,
                "timeout_seconds": 1800,
                "batch_size": 1000,
                "max_concurrency": 1,
            },
            "quality": {
                "policy_name": "certification_strict",
                "quarantine_policy": "reject",
            },
            "reconciliation": {
                "policy_name": "certification_exact",
                "required_for_state_commit": True,
            },
            "execution": {
                "engine": "AUTO",
                "progress_owner": "FRAMEWORK",
                "apply_engine": "AUTO",
            },
            "enabled": True,
            "config_schema_version": 1,
        }
    )


def _request(config: DatasetConfig) -> FabricPipelineChildRequest:
    effective = resolve_effective_config(config)
    plan = compile_execution_plan(effective, run_mode=RunMode.NORMAL)
    return FabricPipelineChildRequest(
        framework_pipeline_run_id=uuid4(),
        framework_dataset_run_id=uuid4(),
        dataset_id=config.dataset_id,
        run_mode=RunMode.NORMAL,
        attempt=1,
        effective_config_hash=effective.effective_config_hash,
        execution_plan_hash=plan.plan_hash,
    )


def test_pipeline_child_persists_exact_durable_outcome():
    config = _config()
    repository = InMemoryControlPlane()
    repository.deploy_dataset(config)
    request = _request(config)

    def executor(observed_request, observed_config, observed_repository):
        assert observed_request is request
        assert observed_config == config
        assert observed_repository is repository
        return FabricPipelineChildResult(
            status=DatasetStatus.SUCCEEDED,
            row_accounting=RowAccounting(rows_read=1, rows_accepted=1),
            mutations=MutationCounts(updated=1),
        )

    outcome = execute_pipeline_child(
        repository=repository,
        request=request,
        executor=executor,
    )

    assert outcome.dataset_run_id == request.framework_dataset_run_id
    assert outcome.status is DatasetStatus.SUCCEEDED
    assert len(repository.dataset_runs) == 1
    audit = repository.dataset_runs[0]
    assert audit.pipeline_run_id == request.framework_pipeline_run_id
    assert audit.dataset_id == request.dataset_id
    assert audit.effective_config_hash == request.effective_config_hash
    assert audit.mutations.updated == 1


def test_pipeline_child_fails_closed_on_exact_plan_mismatch():
    config = _config()
    repository = InMemoryControlPlane()
    repository.deploy_dataset(config)
    request = _request(config).model_copy(update={"execution_plan_hash": "0" * 64})

    with pytest.raises(ValueError, match="execution plan hash mismatch"):
        execute_pipeline_child(
            repository=repository,
            request=request,
            executor=lambda *_: FabricPipelineChildResult(status=DatasetStatus.SUCCEEDED),
        )

    assert repository.dataset_runs == []


def test_pipeline_child_parameter_parser_requires_exact_seven_names():
    request = _request(_config())
    values = request.model_dump(mode="json")
    assert pipeline_child_request_from_parameters(values) == request

    with pytest.raises(ValueError, match="unexpected"):
        pipeline_child_request_from_parameters({**values, "database_url": "secret"})
