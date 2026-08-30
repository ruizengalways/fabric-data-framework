from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select

from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    RunMode,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.control_plane.schema import (
    ENVIRONMENT_LOCAL_STATE_TABLES,
    PROMOTABLE_DEFINITION_TABLES,
    dataset_attempt_lineage,
    reprocess_request,
    table_names,
)
from fabric_data_framework.control_plane.io import (
    record_attempt_lineage,
    record_reprocess_request,
)
from fabric_data_framework.contracts.recovery import (
    DatasetAttemptLineage,
    ReprocessRequest,
    ReprocessRequestStatus,
)
from fabric_data_framework.delivery import materialize_semantic_metadata


def _config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="erp.order",
        source=SourceConfig(system="erp", object="dbo.Order", connection_ref="erp_sql"),
        target=TargetConfig(layer="silver", object="order"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="erp_full"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
    )


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    materialize_semantic_metadata(
        engine,
        configs=(_config(),),
        domain="orders",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )
    return engine


def test_attempt_lineage_is_environment_local_and_schema_sets_still_cover_every_table():
    assert "dataset_attempt_lineage" in ENVIRONMENT_LOCAL_STATE_TABLES
    assert "dataset_attempt_lineage" not in PROMOTABLE_DEFINITION_TABLES
    assert PROMOTABLE_DEFINITION_TABLES.isdisjoint(ENVIRONMENT_LOCAL_STATE_TABLES)
    assert PROMOTABLE_DEFINITION_TABLES | ENVIRONMENT_LOCAL_STATE_TABLES == table_names()


def test_reprocess_request_status_can_advance_without_changing_semantic_identity(tmp_path):
    engine = _engine(tmp_path)
    request = ReprocessRequest(
        dataset_id="erp.order",
        run_mode=RunMode.BACKFILL,
        reason="repair missing source interval",
        requested_by="data-ops",
        range_json={"lower": 100, "upper": 200},
    )

    record_reprocess_request(engine, request)
    record_reprocess_request(
        engine,
        request.model_copy(update={"status": ReprocessRequestStatus.RUNNING}),
    )

    with engine.connect() as connection:
        row = connection.execute(select(reprocess_request)).mappings().one()
    assert row["status"] == "RUNNING"
    assert row["range_json"] == {"lower": 100, "upper": 200}

    changed = request.model_copy(update={"reason": "different semantic request"})
    with pytest.raises(ValueError, match="semantic identity cannot change"):
        record_reprocess_request(engine, changed)


def test_attempt_lineage_is_append_only_relational_evidence(tmp_path):
    engine = _engine(tmp_path)
    request = ReprocessRequest(
        dataset_id="erp.order",
        run_mode=RunMode.BACKFILL,
        reason="repair missing source interval",
        requested_by="data-ops",
        range_json={"lower": 100, "upper": 200},
    )
    record_reprocess_request(engine, request)

    run_id = uuid4()
    lineage = DatasetAttemptLineage(
        dataset_run_id=run_id,
        dataset_id="erp.order",
        root_dataset_run_id=run_id,
        attempt=1,
        run_mode=RunMode.BACKFILL,
        reprocess_request_id=request.reprocess_request_id,
    )
    record_attempt_lineage(engine, lineage)

    with engine.connect() as connection:
        row = connection.execute(select(dataset_attempt_lineage)).mappings().one()
    assert row["dataset_run_id"] == str(run_id)
    assert row["root_dataset_run_id"] == str(run_id)
    assert row["attempt"] == 1
    assert row["run_mode"] == "BACKFILL"
    assert row["reprocess_request_id"] == str(request.reprocess_request_id)

    with pytest.raises(ValueError, match="already recorded"):
        record_attempt_lineage(engine, lineage)
