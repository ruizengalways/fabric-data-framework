from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select

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
    WatermarkConfig,
)
from fabric_data_framework.control_plane.schema import dataset, deployment_history, watermark
from fabric_data_framework.deployment.delivery import (
    build_release_manifest,
    config_bundle_hash,
    materialize_semantic_metadata,
    record_deployment_history,
    validate_release_tag,
)
from fabric_data_framework.deployment.contracts import (
    CIProvider,
    DeploymentMechanism,
    DeploymentProvenance,
    EnvironmentBindings,
    build_deployment_plan,
)
from fabric_data_framework.infrastructure import EnvironmentName


def config(dataset_id: str = "crm.customer") -> DatasetConfig:
    return DatasetConfig(
        dataset_id=dataset_id,
        source=SourceConfig(system="crm", object=f"dbo.{dataset_id.split('.')[-1]}"),
        target=TargetConfig(layer="silver", object=dataset_id.split(".")[-1]),
        load=LoadPolicy(
            capture_strategy=CaptureStrategy.WATERMARK,
            apply_strategy=ApplyStrategy.SCD2,
            business_key=("customer_id",),
            merge_key=("customer_id",),
            watermark=WatermarkConfig(column="modified_at", tie_breaker=("customer_id",)),
            tracked_columns=("name",),
        ),
        orchestration=OrchestrationPolicy(execution_group="crm_daily"),
        quality=DataQualityPolicy(policy_name="standard", quarantine_policy="reject_bad_rows"),
        reconciliation=ReconciliationPolicy(policy_name="row_accounting"),
    )


def test_config_bundle_hash_is_order_independent():
    first = config("crm.customer")
    second = config("crm.account")
    assert config_bundle_hash((first, second)) == config_bundle_hash((second, first))


def test_release_manifest_and_plan_keep_environment_bindings_outside_release_identity():
    manifest = build_release_manifest(
        domain="customer",
        domain_release_version="0.1.0",
        domain_git_sha="a" * 40,
        framework_version="0.3.0",
        configs=(config(),),
        config_schema_version=1,
        fabric_item_manifest_version="none-v1",
        build_id="build-7",
        generated_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    dev = EnvironmentBindings(
        profile_name="customer-dev", environment=EnvironmentName.DEV, domain="customer"
    )
    prod = EnvironmentBindings(
        profile_name="customer-prod", environment=EnvironmentName.PROD, domain="customer"
    )

    dev_plan = build_deployment_plan(manifest, dev)
    prod_plan = build_deployment_plan(manifest, prod)

    assert dev_plan.release_hash == prod_plan.release_hash == manifest.bundle.release_hash
    assert dev_plan.request.bundle == prod_plan.request.bundle
    assert dev_plan.bindings.profile_name != prod_plan.bindings.profile_name
    assert "watermark" in dev_plan.protected_environment_local_state_tables


def test_materialization_is_idempotent_and_preserves_runtime_watermark(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    configs = (config(),)
    first_hash = materialize_semantic_metadata(
        engine,
        configs=configs,
        domain="customer",
        domain_git_sha="b" * 40,
        framework_version="0.3.0",
    )
    with engine.begin() as connection:
        connection.execute(
            watermark.insert().values(
                dataset_id="crm.customer",
                committed_value="2026-08-28T00:00:00Z",
                committed_tie_breaker="C100",
                committed_dataset_run_id="run-1",
                version=1,
                created_at=datetime.now(timezone.utc),
                updated_at=None,
            )
        )

    second_hash = materialize_semantic_metadata(
        engine,
        configs=configs,
        domain="customer",
        domain_git_sha="c" * 40,
        framework_version="0.3.0",
    )

    with engine.connect() as connection:
        dataset_row = connection.execute(
            select(dataset).where(dataset.c.dataset_id == "crm.customer")
        ).mappings().one()
        watermark_row = connection.execute(
            select(watermark).where(watermark.c.dataset_id == "crm.customer")
        ).mappings().one()

    assert first_hash == second_hash
    assert dataset_row["domain_git_sha"] == "c" * 40
    assert watermark_row["committed_tie_breaker"] == "C100"
    assert watermark_row["version"] == 1


def test_deployment_history_is_environment_local_and_append_only(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'control.db'}")
    manifest = build_release_manifest(
        domain="customer",
        domain_release_version="0.1.0",
        domain_git_sha="d" * 40,
        framework_version="0.3.0",
        configs=(config(),),
        config_schema_version=1,
        fabric_item_manifest_version="none-v1",
        build_id="build-8",
    )
    provenance = DeploymentProvenance(
        environment=EnvironmentName.DEV,
        domain="customer",
        bundle=manifest.bundle,
        deployment_mechanism=DeploymentMechanism.DRY_RUN,
        ci_provider=CIProvider.GITHUB_ACTIONS,
        initiated_by="ci",
        status="SUCCEEDED",
    )
    record_deployment_history(engine, provenance)
    with engine.connect() as connection:
        rows = connection.execute(select(deployment_history)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["environment"] == "DEV"
    assert rows[0]["config_bundle_hash"] == manifest.bundle.config_bundle_hash


def test_release_tag_must_match_package_version():
    validate_release_tag("v0.3.0", "0.3.0")
    try:
        validate_release_tag("v0.3.1", "0.3.0")
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("mismatched tag should fail")
