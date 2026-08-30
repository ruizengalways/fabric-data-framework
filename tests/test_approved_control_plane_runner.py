from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
import json

import pytest
from sqlalchemy import create_engine

from fabric_data_framework.evidence.approved_control_plane_runner import (
    execute_approved_control_plane_certification,
    write_control_plane_certification_report,
)
from fabric_data_framework.control_plane_certification import (
    CertificationCheckStatus,
    ControlPlaneCertificationCheck,
    ControlPlaneCertificationReport,
    ControlPlaneExternalEvidence,
    FABRIC_SQL_DATABASE_V1,
)
from fabric_data_framework.infrastructure import EnvironmentName
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckSpec,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
)
from fabric_data_framework.evidence.integration_runner import ApprovedIntegrationRunnerConfig


NOW = datetime(2026, 8, 29, 13, 30, tzinfo=timezone.utc)
SECRET_URL = "mssql+pyodbc://user:s3cr3t@example.invalid/control"


class TrackingEnvironment(Mapping[str, str]):
    def __init__(self, values: dict[str, str]):
        self.values = values
        self.getitem_calls: list[str] = []
        self.presence_checks: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.getitem_calls.append(key)
        return self.values[key]

    def get(self, key: str, default=None):
        self.presence_checks.append(key)
        return "present" if key in self.values and self.values[key].strip() else default

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


def _spec(kind=IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION):
    return IntegrationEvidenceSpec(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        checks=(
            IntegrationEvidenceCheckSpec(
                check_id="control-plane.certify",
                kind=kind,
            ),
            IntegrationEvidenceCheckSpec(
                check_id="optional.kafka",
                kind=IntegrationEvidenceCheckKind.KAFKA_PROVIDER,
                required=False,
            ),
        ),
    )


def _config(profile="fabric_sql_database_v1"):
    return ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName.DEV,
        domain="customer",
        framework_version="0.4.0",
        release_hash="a" * 64,
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
        control_plane_profile=profile,
    )


def _external(**updates):
    values = {
        "backend_service_identity_reference": "inventory:fabric-sql-dev",
        "identity_access_control_reference": "ticket:iam-1",
        "network_security_reference": "ticket:network-1",
        "backup_restore_reference": "drill:restore-1",
        "availability_recovery_reference": "drill:ha-1",
        "monitoring_alerting_reference": "runbook:monitoring-1",
        "retention_governance_reference": "policy:retention-1",
    }
    values.update(updates)
    return ControlPlaneExternalEvidence(**values)


def _passing_report(detail="certification probe passed"):
    checks = [
        ControlPlaneCertificationCheck(
            check_id=check_id,
            status=CertificationCheckStatus.PASS,
            detail=detail,
        )
        for check_id in (
            "dialect_profile",
            "schema_version",
            "required_tables",
            "migration_history",
            "transaction_rollback",
            "target_operation_cas",
            "cdc_checkpoint_cas",
        )
    ]
    for field_name in (
        "backend_service_identity_reference",
        "identity_access_control_reference",
        "network_security_reference",
        "backup_restore_reference",
        "availability_recovery_reference",
        "monitoring_alerting_reference",
        "retention_governance_reference",
    ):
        checks.append(
            ControlPlaneCertificationCheck(
                check_id=f"external_{field_name}",
                status=CertificationCheckStatus.PASS,
                detail=f"retained reference for {field_name}",
            )
        )
    return ControlPlaneCertificationReport(
        profile=FABRIC_SQL_DATABASE_V1,
        observed_dialect="mssql",
        schema_version=4,
        conformance_requested=True,
        checks=tuple(checks),
        evaluated_at=NOW,
    )


def test_authorization_gate_prevents_reading_database_url_value():
    environ = TrackingEnvironment({"CONTROL_PLANE_DATABASE_URL": SECRET_URL})

    with pytest.raises(ValueError, match="not explicitly authorized"):
        execute_approved_control_plane_certification(
            config=_config(),
            spec=_spec(),
            check_id="control-plane.certify",
            environ=environ,
            external_evidence=_external(),
            evidence_references=("artifact:certification-report",),
            allow_conformance_writes=False,
        )

    assert environ.presence_checks == ["CONTROL_PLANE_DATABASE_URL"]
    assert environ.getitem_calls == []


def test_wrong_check_kind_is_rejected_before_database_url_value_is_read():
    environ = TrackingEnvironment({"CONTROL_PLANE_DATABASE_URL": SECRET_URL})

    with pytest.raises(ValueError, match="CONTROL_PLANE_CERTIFICATION"):
        execute_approved_control_plane_certification(
            config=_config(),
            spec=_spec(IntegrationEvidenceCheckKind.KAFKA_PROVIDER),
            check_id="control-plane.certify",
            environ=environ,
            external_evidence=_external(),
            evidence_references=("artifact:certification-report",),
            allow_conformance_writes=True,
        )

    assert environ.getitem_calls == []


