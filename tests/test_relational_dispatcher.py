from __future__ import annotations

from sqlalchemy import create_engine, select

from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.contracts.dispatch import DatasetDispatchOutcome
from fabric_data_framework.control_plane import apply_baseline_schema, pipeline_run
from fabric_data_framework.delivery import config_bundle_hash
from fabric_data_framework.dispatcher import dispatch_datasets_with_backend
from fabric_data_framework.relational_repository import SqlAlchemyControlPlaneRepository


def _config():
    return DatasetConfig(
        dataset_id="crm.customer",
        source=SourceConfig(system="crm", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
    )


class _Backend:
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
        del effective_by_id, max_concurrency
        outcomes = {}
        for dataset_id in dataset_ids:
            from fabric_data_framework.operations import DatasetRunAudit
            from uuid import uuid4

            run_id = uuid4()
            effective = repository.get_dataset(dataset_id)
            from fabric_data_framework.config import resolve_effective_config

            effective_hash = resolve_effective_config(effective).effective_config_hash
            repository.record_dataset_run(
                DatasetRunAudit(
                    dataset_run_id=run_id,
                    pipeline_run_id=pipeline_run_id,
                    dataset_id=dataset_id,
                    run_mode=run_mode,
                    status=DatasetStatus.SUCCEEDED,
                    effective_config_hash=effective_hash,
                )
            )
            outcomes[dataset_id] = DatasetDispatchOutcome(
                dataset_run_id=run_id,
                status=DatasetStatus.SUCCEEDED,
            )
        return outcomes


def test_dispatcher_persists_non_normal_pipeline_run_mode(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    apply_baseline_schema(engine)
    config = _config()
    repository = SqlAlchemyControlPlaneRepository(
        engine,
        domain="customer",
        domain_git_sha="abcdef0",
        framework_version="0.4.0",
    )
    repository.deploy_dataset(config)

    result = dispatch_datasets_with_backend(
        repository=repository,
        backend=_Backend(),
        environment="dev",
        domain="customer",
        domain_git_sha="abcdef0",
        framework_version="0.4.0",
        config_bundle_hash=config_bundle_hash((config,)),
        run_mode=RunMode.BACKFILL,
    )

    with engine.connect() as connection:
        row = connection.execute(
            select(pipeline_run).where(
                pipeline_run.c.pipeline_run_id == str(result.pipeline_run_id)
            )
        ).mappings().one()
    assert row["run_mode"] == RunMode.BACKFILL.value
