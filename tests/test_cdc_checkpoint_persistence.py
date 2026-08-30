from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.capture.cdc import build_cdc_checkpoint
from fabric_data_framework.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.control_plane.schema import (
    CONTROL_PLANE_SCHEMA_VERSION,
    ENVIRONMENT_LOCAL_STATE_TABLES,
)
from fabric_data_framework.control_plane.io import (
    CDCCheckpointVersionConflict,
    commit_cdc_checkpoint,
    read_cdc_checkpoint,
)
from fabric_data_framework.delivery import materialize_semantic_metadata
from fabric_data_framework.deployment import (
    ControlPlaneRecordClass,
    classify_control_plane_record,
)
from fabric_data_framework.runtime import StateCommitGate


def _config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="erp.order_cdc",
        source=SourceConfig(system="erp", object="dbo.Order", connection_ref="erp_sql"),
        target=TargetConfig(layer="silver", object="order"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.CDC,
            apply_strategy=ApplyStrategy.UPSERT,
            merge_key=("order_id",),
        ),
        orchestration=OrchestrationPolicy(execution_group="erp_cdc"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
    )


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    materialize_semantic_metadata(
        engine,
        configs=(_config(),),
        domain="orders",
        domain_git_sha="d" * 40,
        framework_version="0.4.0",
    )
    return engine


def _passed_gate() -> StateCommitGate:
    return StateCommitGate(
        target_committed=True,
        reconciliation_required=True,
        reconciliation_passed=True,
    )


def test_cdc_checkpoint_is_environment_local_control_plane_state():
    assert CONTROL_PLANE_SCHEMA_VERSION >= 2
    assert "cdc_checkpoint" in ENVIRONMENT_LOCAL_STATE_TABLES
    assert (
        classify_control_plane_record("cdc_checkpoint")
        is ControlPlaneRecordClass.ENVIRONMENT_LOCAL_STATE
    )


def test_cdc_checkpoint_initial_commit_and_read(tmp_path):
    engine = _engine(tmp_path)
    run_id = uuid4()
    checkpoint = build_cdc_checkpoint({"p0": (10, 2), "p1": (4, 0)})

    state = commit_cdc_checkpoint(
        engine,
        dataset_id="erp.order_cdc",
        checkpoint=checkpoint,
        dataset_run_id=run_id,
        expected_version=0,
        gate=_passed_gate(),
    )

    assert state.version == 1
    assert state.checkpoint == checkpoint
    assert state.committed_dataset_run_id == run_id
    assert read_cdc_checkpoint(engine, "erp.order_cdc") == state


def test_cdc_checkpoint_refuses_state_advance_before_semantic_gate(tmp_path):
    engine = _engine(tmp_path)
    checkpoint = build_cdc_checkpoint({"p0": (10, 0)})

    with pytest.raises(ValueError, match="cannot advance"):
        commit_cdc_checkpoint(
            engine,
            dataset_id="erp.order_cdc",
            checkpoint=checkpoint,
            dataset_run_id=uuid4(),
            expected_version=0,
            gate=StateCommitGate(
                target_committed=True,
                reconciliation_required=True,
                reconciliation_passed=False,
            ),
        )

    assert read_cdc_checkpoint(engine, "erp.order_cdc") is None


def test_cdc_checkpoint_update_uses_optimistic_version(tmp_path):
    engine = _engine(tmp_path)
    first = commit_cdc_checkpoint(
        engine,
        dataset_id="erp.order_cdc",
        checkpoint=build_cdc_checkpoint({"p0": (10, 0)}),
        dataset_run_id=uuid4(),
        expected_version=0,
        gate=_passed_gate(),
    )
    second_run = uuid4()
    second_checkpoint = build_cdc_checkpoint({"p0": (12, 3)})
    second = commit_cdc_checkpoint(
        engine,
        dataset_id="erp.order_cdc",
        checkpoint=second_checkpoint,
        dataset_run_id=second_run,
        expected_version=first.version,
        gate=_passed_gate(),
    )

    assert second.version == 2
    assert second.checkpoint == second_checkpoint
    assert second.committed_dataset_run_id == second_run

    with pytest.raises(CDCCheckpointVersionConflict, match="current version is 2"):
        commit_cdc_checkpoint(
            engine,
            dataset_id="erp.order_cdc",
            checkpoint=build_cdc_checkpoint({"p0": (13, 0)}),
            dataset_run_id=uuid4(),
            expected_version=1,
            gate=_passed_gate(),
        )


def test_cdc_checkpoint_refuses_regression_or_partition_drop(tmp_path):
    engine = _engine(tmp_path)
    first = commit_cdc_checkpoint(
        engine,
        dataset_id="erp.order_cdc",
        checkpoint=build_cdc_checkpoint({"p0": (10, 0), "p1": (5, 0)}),
        dataset_run_id=uuid4(),
        expected_version=0,
        gate=_passed_gate(),
    )

    with pytest.raises(ValueError, match="cannot regress partition p0"):
        commit_cdc_checkpoint(
            engine,
            dataset_id="erp.order_cdc",
            checkpoint=build_cdc_checkpoint({"p0": (9, 0), "p1": (6, 0)}),
            dataset_run_id=uuid4(),
            expected_version=first.version,
            gate=_passed_gate(),
        )

    with pytest.raises(ValueError, match="cannot drop partition p1"):
        commit_cdc_checkpoint(
            engine,
            dataset_id="erp.order_cdc",
            checkpoint=build_cdc_checkpoint({"p0": (11, 0)}),
            dataset_run_id=uuid4(),
            expected_version=first.version,
            gate=_passed_gate(),
        )

    persisted = read_cdc_checkpoint(engine, "erp.order_cdc")
    assert persisted is not None
    assert persisted.version == 1
    assert persisted.checkpoint == build_cdc_checkpoint({"p0": (10, 0), "p1": (5, 0)})


def test_cdc_checkpoint_initial_writer_requires_expected_version_zero(tmp_path):
    engine = _engine(tmp_path)

    with pytest.raises(CDCCheckpointVersionConflict, match="does not exist"):
        commit_cdc_checkpoint(
            engine,
            dataset_id="erp.order_cdc",
            checkpoint=build_cdc_checkpoint({"p0": (1, 0)}),
            dataset_run_id=uuid4(),
            expected_version=4,
            gate=_passed_gate(),
        )
