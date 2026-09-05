from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select

from fabric_data_framework.contracts.group_policy import (
    DataQualityPolicyPatch,
    ExecutionGroupPolicy,
    PipelineFailurePolicy,
)
from fabric_data_framework.control_plane.repository import InMemoryControlPlane
from fabric_data_framework.control_plane.schema import data_quality_policy
from fabric_data_framework.deployment.delivery import (
    config_bundle_hash,
    materialize_semantic_metadata,
)
from fabric_data_framework.metadata.config import (
    ApplyStrategy,
    CaptureStrategy,
    DataQualityPolicy,
    DatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    OverrideField,
    ReconciliationPolicy,
    RuntimeOverride,
    SourceConfig,
    TargetConfig,
    canonical_hash,
)
from fabric_data_framework.orchestration.planner import (
    OrchestrationIntegrityError,
    build_dispatch_plan,
)


def _config(dataset_id: str, *, group: str = "daily") -> DatasetConfig:
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(system="crm", object=dataset_id),
        target=TargetConfig(layer="silver", object=dataset_id),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.FULL,
            apply_strategy=ApplyStrategy.REPLACE,
        ),
        orchestration=OrchestrationPolicy(
            execution_group=group,
            max_concurrency=4,
        ),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="row"),
        reconciliation=ReconciliationPolicy(policy_name="count"),
    )


def test_execution_group_defaults_dataset_patch_and_runtime_override_have_fixed_precedence():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("crm.customer"))
    repository.deploy_dataset(_config("crm.contact"))
    repository.deploy_dataset(_config("crm.other", group="hourly"))

    policy = ExecutionGroupPolicy(
        execution_group="daily",
        failure_policy=PipelineFailurePolicy.FAIL_AT_END,
        max_concurrency=2,
        quality_defaults=DataQualityPolicyPatch(
            enabled=False,
            quarantine_enabled=False,
            max_quarantine_rows=10,
        ),
        dataset_quality_overrides={
            "crm.contact": DataQualityPolicyPatch(
                enabled=True,
                max_quarantine_rows=1,
            )
        },
    )
    override = RuntimeOverride(
        dataset_id="crm.contact",
        field=OverrideField.QUARANTINE_ENABLED,
        value=True,
        reason="temporary approved incident handling",
        requested_by="operator@example.invalid",
        valid_from=datetime(2026, 9, 5, tzinfo=timezone.utc),
    )

    plan = build_dispatch_plan(
        repository=repository,
        execution_group_policy=policy,
        overrides=(override,),
        as_of=datetime(2026, 9, 6, tzinfo=timezone.utc),
        max_concurrency=4,
    )

    assert plan.selected_dataset_ids == ("crm.contact", "crm.customer")
    assert plan.max_concurrency == 2
    assert plan.failure_policy is PipelineFailurePolicy.FAIL_AT_END
    assert plan.execution_group_policy_hash == policy.policy_hash

    customer = plan.effective_for("crm.customer")
    assert customer.config.quality.enabled is False
    assert customer.config.quality.quarantine_enabled is False
    assert customer.config.quality.max_quarantine_rows == 10

    contact = plan.effective_for("crm.contact")
    assert contact.config.quality.enabled is True
    assert contact.config.quality.quarantine_enabled is True
    assert contact.config.quality.max_quarantine_rows == 1
    assert contact.base_config_hash == repository.get_dataset("crm.contact").config_hash
    assert contact.effective_config_hash != contact.base_config_hash


def test_execution_group_policy_rejects_dataset_override_outside_group():
    repository = InMemoryControlPlane()
    repository.deploy_dataset(_config("crm.customer"))
    repository.deploy_dataset(_config("crm.hourly", group="hourly"))
    policy = ExecutionGroupPolicy(
        execution_group="daily",
        dataset_quality_overrides={
            "crm.hourly": DataQualityPolicyPatch(enabled=False)
        },
    )

    with pytest.raises(OrchestrationIntegrityError, match="outside its group"):
        build_dispatch_plan(repository=repository, execution_group_policy=policy)


def test_group_policy_becomes_release_identity_without_breaking_legacy_dataset_only_hash():
    configs = (_config("crm.customer"),)
    historical = canonical_hash([configs[0].model_dump(mode="json")])
    assert config_bundle_hash(configs) == historical

    policy = ExecutionGroupPolicy(
        execution_group="daily",
        quality_defaults=DataQualityPolicyPatch(max_quarantine_fraction=0.01),
    )
    assert config_bundle_hash(configs, (policy,)) != historical
    changed = policy.model_copy(
        update={"quality_defaults": DataQualityPolicyPatch(max_quarantine_fraction=0.02)}
    )
    assert config_bundle_hash(configs, (policy,)) != config_bundle_hash(configs, (changed,))


def test_materialized_dq_definition_exposes_operational_switches_and_thresholds(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    base = _config("crm.customer")
    config = base.model_copy(
        update={
            "quality": base.quality.model_copy(
                update={
                    "enabled": True,
                    "quarantine_enabled": True,
                    "max_quarantine_rows": 25,
                    "max_quarantine_fraction": 0.005,
                }
            )
        }
    )
    materialize_semantic_metadata(
        engine,
        configs=(config,),
        domain="crm",
        domain_git_sha="a" * 40,
        framework_version="0.4.0",
    )

    with engine.connect() as connection:
        row = connection.execute(select(data_quality_policy)).mappings().one()
    assert row["definition"]["enabled"] is True
    assert row["definition"]["quarantine_enabled"] is True
    assert row["definition"]["max_quarantine_rows"] == 25
    assert row["definition"]["max_quarantine_fraction"] == 0.005