def test_reference_profile_is_rejected_before_database_url_value_is_read():
    environ = TrackingEnvironment({"CONTROL_PLANE_DATABASE_URL": SECRET_URL})

    with pytest.raises(ValueError, match="production-eligible"):
        execute_approved_control_plane_certification(
            config=_config("sqlite_reference_v1"),
            spec=_spec(),
            check_id="control-plane.certify",
            environ=environ,
            external_evidence=_external(),
            evidence_references=("artifact:certification-report",),
            allow_conformance_writes=True,
        )

    assert environ.getitem_calls == []


def test_incomplete_external_evidence_is_rejected_before_database_url_value_is_read():
    environ = TrackingEnvironment({"CONTROL_PLANE_DATABASE_URL": SECRET_URL})

    with pytest.raises(ValueError, match="complete external evidence"):
        execute_approved_control_plane_certification(
            config=_config(),
            spec=_spec(),
            check_id="control-plane.certify",
            environ=environ,
            external_evidence=_external(network_security_reference=None),
            evidence_references=("artifact:certification-report",),
            allow_conformance_writes=True,
        )

    assert environ.getitem_calls == []


def test_success_returns_production_pass_partial_manifest_without_retaining_database_url():
    environ = TrackingEnvironment({"CONTROL_PLANE_DATABASE_URL": SECRET_URL})
    observed_urls: list[str] = []

    def engine_factory(url: str):
        observed_urls.append(url)
        return create_engine("sqlite://")

    def certifier(engine, *, profile, run_conformance, external_evidence):
        assert profile is FABRIC_SQL_DATABASE_V1
        assert run_conformance is True
        assert external_evidence.complete is True
        return _passing_report()

    execution = execute_approved_control_plane_certification(
        config=_config(),
        spec=_spec(),
        check_id="control-plane.certify",
        environ=environ,
        external_evidence=_external(),
        evidence_references=("artifact:certification-report",),
        allow_conformance_writes=True,
        engine_factory=engine_factory,
        certifier=certifier,
    )

    assert observed_urls == [SECRET_URL]
    assert environ.getitem_calls == ["CONTROL_PLANE_DATABASE_URL"]
    assert execution.report is not None
    assert execution.report.production_certified is True
    result = execution.manifest.results[0]
    assert result.status is IntegrationEvidenceStatus.PASS
    assert execution.manifest.results[1].status is IntegrationEvidenceStatus.NOT_RUN
    retained = json.dumps(
        {
            "plan": execution.plan.model_dump(mode="json"),
            "manifest": execution.manifest.model_dump(mode="json"),
            "report": execution.report.model_dump(mode="json"),
        }
    )
    assert SECRET_URL not in retained
    assert "s3cr3t" not in retained


def test_driver_exception_becomes_sanitized_fail_and_no_report_is_retained():
    environ = TrackingEnvironment({"CONTROL_PLANE_DATABASE_URL": SECRET_URL})

    def engine_factory(url: str):
        raise RuntimeError(f"failed to connect to {url}; password=super-secret")

    execution = execute_approved_control_plane_certification(
        config=_config(),
        spec=_spec(),
        check_id="control-plane.certify",
        environ=environ,
        external_evidence=_external(),
        evidence_references=("artifact:certification-report",),
        allow_conformance_writes=True,
        engine_factory=engine_factory,
    )

    result = execution.manifest.results[0]
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert result.detail == "integration check runner raised RuntimeError"
    assert execution.report is None
    rendered = execution.manifest.model_dump_json()
    assert SECRET_URL not in rendered
    assert "super-secret" not in rendered


def test_unsafe_certification_report_is_rejected_before_retention():
    environ = TrackingEnvironment({"CONTROL_PLANE_DATABASE_URL": SECRET_URL})

    def engine_factory(url: str):
        return create_engine("sqlite://")

    def certifier(engine, *, profile, run_conformance, external_evidence):
        return _passing_report(detail="Authorization: Bearer abc.def")

    execution = execute_approved_control_plane_certification(
        config=_config(),
        spec=_spec(),
        check_id="control-plane.certify",
        environ=environ,
        external_evidence=_external(),
        evidence_references=("artifact:certification-report",),
        allow_conformance_writes=True,
        engine_factory=engine_factory,
        certifier=certifier,
    )

    assert execution.report is None
    result = execution.manifest.results[0]
    assert result.status is IntegrationEvidenceStatus.FAIL
    assert result.detail == "integration check runner raised ValueError"
    assert "Bearer abc.def" not in execution.manifest.model_dump_json()


def test_report_writer_rejects_secret_bearing_detail(tmp_path):
    path = tmp_path / "report.json"
    report = _passing_report(detail="https://example.test/?sig=secret")

    with pytest.raises(ValueError, match="credential material"):
        write_control_plane_certification_report(report, path)

    assert not path.exists()
