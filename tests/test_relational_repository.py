from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select

from fabric_data_framework.adapters.fabric.pipeline import FabricPipelineBinding
from fabric_data_framework.adapters.fabric.rest import FabricJobInstance, FabricJobStatus
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    PipelineStatus,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
    resolve_effective_config,
)
from fabric_data_framework.control_plane.schema import (
    apply_baseline_schema,
    pipeline_run,
    step_run,
)
from fabric_data_framework.deployment.delivery import config_bundle_hash
from fabric_data_framework.execution.backends.fabric_pipeline import FabricPipelineBackend
from fabric_data_framework.contracts.audit import (
    DatasetRunAudit,
    PipelineRunAudit,
    StepRunAudit,
    StepStatus,
)
from fabric_data_framework.control_plane.sqlalchemy_repository import SqlAlchemyControlPlaneRepository


def _config(*, connection_ref="crm-readonly"):
    return DatasetConfig(
        dataset_id="crm.customer",
        source=SourceConfig(
            system="crm",
            object="dbo.Customer",
            connection_ref=connection_ref,
        ),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
    )


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    apply_baseline_schema(engine)
    return engine


def _repo(tmp_path, config=None):
    engine = _engine(tmp_path)
    config = config or _config()
    repository = SqlAlchemyControlPlaneRepository(
        engine,
        domain="customer",
        domain_git_sha="abcdef0",
        framework_version="0.4.0",
    )
    repository.deploy_dataset(config)
    return engine, repository, config


def _pipeline_audit(
    pipeline_run_id,
    config,
    *,
    status=PipelineStatus.RUNNING,
    error_code=None,
    error_message=None,
):
    return PipelineRunAudit(
        pipeline_run_id=pipeline_run_id,
        environment="dev",
        domain="customer",
        status=status,
        run_mode=RunMode.NORMAL,
        domain_git_sha="abcdef0",
        framework_version="0.4.0",
        config_bundle_hash=config_bundle_hash((config,)),
        error_code=error_code,
        error_message=error_message,
    )


def test_runtime_repository_refuses_unmigrated_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")

    with pytest.raises(RuntimeError, match="explicitly migrated schema"):
        SqlAlchemyControlPlaneRepository(
            engine,
            domain="customer",
            domain_git_sha="abcdef0",
            framework_version="0.4.0",
        )


def test_deployed_dataset_is_read_from_released_catalog_with_hash_validation(tmp_path):
    _, repository, config = _repo(tmp_path)

    assert repository.get_dataset("crm.customer") == config
    assert repository.list_datasets() == (config,)
    assert repository.get_dataset("crm.customer").source.connection_ref == "crm-readonly"

    mismatched = SqlAlchemyControlPlaneRepository(
        repository.engine,
        domain="customer",
        domain_git_sha="abcdef0",
        framework_version="0.4.0",
        configs=(_config(connection_ref="different-binding"),),
    )
    with pytest.raises(RuntimeError, match="config hash mismatch"):
        mismatched.get_dataset("crm.customer")


def test_pipeline_dataset_and_step_lifecycle_are_durable_and_updatable(tmp_path):
    engine, repository, config = _repo(tmp_path)
    pipeline_run_id = uuid4()
    dataset_run_id = uuid4()
    repository.record_pipeline_run(_pipeline_audit(pipeline_run_id, config))
    effective = resolve_effective_config(config)
    started = datetime.now(timezone.utc)

    repository.record_dataset_run(
        DatasetRunAudit(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=config.dataset_id,
            run_mode=RunMode.NORMAL,
            status=DatasetStatus.RUNNING,
            effective_config_hash=effective.effective_config_hash,
            started_at=started,
        )
    )
    repository.record_dataset_run(
        DatasetRunAudit(
            dataset_run_id=dataset_run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=config.dataset_id,
            run_mode=RunMode.NORMAL,
            status=DatasetStatus.SUCCEEDED,
            effective_config_hash=effective.effective_config_hash,
            started_at=started,
            completed_at=datetime.now(timezone.utc),
        )
    )
    step_started = datetime.now(timezone.utc)
    step = StepRunAudit(
        dataset_run_id=dataset_run_id,
        step_name="provider_job",
        status=StepStatus.SUCCEEDED,
        started_at=step_started,
        completed_at=datetime.now(timezone.utc),
        details={"native_run_id": "fabric-123"},
    )
    repository.record_step_run(step)

    outcome = repository.get_dataset_outcome(dataset_run_id)
    assert outcome is not None
    assert outcome.status is DatasetStatus.SUCCEEDED
    with engine.connect() as connection:
        row = connection.execute(
            select(step_run).where(step_run.c.step_run_id == str(step.step_run_id))
        ).mappings().one()
    assert row["details"] == {"native_run_id": "fabric-123"}

    repository.record_pipeline_run(
        _pipeline_audit(pipeline_run_id, config, status=PipelineStatus.SUCCESS)
    )
    with engine.connect() as connection:
        pipeline = connection.execute(
            select(pipeline_run).where(pipeline_run.c.pipeline_run_id == str(pipeline_run_id))
        ).mappings().one()
    assert pipeline["status"] == "SUCCESS"
    assert pipeline["error_code"] is None
    assert pipeline["error_message"] is None


