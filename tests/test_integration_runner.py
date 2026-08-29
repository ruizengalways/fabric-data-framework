from uuid import uuid4

import pytest
from pydantic import ValidationError

from fabric_data_framework.infrastructure import EnvironmentName
from fabric_data_framework.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceSpec,
)
from fabric_data_framework.integration_runner import (
    ApprovedIntegrationRunnerConfig,
    IntegrationCheckPhysicalBinding,
    build_approved_integration_run_plan,
)


RELEASE_HASH = "a" * 64


def _spec(*checks):
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash=RELEASE_HASH,
        checks=checks,
    )


def _config(*bindings, **updates):
    values = {
        "environment": EnvironmentName.DEV,
        "domain": "customer",
        "framework_version": "0.4.0",
        "release_hash": RELEASE_HASH,
        "fabric_access_token_env_var": "FABRIC_ACCESS_TOKEN",
        "control_plane_profile": "fabric_sql_database_v1",
        "control_plane_database_url_env_var": "FABRIC_CONTROL_PLANE_DATABASE_URL",
        "warehouse_database_url_env_var": "FABRIC_WAREHOUSE_DATABASE_URL",
        "bindings": bindings,
    }
    values.update(updates)
    return ApprovedIntegrationRunnerConfig(**values)


def test_read_only_preflight_is_ready_with_token_and_exact_item_binding():
    workspace_id = uuid4()
    item_id = uuid4()
    spec = _spec(
        IntegrationEvidenceCheckSpec(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
            required=True,
        )
    )
    config = _config(
        IntegrationCheckPhysicalBinding(
            check_id="fabric.item.read",
            workspace_id=workspace_id,
            item_id=item_id,
        )
    )

    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ={"FABRIC_ACCESS_TOKEN": "ephemeral-secret-value"},
    )

    assert plan.ready is True
    assert plan.mutating_check_ids == ()
    assert plan.runtime_requirements[0].env_var == "FABRIC_ACCESS_TOKEN"
    assert plan.runtime_requirements[0].present is True
    rendered = plan.model_dump_json()
    assert "ephemeral-secret-value" not in rendered


def test_required_mutating_checks_require_explicit_authorization():
    workspace_id = uuid4()
    item_id = uuid4()
    spec = _spec(
        IntegrationEvidenceCheckSpec(
            check_id="fabric.pipeline",
            kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            required=True,
        ),
        IntegrationEvidenceCheckSpec(
            check_id="control.cert",
            kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            required=True,
        ),
        IntegrationEvidenceCheckSpec(
            check_id="warehouse.commit",
            kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
            required=True,
        ),
    )
    config = _config(
        IntegrationCheckPhysicalBinding(
            check_id="fabric.pipeline",
            workspace_id=workspace_id,
            item_id=item_id,
        )
    )
    environ = {
        "FABRIC_ACCESS_TOKEN": "secret-token",
        "FABRIC_CONTROL_PLANE_DATABASE_URL": "mssql+pyodbc://secret",
        "FABRIC_WAREHOUSE_DATABASE_URL": "mssql+pyodbc://secret",
    }

    blocked = build_approved_integration_run_plan(config, spec, environ=environ)
    assert blocked.ready is False
    assert blocked.missing_runtime_env_vars == ()
    assert set(blocked.mutating_check_ids) == {
        "fabric.pipeline",
        "control.cert",
        "warehouse.commit",
    }
    assert "secret-token" not in blocked.model_dump_json()
    assert "mssql+pyodbc://secret" not in blocked.model_dump_json()

    approved = build_approved_integration_run_plan(
        config,
        spec,
        environ=environ,
        allow_mutating_checks=True,
    )
    assert approved.ready is True


def test_missing_runtime_values_are_reported_by_name_only():
    spec = _spec(
        IntegrationEvidenceCheckSpec(
            check_id="control.cert",
            kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            required=True,
        )
    )
    config = _config()

    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ={},
        allow_mutating_checks=True,
    )

    assert plan.ready is False
    assert plan.missing_runtime_env_vars == ("FABRIC_CONTROL_PLANE_DATABASE_URL",)


def test_required_fabric_item_check_requires_physical_binding():
    spec = _spec(
        IntegrationEvidenceCheckSpec(
            check_id="fabric.copy",
            kind=IntegrationEvidenceCheckKind.FABRIC_COPY_JOB_CAPTURE,
            required=True,
        )
    )
    config = _config()

    with pytest.raises(ValueError, match="requires a physical binding"):
        build_approved_integration_run_plan(
            config,
            spec,
            environ={"FABRIC_ACCESS_TOKEN": "secret"},
            allow_mutating_checks=True,
        )


def test_binding_not_declared_in_spec_is_rejected():
    spec = _spec(
        IntegrationEvidenceCheckSpec(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
        )
    )
    config = _config(
        IntegrationCheckPhysicalBinding(
            check_id="fabric.item.typo",
            workspace_id=uuid4(),
            item_id=uuid4(),
        ),
        IntegrationCheckPhysicalBinding(
            check_id="fabric.item.read",
            workspace_id=uuid4(),
            item_id=uuid4(),
        ),
    )

    with pytest.raises(ValueError, match="not declared"):
        build_approved_integration_run_plan(
            config,
            spec,
            environ={"FABRIC_ACCESS_TOKEN": "secret"},
        )


def test_config_and_evidence_spec_must_be_same_exact_release():
    spec = _spec(
        IntegrationEvidenceCheckSpec(
            check_id="fabric.item.read",
            kind=IntegrationEvidenceCheckKind.FABRIC_ITEM_READ,
        )
    )
    config = _config(
        IntegrationCheckPhysicalBinding(
            check_id="fabric.item.read",
            workspace_id=uuid4(),
            item_id=uuid4(),
        ),
        release_hash="b" * 64,
    )

    with pytest.raises(ValueError, match="release hash differ"):
        build_approved_integration_run_plan(
            config,
            spec,
            environ={"FABRIC_ACCESS_TOKEN": "secret"},
        )


def test_runtime_secret_fields_accept_only_environment_variable_names():
    with pytest.raises(ValidationError):
        _config(fabric_access_token_env_var="https://example.test?sig=secret")


def test_control_plane_profile_and_runtime_url_name_are_declared_together():
    with pytest.raises(ValidationError, match="requires control_plane_database_url_env_var"):
        ApprovedIntegrationRunnerConfig(
            environment=EnvironmentName.DEV,
            domain="customer",
            framework_version="0.4.0",
            release_hash=RELEASE_HASH,
            control_plane_profile="fabric_sql_database_v1",
        )
