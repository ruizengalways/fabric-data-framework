from fabric_data_framework.apply.append import InMemoryAppendTarget
from fabric_data_framework.contracts.reconciliation import (
    ReconciliationObservation,
    ReconciliationSeverity,
    ReconciliationStatus,
)
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.execution import execute_append_batch
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationCheck,
    ReconciliationCheckKind,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)


def _config(*, required=True, severity=ReconciliationSeverity.ERROR) -> DatasetConfig:
    return DatasetConfig(
        dataset_id="events.order_event",
        source=SourceConfig(system="events", object="order_event"),
        target=TargetConfig(layer="silver", object="order_event"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.APPEND,
            append_identity=("event_id",),
        ),
        orchestration=OrchestrationPolicy(execution_group="events_daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(
            policy_name="append_controls",
            required_for_state_commit=required,
            checks=(
                ReconciliationCheck(
                    check_id="source-target-count",
                    kind=ReconciliationCheckKind.ROW_COUNT_MATCH,
                    severity=severity,
                ),
            ),
        ),
    )


def _run(config: DatasetConfig):
    repository = InMemoryControlPlane()
    repository.deploy_dataset(config)
    target = InMemoryAppendTarget(({"event_id": "E0", "value": 0},))
    result = execute_append_batch(
        repository=repository,
        target=target,
        dataset_id=config.dataset_id,
        source_rows=({"event_id": "E1", "value": 10},),
        reconciliation_observations=(
            ReconciliationObservation(
                check_id="source-target-count",
                expected=1,
                actual=0,
            ),
        ),
    )
    return repository, target, result


def test_warning_reconciliation_is_audited_and_allows_publication():
    repository, target, result = _run(
        _config(severity=ReconciliationSeverity.WARNING)
    )

    assert result.status is DatasetStatus.SUCCEEDED
    assert result.reconciliation is not None
    assert result.reconciliation.status is ReconciliationStatus.WARN
    assert [row["event_id"] for row in target.read()] == ["E0", "E1"]
    assert repository.reconciliation_results[-1].status is ReconciliationStatus.WARN


def test_nonrequired_error_reconciliation_does_not_claim_state_gate_authority():
    repository, target, result = _run(_config(required=False))

    assert result.status is DatasetStatus.SUCCEEDED
    assert result.reconciliation is not None
    assert result.reconciliation.status is ReconciliationStatus.FAIL
    assert result.reconciliation.blocks_state_advance is False
    assert [row["event_id"] for row in target.read()] == ["E0", "E1"]
    assert repository.dataset_runs[-1].status is DatasetStatus.SUCCEEDED


def test_required_error_reconciliation_blocks_publication():
    repository, target, result = _run(_config(required=True))

    assert result.status is DatasetStatus.FAILED
    assert result.reconciliation is not None
    assert result.reconciliation.status is ReconciliationStatus.FAIL
    assert result.reconciliation.blocks_state_advance is True
    assert result.error_code == "RECONCILIATION_FAILED"
    assert [row["event_id"] for row in target.read()] == ["E0"]
    assert repository.dataset_runs[-1].status is DatasetStatus.FAILED
