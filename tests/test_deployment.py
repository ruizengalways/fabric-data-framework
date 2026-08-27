from fabric_data_framework.deployment import (
    CIProvider,
    ControlPlaneRecordClass,
    DeploymentMechanism,
    DeploymentProvenance,
    DeploymentRequest,
    EnvironmentBindings,
    ReleaseBundleIdentity,
    ReleaseManifest,
    build_deployment_plan,
    classify_control_plane_record,
)
from fabric_data_framework.infrastructure import EnvironmentName


def release_bundle() -> ReleaseBundleIdentity:
    return ReleaseBundleIdentity(
        domain_release_version="1.0.0",
        domain_git_sha="a" * 40,
        framework_version="0.3.0",
        config_bundle_hash="b" * 64,
        config_schema_version=1,
        control_plane_schema_version=1,
        fabric_item_manifest_version="1",
        build_id="build-42",
    )


def test_same_release_identity_is_reused_across_environments():
    bundle = release_bundle()
    dev = DeploymentRequest(
        target_environment=EnvironmentName.DEV,
        bundle=bundle,
        logical_binding_profile="customer-dev",
    )
    prod = DeploymentRequest(
        target_environment=EnvironmentName.PROD,
        bundle=bundle,
        logical_binding_profile="customer-prod",
    )
    assert dev.bundle.release_hash == prod.bundle.release_hash
    assert dev.bundle == prod.bundle
    assert dev.logical_binding_profile != prod.logical_binding_profile


def test_runtime_state_is_classified_as_environment_local_not_promotable():
    assert classify_control_plane_record("dataset") is ControlPlaneRecordClass.RELEASE_DEFINITION
    assert classify_control_plane_record("watermark") is ControlPlaneRecordClass.ENVIRONMENT_LOCAL_STATE
    assert (
        classify_control_plane_record("runtime_override")
        is ControlPlaneRecordClass.ENVIRONMENT_LOCAL_STATE
    )


def test_deployment_provenance_records_provider_and_mechanism():
    provenance = DeploymentProvenance(
        environment=EnvironmentName.UAT,
        domain="customer",
        bundle=release_bundle(),
        deployment_mechanism=DeploymentMechanism.FABRIC_DEPLOYMENT_PIPELINE,
        ci_provider=CIProvider.GITHUB_ACTIONS,
        initiated_by="release-bot",
        status="SUCCEEDED",
    )
    assert provenance.bundle.release_hash
    assert provenance.environment is EnvironmentName.UAT


def test_plan_protects_environment_local_state():
    manifest = ReleaseManifest(domain="customer", bundle=release_bundle())
    bindings = EnvironmentBindings(
        profile_name="customer-prod",
        environment=EnvironmentName.PROD,
        domain="customer",
    )
    plan = build_deployment_plan(manifest, bindings)
    assert plan.request.bundle == manifest.bundle
    assert "dataset_run" in plan.protected_environment_local_state_tables
