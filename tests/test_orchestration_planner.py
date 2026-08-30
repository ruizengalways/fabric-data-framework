from __future__ import annotations

import pytest

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
from fabric_data_framework.contracts.dispatch import DatasetDispatchOutcome
from fabric_data_framework.orchestration.planner import (
    OrchestrationIntegrityError,
    blocking_dependencies,
    build_dispatch_plan,
)
from fabric_data_framework.control_plane.repository import InMemoryControlPlane


def _config(
    dataset_id: str,
    *,
    execution_group: str = "daily",
    dependencies: tuple[str, ...] = (),
    priority: int = 100,
    max_concurrency: int = 4,
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(system="crm", object=dataset_id),
        target=TargetConfig(layer="silver", object=dataset_id),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(
            execution_group=execution_group,
            criticality=Criticality.MEDIUM,
            dependencies=dependencies,
            priority=priority,
            max_concurrency=max_concurrency,
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject"),
        reconciliation=ReconciliationPolicy(policy_name="standard"),
    )


def test_planner_is_provider_neutral_and_computes_stable_selection_and_concurrency():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("late", priority=200, max_concurrency=4))
    repository.deploy_dataset(_config("first", priority=10, max_concurrency=2))
    repository.deploy_dataset(_config("other_group", execution_group="hourly"))

    plan = build_dispatch_plan(
        repository=repository,
        execution_group="daily",
        max_concurrency=8,
    )

    assert plan.selected_dataset_ids == ("first", "late")
    assert plan.max_concurrency == 2
    assert plan.effective_for("first").config.dataset_id == "first"


def test_dependency_on_deployed_but_unselected_dataset_is_a_blocker_not_metadata_corruption():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("upstream", execution_group="hourly"))
    repository.deploy_dataset(
        _config("daily_child", execution_group="daily", dependencies=("upstream",))
    )

    plan = build_dispatch_plan(repository=repository, execution_group="daily")

    assert plan.selected_dataset_ids == ("daily_child",)
    assert blocking_dependencies(plan, "daily_child", {}) == ("upstream",)


def test_planner_rejects_cycle_without_invoking_an_execution_backend():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("a", dependencies=("b",)))
    repository.deploy_dataset(_config("b", dependencies=("a",)))

    with pytest.raises(OrchestrationIntegrityError, match="dependency cycle"):
        build_dispatch_plan(repository=repository)


def test_dispatch_outcome_contract_remains_backend_agnostic():
    outcome = DatasetDispatchOutcome(
        dataset_run_id=__import__("uuid").uuid4(),
        status=DatasetStatus.SUCCEEDED,
    )
    assert outcome.status is DatasetStatus.SUCCEEDED