def test_pipeline_failure_error_is_durable_and_updated_at_terminal_state(tmp_path):
    engine, repository, config = _repo(tmp_path)
    pipeline_run_id = uuid4()
    repository.record_pipeline_run(_pipeline_audit(pipeline_run_id, config))
    repository.record_pipeline_run(
        _pipeline_audit(
            pipeline_run_id,
            config,
            status=PipelineStatus.FAILED,
            error_code="DATASET_FAILURES_AT_END",
            error_message="crm.customer[FAILED/EXECUTOR_EXCEPTION]: RuntimeError: boom",
        )
    )

    with engine.connect() as connection:
        row = connection.execute(
            select(pipeline_run).where(pipeline_run.c.pipeline_run_id == str(pipeline_run_id))
        ).mappings().one()
    assert row["status"] == "FAILED"
    assert row["error_code"] == "DATASET_FAILURES_AT_END"
    assert "crm.customer" in row["error_message"]
    assert "RuntimeError: boom" in row["error_message"]


def test_dataset_run_semantic_identity_cannot_change(tmp_path):
    _, repository, config = _repo(tmp_path)
    pipeline_run_id = uuid4()
    repository.record_pipeline_run(_pipeline_audit(pipeline_run_id, config))
    run_id = uuid4()
    effective = resolve_effective_config(config)
    repository.record_dataset_run(
        DatasetRunAudit(
            dataset_run_id=run_id,
            pipeline_run_id=pipeline_run_id,
            dataset_id=config.dataset_id,
            run_mode=RunMode.NORMAL,
            status=DatasetStatus.RUNNING,
            effective_config_hash=effective.effective_config_hash,
        )
    )

    with pytest.raises(ValueError, match="semantic identity cannot change"):
        repository.record_dataset_run(
            DatasetRunAudit(
                dataset_run_id=run_id,
                pipeline_run_id=uuid4(),
                dataset_id=config.dataset_id,
                run_mode=RunMode.NORMAL,
                status=DatasetStatus.SUCCEEDED,
                effective_config_hash=effective.effective_config_hash,
            )
        )


def test_fabric_pipeline_child_parent_handoff_uses_relational_outcome_and_step_evidence(tmp_path):
    engine, repository, config = _repo(tmp_path)
    effective = resolve_effective_config(config)
    pipeline_run_id = uuid4()
    repository.record_pipeline_run(_pipeline_audit(pipeline_run_id, config))
    workspace_id = uuid4()
    item_id = uuid4()
    job_id = uuid4()
    root_id = uuid4()

    class ChildTransport:
        def invoke(self, invocation):
            # Simulate the released child runtime durably writing its semantic outcome
            # before the provider reports Completed to the parent.
            child_started = datetime.now(timezone.utc)
            repository.record_dataset_run(
                DatasetRunAudit(
                    dataset_run_id=invocation.dataset_run_id,
                    pipeline_run_id=invocation.pipeline_run_id,
                    dataset_id=invocation.dataset_id,
                    run_mode=invocation.run_mode,
                    status=DatasetStatus.SUCCEEDED,
                    effective_config_hash=invocation.effective_config_hash,
                    started_at=child_started,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            return FabricJobInstance(
                job_instance_id=job_id,
                item_id=item_id,
                job_type="Pipeline",
                status=FabricJobStatus.COMPLETED,
                root_activity_id=root_id,
                start_time_utc=child_started,
                end_time_utc=datetime.now(timezone.utc),
                failure_reason=None,
            )

    backend = FabricPipelineBackend(
        transport=ChildTransport(),
        binding_resolver=lambda _: FabricPipelineBinding(
            workspace_id=workspace_id,
            pipeline_item_id=item_id,
        ),
        outcome_reader=repository.get_dataset_outcome,
    )

    outcome = backend.execute_one(
        repository=repository,
        pipeline_run_id=pipeline_run_id,
        effective=effective,
        run_mode=RunMode.NORMAL,
    )

    assert outcome.status is DatasetStatus.SUCCEEDED
    assert repository.get_dataset_outcome(outcome.dataset_run_id) == outcome
    with engine.connect() as connection:
        native_step = connection.execute(
            select(step_run).where(
                step_run.c.dataset_run_id == str(outcome.dataset_run_id),
                step_run.c.step_name == "fabric_pipeline_remote_job",
            )
        ).mappings().one()
    assert native_step["details"]["job_instance_id"] == str(job_id)
    assert native_step["details"]["root_activity_id"] == str(root_id)
    assert native_step["details"]["workspace_id"] == str(workspace_id)
