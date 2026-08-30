from uuid import uuid4

from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceSpec,
)
from fabric_data_framework.evidence.integration_runner import (
    ApprovedIntegrationRunnerConfig,
    IntegrationCheckPhysicalBinding,
    build_approved_integration_run_plan,
)


def test_pipeline_preflight_requires_token_and_control_plane_database_by_name():
    spec = IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="fabric.pipeline",
                kind=IntegrationEvidenceCheckKind.FABRIC_PIPELINE_RUN,
            ),
        ),
    )
    config = ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        fabric_access_token_env_var="FABRIC_ACCESS_TOKEN",
        control_plane_profile="fabric_sql_database_v1",
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
        bindings=(
            IntegrationCheckPhysicalBinding(
                check_id="fabric.pipeline",
                workspace_id=uuid4(),
                item_id=uuid4(),
            ),
        ),
    )

    missing_db = build_approved_integration_run_plan(
        config,
        spec,
        environ={"FABRIC_ACCESS_TOKEN": "secret-token"},
        allow_mutating_checks=True,
    )
    assert missing_db.ready is False
    assert missing_db.missing_runtime_env_vars == ("CONTROL_PLANE_DATABASE_URL",)
    assert {item.env_var for item in missing_db.runtime_requirements} == {
        "FABRIC_ACCESS_TOKEN",
        "CONTROL_PLANE_DATABASE_URL",
    }
    assert "secret-token" not in missing_db.model_dump_json()

    ready = build_approved_integration_run_plan(
        config,
        spec,
        environ={
            "FABRIC_ACCESS_TOKEN": "secret-token",
            "CONTROL_PLANE_DATABASE_URL": "mssql+pyodbc://runtime-secret",
        },
        allow_mutating_checks=True,
    )
    assert ready.ready is True
    rendered = ready.model_dump_json()
    assert "secret-token" not in rendered
    assert "mssql+pyodbc://runtime-secret" not in rendered
