from sqlalchemy import create_engine, select

from fabric_data_framework.control_plane.schema import reconciliation_policy
from fabric_data_framework.deployment.delivery import materialize_semantic_metadata
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    ReconciliationAggregate,
    ReconciliationCheck,
    ReconciliationCheckKind,
    ReconciliationPolicy,
    SourceConfig,
    TargetConfig,
)


def test_declarative_reconciliation_definition_is_materialized_in_control_plane():
    config = DatasetConfig(
        dataset_id="orders.order",
        source=SourceConfig(system="erp", object="dbo.Order"),
        target=TargetConfig(layer="silver", object="order"),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(execution_group="orders_daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(
            policy_name="orders_controls",
            checks=(
                ReconciliationCheck(
                    check_id="daily-count",
                    kind=ReconciliationCheckKind.ROW_COUNT_MATCH,
                    partition_by=("business_date",),
                ),
                ReconciliationCheck(
                    check_id="amount-total",
                    kind=ReconciliationCheckKind.AGGREGATE_MATCH,
                    column="amount",
                    aggregate=ReconciliationAggregate.SUM,
                    absolute_tolerance=0.01,
                ),
            ),
        ),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")

    materialize_semantic_metadata(
        engine,
        configs=(config,),
        domain="orders",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )

    with engine.connect() as connection:
        row = connection.execute(
            select(reconciliation_policy).where(
                reconciliation_policy.c.dataset_id == config.dataset_id
            )
        ).mappings().one()

    assert row["policy_name"] == "orders_controls"
    assert row["required_for_state_commit"] is True
    assert row["definition"] == config.reconciliation.model_dump(mode="json")
    assert [item["check_id"] for item in row["definition"]["checks"]] == [
        "daily-count",
        "amount-total",
    ]
