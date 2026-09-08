from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from fabric_data_framework.certification.pipeline_child import (
    CertificationPipelineChildExecutor,
)
from fabric_data_framework.contracts.execution_plan import compile_execution_plan
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.execution.pipeline_child import (
    FabricPipelineChildRequest,
    execute_pipeline_child,
)
from fabric_data_framework.metadata.config import (
    DatasetConfig,
    DatasetStatus,
    RunMode,
    resolve_effective_config,
)


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "certification/integration_project/config/datasets"


def _config(name: str) -> DatasetConfig:
    return DatasetConfig.model_validate_json((DATASETS / name).read_text(encoding="utf-8"))


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


def _warehouse_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _attach(dbapi_connection, _connection_record):
        dbapi_connection.execute("ATTACH DATABASE ':memory:' AS dbo")

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE dbo.cert_pipeline_control "
                "(dataset_id TEXT PRIMARY KEY, failure_mode TEXT NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE dbo.cert_progress "
                "(dataset_id TEXT PRIMARY KEY, checkpoint TEXT NOT NULL)"
            )
        )
        for name in (
            "cert_full_source",
            "cert_full_target",
            "cert_scd1_target",
            "cert_scd2_current",
            "cert_retry_source",
            "cert_retry_target",
            "cert_recon_source",
            "cert_recon_target",
        ):
            connection.execute(text(f"CREATE TABLE dbo.{name} (id INTEGER, value TEXT)"))
        for name in ("cert_scd1_source", "cert_scd2_source"):
            connection.execute(
                text(
                    f"CREATE TABLE dbo.{name} "
                    "(id INTEGER, value TEXT, modified_at TEXT)"
                )
            )
        connection.execute(
            text(
                "CREATE TABLE dbo.cert_scd2_history "
                "(id INTEGER, value TEXT, is_current INTEGER)"
            )
        )
    return engine


def _seed(connection, *, dataset_id: str, mode: str, checkpoint: str) -> None:
    connection.execute(
        text(
            "INSERT INTO dbo.cert_pipeline_control(dataset_id, failure_mode) "
            "VALUES (:dataset_id, :mode)"
        ),
        {"dataset_id": dataset_id, "mode": mode},
    )
    connection.execute(
        text(
            "INSERT INTO dbo.cert_progress(dataset_id, checkpoint) "
            "VALUES (:dataset_id, :checkpoint)"
        ),
        {"dataset_id": dataset_id, "checkpoint": checkpoint},
    )


def _rows(engine, table: str, columns: str = "id, value"):
    with engine.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                text(f"SELECT {columns} FROM dbo.{table} ORDER BY id, value")
            ).mappings()
        ]


def _checkpoint(engine, dataset_id: str) -> str:
    with engine.connect() as connection:
        return str(
            connection.execute(
                text(
                    "SELECT checkpoint FROM dbo.cert_progress WHERE dataset_id=:dataset_id"
                ),
                {"dataset_id": dataset_id},
            ).scalar_one()
        )


def _execute(config: DatasetConfig, engine):
    repository = InMemoryControlPlane()
    repository.deploy_dataset(config)
    request = _request(config)
    outcome = execute_pipeline_child(
        repository=repository,
        request=request,
        executor=CertificationPipelineChildExecutor(engine),
    )
    return repository, request, outcome


def test_full_replace_uses_real_reconciliation_before_publication():
    config = _config("cert.full_replace.json")
    engine = _warehouse_engine()
    with engine.begin() as connection:
        _seed(connection, dataset_id=config.dataset_id, mode="SUCCESS", checkpoint="baseline")
        connection.execute(text("INSERT INTO dbo.cert_full_source VALUES (1, 'new'), (2, 'added')"))
        connection.execute(text("INSERT INTO dbo.cert_full_target VALUES (1, 'old')"))

    repository, request, outcome = _execute(config, engine)

    assert outcome.dataset_run_id == request.framework_dataset_run_id
    assert outcome.status is DatasetStatus.SUCCEEDED
    assert _rows(engine, "cert_full_target") == [
        {"id": 2, "value": "added"},
        {"id": 1, "value": "new"},
    ]
    assert _checkpoint(engine, config.dataset_id) == "published"
    assert len(repository.reconciliations) == 1
    assert len(repository.dataset_runs) == 1


def test_retryable_failure_keeps_state_unchanged_then_exact_retry_publishes_once():
    config = _config("cert.retry_idempotency.json")
    engine = _warehouse_engine()
    with engine.begin() as connection:
        _seed(
            connection,
            dataset_id=config.dataset_id,
            mode="CERTIFICATION_RETRYABLE_FAILURE",
            checkpoint="baseline",
        )
        connection.execute(text("INSERT INTO dbo.cert_retry_source VALUES (1, 'new')"))
        connection.execute(text("INSERT INTO dbo.cert_retry_target VALUES (1, 'old')"))

    repository = InMemoryControlPlane()
    repository.deploy_dataset(config)
    first_request = _request(config)
    first = execute_pipeline_child(
        repository=repository,
        request=first_request,
        executor=CertificationPipelineChildExecutor(engine),
    )

    assert first.status is DatasetStatus.FAILED
    assert first.retryable is True
    assert first.error_code == "CERTIFICATION_RETRYABLE_FAILURE"
    assert _rows(engine, "cert_retry_target") == [{"id": 1, "value": "old"}]
    assert _checkpoint(engine, config.dataset_id) == "baseline"

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE dbo.cert_pipeline_control SET failure_mode='SUCCESS' "
                "WHERE dataset_id=:dataset_id"
            ),
            {"dataset_id": config.dataset_id},
        )
    second_request = _request(config)
    second = execute_pipeline_child(
        repository=repository,
        request=second_request,
        executor=CertificationPipelineChildExecutor(engine),
    )

    assert second.status is DatasetStatus.SUCCEEDED
    assert second.dataset_run_id == second_request.framework_dataset_run_id
    assert _rows(engine, "cert_retry_target") == [{"id": 1, "value": "new"}]
    assert _checkpoint(engine, config.dataset_id) == "published"
    assert len(repository.dataset_runs) == 2


