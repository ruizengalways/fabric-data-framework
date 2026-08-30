import pytest

from fabric_data_framework.apply.replace import InMemoryReplaceTarget
from fabric_data_framework.apply.snapshot_diff import (
    SnapshotDiffError,
    SnapshotDiffPolicy,
    plan_snapshot_diff,
)
from fabric_data_framework.capture.snapshot import SnapshotEvidence
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.execution.snapshot_diff import execute_snapshot_diff
from fabric_data_framework.quality.rules import RowRule
from fabric_data_framework.control_plane.repository import InMemoryControlPlane


def _config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="erp.product",
        source=SourceConfig(system="erp", object="dbo.Product"),
        target=TargetConfig(layer="silver", object="product"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.SNAPSHOT,
            apply_strategy=ApplyStrategy.SNAPSHOT_DIFF,
            merge_key=("product_id",),
            tracked_columns=("name", "status"),
        ),
        orchestration=OrchestrationPolicy(
            execution_group="erp_snapshot",
            criticality=Criticality.HIGH,
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="snapshot_count"),
    )


def _evidence(count: int, *, complete: bool = True) -> SnapshotEvidence:
    return SnapshotEvidence(
        snapshot_id="snap-20260828",
        complete=complete,
        source_row_count=count,
        boundary_ref="source_txn:42",
    )


def test_snapshot_diff_insert_update_delete_and_unchanged():
    current = [
        {"product_id": "P1", "name": "One", "status": "A"},
        {"product_id": "P2", "name": "Two", "status": "A"},
        {"product_id": "P3", "name": "Three", "status": "A"},
    ]
    candidate = [
        {"product_id": "P1", "name": "One", "status": "A"},
        {"product_id": "P2", "name": "Two v2", "status": "A"},
        {"product_id": "P4", "name": "Four", "status": "A"},
    ]

    plan = plan_snapshot_diff(
        current,
        candidate,
        evidence=_evidence(3),
        merge_key=("product_id",),
        tracked_columns=("name", "status"),
        policy=SnapshotDiffPolicy(propagate_deletes=True, max_delete_fraction=0.5),
    )

    assert plan.inserted_keys == (("P4",),)
    assert plan.updated_keys == (("P2",),)
    assert plan.deleted_keys == (("P3",),)
    assert plan.unchanged_keys == (("P1",),)
    assert plan.mutations.inserted == 1
    assert plan.mutations.updated == 1
    assert plan.mutations.deleted == 1


def test_snapshot_diff_without_delete_propagation_preserves_missing_target_rows():
    plan = plan_snapshot_diff(
        [{"product_id": "P1"}, {"product_id": "P2"}],
        [{"product_id": "P1"}],
        evidence=_evidence(1),
        merge_key=("product_id",),
        policy=SnapshotDiffPolicy(propagate_deletes=False),
    )

    assert plan.deleted_keys == ()
    assert {row["product_id"] for row in plan.rows} == {"P1", "P2"}


def test_snapshot_diff_requires_complete_snapshot():
    with pytest.raises(SnapshotDiffError, match="complete snapshot"):
        plan_snapshot_diff(
            [{"product_id": "P1"}],
            [{"product_id": "P1"}],
            evidence=_evidence(1, complete=False),
            merge_key=("product_id",),
        )


def test_snapshot_diff_blocks_delete_all_and_excessive_delete_fraction():
    with pytest.raises(SnapshotDiffError, match="delete all"):
        plan_snapshot_diff(
            [{"product_id": "P1"}],
            [],
            evidence=_evidence(0),
            merge_key=("product_id",),
            policy=SnapshotDiffPolicy(propagate_deletes=True),
        )

    with pytest.raises(SnapshotDiffError, match="delete fraction"):
        plan_snapshot_diff(
            [
                {"product_id": "P1"},
                {"product_id": "P2"},
                {"product_id": "P3"},
                {"product_id": "P4"},
            ],
            [{"product_id": "P1"}],
            evidence=_evidence(1),
            merge_key=("product_id",),
            policy=SnapshotDiffPolicy(
                propagate_deletes=True,
                allow_delete_all=True,
                max_delete_fraction=0.5,
            ),
        )


def test_snapshot_diff_rejects_duplicate_candidate_key():
    with pytest.raises(SnapshotDiffError, match="duplicate candidate merge key"):
        plan_snapshot_diff(
            [],
            [{"product_id": "P1"}, {"product_id": "P1"}],
            evidence=_evidence(2),
            merge_key=("product_id",),
        )


def test_executor_blocks_delete_inference_when_source_row_is_quarantined():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config())
    target = InMemoryReplaceTarget(
        [
            {"product_id": "P1", "name": "One", "status": "A"},
            {"product_id": "P2", "name": "Two", "status": "A"},
        ]
    )
    rules = (
        RowRule(
            "NAME_REQUIRED",
            "name required",
            lambda row: bool(row.get("name")),
        ),
    )

    result = execute_snapshot_diff(
        repository=repository,
        target=target,
        dataset_id="erp.product",
        source_rows=[
            {"product_id": "P1", "name": "One", "status": "A"},
            {"product_id": "P2", "name": "", "status": "A"},
        ],
        snapshot_evidence=_evidence(2),
        rules=rules,
        diff_policy=SnapshotDiffPolicy(propagate_deletes=True),
    )

    assert result.status is DatasetStatus.FAILED
    assert result.error_code == "SNAPSHOT_DIFF_GUARD_FAILED"
    assert "quarantined" in result.error_message
    assert {row["product_id"] for row in target.read()} == {"P1", "P2"}


def test_executor_reconciliation_failure_does_not_mutate_target():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config())
    target = InMemoryReplaceTarget(
        [{"product_id": "P1", "name": "One", "status": "A"}]
    )

    result = execute_snapshot_diff(
        repository=repository,
        target=target,
        dataset_id="erp.product",
        source_rows=[
            {"product_id": "P1", "name": "One v2", "status": "A"},
            {"product_id": "P2", "name": "Two", "status": "A"},
        ],
        snapshot_evidence=_evidence(2),
        diff_policy=SnapshotDiffPolicy(propagate_deletes=True),
        force_reconciliation_failure=True,
    )

    assert result.status is DatasetStatus.FAILED
    assert result.error_code == "RECONCILIATION_FAILED"
    assert target.read() == (
        {"product_id": "P1", "name": "One", "status": "A"},
    )
