from __future__ import annotations

from fabric_data_framework.apply.replace import InMemoryReplaceTarget, ReplaceGuardPolicy
from fabric_data_framework.capture.full import FullSnapshotEvidence
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
from fabric_data_framework.execution import execute_full_replace
from fabric_data_framework.quality import RowRule
from fabric_data_framework.control_plane.repository import InMemoryControlPlane


def _config() -> DatasetConfig:
    return DatasetConfig(
        dataset_id="crm.customer_full",
        source=SourceConfig(system="crm", object="dbo.Customer"),
        target=TargetConfig(layer="silver", object="customer"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(
            execution_group="daily",
            criticality=Criticality.HIGH,
        ),
        quality=DataQualityPolicy(policy_name="customer", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="count_and_completeness"),
    )


def _repository() -> InMemoryControlPlane:
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config())
    return repository


def _evidence(count: int, *, complete: bool = True) -> FullSnapshotEvidence:
    return FullSnapshotEvidence(
        snapshot_id="snapshot-2026-08-28T00:00:00Z",
        complete=complete,
        source_row_count=count,
        boundary_ref="source-transaction-42",
    )


def test_full_replace_stages_then_publishes_complete_reconciled_candidate():
    repository = _repository()
    target = InMemoryReplaceTarget([{"customer_id": "OLD"}])

    result = execute_full_replace(
        repository=repository,
        target=target,
        dataset_id="crm.customer_full",
        source_rows=[{"customer_id": "C001"}, {"customer_id": "C002"}],
        snapshot_evidence=_evidence(2),
    )

    assert result.status is DatasetStatus.SUCCEEDED
    assert result.staged is not None
    assert result.reconciliation is not None
    assert [row["customer_id"] for row in target.read()] == ["C001", "C002"]
    assert repository.dataset_runs[-1].mutations.inserted == 2
    assert repository.dataset_runs[-1].mutations.deleted == 1
    assert repository.dataset_runs[-1].row_accounting.rows_read == 2


def test_incomplete_snapshot_cannot_replace_live_target():
    repository = _repository()
    target = InMemoryReplaceTarget([{"customer_id": "KEEP"}])

    result = execute_full_replace(
        repository=repository,
        target=target,
        dataset_id="crm.customer_full",
        source_rows=[{"customer_id": "C001"}],
        snapshot_evidence=_evidence(1, complete=False),
    )

    assert result.status is DatasetStatus.FAILED
    assert result.error_code == "FULL_REPLACE_GUARD_FAILED"
    assert target.read() == ({"customer_id": "KEEP"},)
    assert repository.dataset_runs[-1].mutations.inserted == 0


def test_unexpected_empty_source_cannot_wipe_non_empty_target_by_default():
    repository = _repository()
    target = InMemoryReplaceTarget([{"customer_id": "KEEP"}])

    result = execute_full_replace(
        repository=repository,
        target=target,
        dataset_id="crm.customer_full",
        source_rows=[],
        snapshot_evidence=_evidence(0),
    )

    assert result.status is DatasetStatus.FAILED
    assert "empty FULL source" in result.error_message
    assert target.read() == ({"customer_id": "KEEP"},)


def test_candidate_drop_guard_blocks_suspicious_large_replacement():
    repository = _repository()
    target = InMemoryReplaceTarget(
        [{"customer_id": f"C{index:03d}"} for index in range(10)]
    )

    result = execute_full_replace(
        repository=repository,
        target=target,
        dataset_id="crm.customer_full",
        source_rows=[{"customer_id": "C999"}],
        snapshot_evidence=_evidence(1),
        guard_policy=ReplaceGuardPolicy(max_candidate_drop_fraction=0.5),
    )

    assert result.status is DatasetStatus.FAILED
    assert "row-count drop" in result.error_message
    assert len(target.read()) == 10


def test_reconciliation_failure_preserves_target_and_staged_candidate_for_evidence():
    repository = _repository()
    target = InMemoryReplaceTarget([{"customer_id": "KEEP"}])

    result = execute_full_replace(
        repository=repository,
        target=target,
        dataset_id="crm.customer_full",
        source_rows=[{"customer_id": "C001"}],
        snapshot_evidence=_evidence(1),
        force_reconciliation_failure=True,
    )

    assert result.status is DatasetStatus.FAILED
    assert result.error_code == "RECONCILIATION_FAILED"
    assert result.staged is not None
    assert result.staged.rows == ({"customer_id": "C001"},)
    assert target.read() == ({"customer_id": "KEEP"},)


def test_row_quarantine_is_accounted_before_full_candidate_publication():
    repository = _repository()
    target = InMemoryReplaceTarget([{"customer_id": "OLD"}])
    rules = (
        RowRule(
            code="VALID_ID",
            message="customer_id must start with C",
            predicate=lambda row: str(row.get("customer_id", "")).startswith("C"),
        ),
    )

    result = execute_full_replace(
        repository=repository,
        target=target,
        dataset_id="crm.customer_full",
        source_rows=[{"customer_id": "C001"}, {"customer_id": "BAD"}],
        snapshot_evidence=_evidence(2),
        rules=rules,
    )

    assert result.status is DatasetStatus.SUCCEEDED
    assert len(result.quarantined) == 1
    assert target.read() == ({"customer_id": "C001"},)
    accounting = repository.dataset_runs[-1].row_accounting
    assert accounting.rows_read == 2
    assert accounting.rows_accepted == 1
    assert accounting.rows_quarantined == 1
    assert len(repository.quarantine_batches) == 1


def test_source_evidence_row_count_mismatch_fails_before_staging_or_publication():
    repository = _repository()
    target = InMemoryReplaceTarget([{"customer_id": "KEEP"}])

    result = execute_full_replace(
        repository=repository,
        target=target,
        dataset_id="crm.customer_full",
        source_rows=[{"customer_id": "C001"}],
        snapshot_evidence=_evidence(2),
    )

    assert result.status is DatasetStatus.FAILED
    assert result.error_code == "FULL_SNAPSHOT_EVIDENCE_INVALID"
    assert result.staged is None
    assert target.read() == ({"customer_id": "KEEP"},)
