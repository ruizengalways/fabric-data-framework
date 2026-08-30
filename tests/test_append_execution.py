from fabric_data_framework.apply.append import InMemoryAppendTarget
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)
from fabric_data_framework.execution import execute_append_batch
from fabric_data_framework.quality.rules import RowRule
from fabric_data_framework.control_plane.repository import InMemoryControlPlane


def _config() -> DatasetConfig:
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
        reconciliation=ReconciliationPolicy(policy_name="append_accounting"),
    )


def _repo() -> InMemoryControlPlane:
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config())
    return repository


def test_append_execution_publishes_only_new_identities_and_audits_mutation():
    repository = _repo()
    target = InMemoryAppendTarget(({"event_id": "E0", "value": 0},))

    result = execute_append_batch(
        repository=repository,
        target=target,
        dataset_id="events.order_event",
        source_rows=(
            {"event_id": "E1", "value": 10},
            {"event_id": "E2", "value": 20},
        ),
        source_reference="landing/events/batch-1",
    )

    assert result.status is DatasetStatus.SUCCEEDED
    assert result.append_result is not None
    assert result.append_result.inserted == 2
    assert [row["event_id"] for row in target.read()] == ["E0", "E1", "E2"]
    assert repository.dataset_runs[-1].mutations.inserted == 2


def test_append_execution_exact_replay_is_successful_noop():
    repository = _repo()
    target = InMemoryAppendTarget()

    first = execute_append_batch(
        repository=repository,
        target=target,
        dataset_id="events.order_event",
        source_rows=({"event_id": "E1", "value": 10},),
    )
    before = target.read()
    second = execute_append_batch(
        repository=repository,
        target=target,
        dataset_id="events.order_event",
        source_rows=({"event_id": "E1", "value": 10},),
    )

    assert first.status is DatasetStatus.SUCCEEDED
    assert second.status is DatasetStatus.SUCCEEDED
    assert second.append_result is not None
    assert second.append_result.inserted == 0
    assert second.append_result.replayed == 1
    assert target.read() == before


def test_append_execution_conflict_fails_without_mutating_target():
    repository = _repo()
    target = InMemoryAppendTarget()
    execute_append_batch(
        repository=repository,
        target=target,
        dataset_id="events.order_event",
        source_rows=({"event_id": "E1", "value": 10},),
    )
    before = target.read()

    result = execute_append_batch(
        repository=repository,
        target=target,
        dataset_id="events.order_event",
        source_rows=({"event_id": "E1", "value": 99},),
    )

    assert result.status is DatasetStatus.FAILED
    assert result.error_code == "APPEND_IDENTITY_CONFLICT"
    assert target.read() == before


def test_append_execution_reconciliation_failure_preserves_target():
    repository = _repo()
    target = InMemoryAppendTarget(({"event_id": "E0", "value": 0},))
    before = target.read()

    result = execute_append_batch(
        repository=repository,
        target=target,
        dataset_id="events.order_event",
        source_rows=({"event_id": "E1", "value": 10},),
        force_reconciliation_failure=True,
    )

    assert result.status is DatasetStatus.FAILED
    assert result.error_code == "RECONCILIATION_FAILED"
    assert target.read() == before


def test_append_execution_quarantines_bad_rows_and_accounts_accepted_rows():
    repository = _repo()
    target = InMemoryAppendTarget()
    rule = RowRule(
        code="POSITIVE_VALUE",
        message="value must be positive",
        predicate=lambda row: row["value"] > 0,
    )

    result = execute_append_batch(
        repository=repository,
        target=target,
        dataset_id="events.order_event",
        source_rows=(
            {"event_id": "E1", "value": 10},
            {"event_id": "E2", "value": -1},
        ),
        rules=(rule,),
        source_reference="landing/events/batch-2",
    )

    assert result.status is DatasetStatus.SUCCEEDED
    assert len(result.quarantined) == 1
    assert [row["event_id"] for row in target.read()] == ["E1"]
    assert repository.dataset_runs[-1].row_accounting is not None
    assert repository.dataset_runs[-1].row_accounting.rows_quarantined == 1