def test_reconciliation_failure_records_failure_and_never_publishes_candidate():
    config = _config("cert.reconciliation_fail_closed.json")
    engine = _warehouse_engine()
    with engine.begin() as connection:
        _seed(
            connection,
            dataset_id=config.dataset_id,
            mode="RECONCILIATION_FAILED",
            checkpoint="baseline",
        )
        connection.execute(text("INSERT INTO dbo.cert_recon_source VALUES (1, 'new')"))
        connection.execute(text("INSERT INTO dbo.cert_recon_target VALUES (1, 'old')"))

    repository, _, outcome = _execute(config, engine)

    assert outcome.status is DatasetStatus.FAILED
    assert outcome.retryable is False
    assert outcome.error_code == "RECONCILIATION_FAILED"
    assert _rows(engine, "cert_recon_target") == [{"id": 1, "value": "old"}]
    assert _checkpoint(engine, config.dataset_id) == "baseline"
    assert len(repository.reconciliations) == 1
    assert repository.reconciliations[0].status.value == "FAIL"


def test_scd1_uses_committed_checkpoint_for_ordering_and_advances_only_after_apply():
    config = _config("cert.watermark_scd1.json")
    engine = _warehouse_engine()
    with engine.begin() as connection:
        _seed(
            connection,
            dataset_id=config.dataset_id,
            mode="SUCCESS",
            checkpoint="2026-08-30T00:00:00Z",
        )
        connection.execute(
            text(
                "INSERT INTO dbo.cert_scd1_source VALUES "
                "(1, 'new', '2026-08-31T00:00:00Z'), "
                "(2, 'added', '2026-08-31T00:00:00Z')"
            )
        )
        connection.execute(text("INSERT INTO dbo.cert_scd1_target VALUES (1, 'old')"))

    _, _, outcome = _execute(config, engine)

    assert outcome.status is DatasetStatus.SUCCEEDED
    assert _rows(engine, "cert_scd1_target") == [
        {"id": 2, "value": "added"},
        {"id": 1, "value": "new"},
    ]
    assert _checkpoint(engine, config.dataset_id) == "2026-08-31T00:00:00Z"
    assert outcome.mutations.inserted == 1
    assert outcome.mutations.updated == 1


def test_scd2_publishes_current_and_history_only_after_invariant_reconciliation():
    config = _config("cert.watermark_scd2.json")
    engine = _warehouse_engine()
    with engine.begin() as connection:
        _seed(
            connection,
            dataset_id=config.dataset_id,
            mode="SUCCESS",
            checkpoint="2026-08-30T00:00:00Z",
        )
        connection.execute(
            text(
                "INSERT INTO dbo.cert_scd2_source VALUES "
                "(1, 'new', '2026-08-31T00:00:00Z'), "
                "(2, 'added', '2026-08-31T00:00:00Z')"
            )
        )
        connection.execute(text("INSERT INTO dbo.cert_scd2_current VALUES (1, 'old')"))
        connection.execute(text("INSERT INTO dbo.cert_scd2_history VALUES (1, 'old', 1)"))

    repository, _, outcome = _execute(config, engine)

    assert outcome.status is DatasetStatus.SUCCEEDED
    assert _rows(engine, "cert_scd2_current") == [
        {"id": 2, "value": "added"},
        {"id": 1, "value": "new"},
    ]
    assert _rows(engine, "cert_scd2_history", "id, value, is_current") == [
        {"id": 2, "value": "added", "is_current": 1},
        {"id": 1, "value": "new", "is_current": 1},
        {"id": 1, "value": "old", "is_current": 0},
    ]
    assert _checkpoint(engine, config.dataset_id) == "2026-08-31T00:00:00Z"
    assert len(repository.reconciliations) == 1
    assert repository.reconciliations[0].status.value == "PASS"


def test_unknown_control_mode_fails_before_any_certification_state_mutation():
    config = _config("cert.full_replace.json")
    engine = _warehouse_engine()
    with engine.begin() as connection:
        _seed(connection, dataset_id=config.dataset_id, mode="SUCCESS", checkpoint="baseline")
        connection.execute(
            text(
                "UPDATE dbo.cert_pipeline_control SET failure_mode='FUTURE_UNKNOWN' "
                "WHERE dataset_id=:dataset_id"
            ),
            {"dataset_id": config.dataset_id},
        )
        connection.execute(text("INSERT INTO dbo.cert_full_source VALUES (1, 'new')"))
        connection.execute(text("INSERT INTO dbo.cert_full_target VALUES (1, 'old')"))

    repository = InMemoryControlPlane()
    repository.deploy_dataset(config)
    request = _request(config)

    import pytest

    with pytest.raises(RuntimeError, match="unsupported certification failure mode"):
        execute_pipeline_child(
            repository=repository,
            request=request,
            executor=CertificationPipelineChildExecutor(engine),
        )

    assert _rows(engine, "cert_full_target") == [{"id": 1, "value": "old"}]
    assert _checkpoint(engine, config.dataset_id) == "baseline"
    assert repository.dataset_runs == []
