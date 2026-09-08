import pytest

from fabric_data_framework.contracts.rebuild import RebuildScope
from fabric_data_framework.contracts.rebuild_impact import RepairIssueOrigin
from fabric_data_framework.metadata.config import (
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
from fabric_data_framework.recovery.rebuild_impact import (
    RebuildImpactError,
    build_rebuild_impact_plan,
)


def _dataset(
    dataset_id: str,
    *,
    layer: str,
    dependencies: tuple[str, ...] = (),
    enabled: bool = True,
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(
            system="repair-fixture",
            object=dataset_id.replace(".", "_"),
        ),
        target=TargetConfig(
            layer=layer,
            object=dataset_id.replace(".", "_"),
        ),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(
            execution_group="repair",
            dependencies=dependencies,
        ),
        quality=DataQualityPolicy(
            policy_name="repair",
            quarantine_policy="row",
        ),
        reconciliation=ReconciliationPolicy(policy_name="repair"),
        enabled=enabled,
    )


def _graph() -> tuple[DatasetConfig, ...]:
    return (
        _dataset("bronze.customer", layer="bronze"),
        _dataset(
            "silver.customer",
            layer="silver",
            dependencies=("bronze.customer",),
        ),
        _dataset(
            "gold.customer",
            layer="gold",
            dependencies=("silver.customer",),
        ),
        _dataset(
            "gold.customer_metrics",
            layer="gold",
            dependencies=("silver.customer",),
            enabled=False,
        ),
        _dataset("bronze.product", layer="bronze"),
        _dataset(
            "silver.product",
            layer="silver",
            dependencies=("bronze.product",),
        ),
    )


def test_capture_data_issue_rebuilds_only_affected_downstream_subgraph():
    plan = build_rebuild_impact_plan(
        _graph(),
        root_dataset_ids=("bronze.customer",),
        issue_origin=RepairIssueOrigin.CAPTURE_DATA,
    )

    assert plan.affected_dataset_ids == (
        "bronze.customer",
        "silver.customer",
        "gold.customer",
        "gold.customer_metrics",
    )
    assert plan.waves == (
        ("bronze.customer",),
        ("silver.customer",),
        ("gold.customer", "gold.customer_metrics"),
    )
    scopes = {item.dataset_id: item.rebuild_scope for item in plan.datasets}
    assert scopes == {
        "bronze.customer": RebuildScope.CAPTURE_AND_TARGET,
        "silver.customer": RebuildScope.TARGET_ONLY,
        "gold.customer": RebuildScope.TARGET_ONLY,
        "gold.customer_metrics": RebuildScope.TARGET_ONLY,
    }
    assert plan.disabled_affected_dataset_ids == ("gold.customer_metrics",)
    assert "bronze.product" not in plan.affected_dataset_ids
    assert "silver.product" not in plan.affected_dataset_ids


def test_silver_target_logic_issue_does_not_rebuild_healthy_bronze():
    plan = build_rebuild_impact_plan(
        _graph(),
        root_dataset_ids=("silver.customer",),
        issue_origin=RepairIssueOrigin.TARGET_LOGIC,
    )

    assert plan.affected_dataset_ids == (
        "silver.customer",
        "gold.customer",
        "gold.customer_metrics",
    )
    assert plan.datasets[0].rebuild_scope is RebuildScope.TARGET_ONLY
    assert "bronze.customer" not in plan.affected_dataset_ids


def test_capture_semantics_issue_requires_authoritative_reset_at_root():
    plan = build_rebuild_impact_plan(
        _graph(),
        root_dataset_ids=("bronze.customer",),
        issue_origin=RepairIssueOrigin.CAPTURE_SEMANTICS,
    )

    assert plan.datasets[0].dataset_id == "bronze.customer"
    assert plan.datasets[0].rebuild_scope is RebuildScope.AUTHORITATIVE_RESET
    assert all(
        item.rebuild_scope is RebuildScope.TARGET_ONLY
        for item in plan.datasets[1:]
    )


def test_scope_override_can_widen_descendant_but_cannot_narrow_root_requirement():
    plan = build_rebuild_impact_plan(
        _graph(),
        root_dataset_ids=("bronze.customer",),
        issue_origin=RepairIssueOrigin.CAPTURE_DATA,
        scope_overrides={"gold.customer": RebuildScope.CAPTURE_AND_TARGET},
    )
    scopes = {item.dataset_id: item.rebuild_scope for item in plan.datasets}
    assert scopes["gold.customer"] is RebuildScope.CAPTURE_AND_TARGET

    with pytest.raises(RebuildImpactError, match="narrower than required"):
        build_rebuild_impact_plan(
            _graph(),
            root_dataset_ids=("bronze.customer",),
            issue_origin=RepairIssueOrigin.CAPTURE_SEMANTICS,
            scope_overrides={"bronze.customer": RebuildScope.CAPTURE_AND_TARGET},
        )


def test_scope_override_cannot_target_unaffected_dataset():
    with pytest.raises(RebuildImpactError, match="outside the affected subgraph"):
        build_rebuild_impact_plan(
            _graph(),
            root_dataset_ids=("silver.customer",),
            issue_origin=RepairIssueOrigin.TARGET_LOGIC,
            scope_overrides={"silver.product": RebuildScope.TARGET_ONLY},
        )


def test_impact_planning_fails_closed_on_unknown_dependency_and_cycle():
    broken = (
        _dataset(
            "silver.customer",
            layer="silver",
            dependencies=("bronze.missing",),
        ),
    )
    with pytest.raises(RebuildImpactError, match="undeployed dataset"):
        build_rebuild_impact_plan(
            broken,
            root_dataset_ids=("silver.customer",),
            issue_origin=RepairIssueOrigin.TARGET_LOGIC,
        )

    cyclic = (
        _dataset("silver.a", layer="silver", dependencies=("silver.b",)),
        _dataset("silver.b", layer="silver", dependencies=("silver.a",)),
    )
    with pytest.raises(RebuildImpactError, match="dependency cycle"):
        build_rebuild_impact_plan(
            cyclic,
            root_dataset_ids=("silver.a",),
            issue_origin=RepairIssueOrigin.TARGET_LOGIC,
        )


def test_impact_plan_hash_is_deterministic_for_same_semantics():
    first = build_rebuild_impact_plan(
        _graph(),
        root_dataset_ids=("bronze.customer",),
        issue_origin=RepairIssueOrigin.CAPTURE_DATA,
    )
    second = build_rebuild_impact_plan(
        reversed(_graph()),
        root_dataset_ids=("bronze.customer",),
        issue_origin=RepairIssueOrigin.CAPTURE_DATA,
    )

    assert first == second
    assert first.plan_hash == second.plan_hash
    assert len(first.plan_hash) == 64
