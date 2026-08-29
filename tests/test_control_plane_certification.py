from datetime import datetime, timezone

from sqlalchemy import create_engine

from fabric_data_framework.control_plane import apply_baseline_schema, dataset
from fabric_data_framework.control_plane_certification import (
    AZURE_SQL_DATABASE_V1,
    FABRIC_SQL_DATABASE_V1,
    SQLITE_REFERENCE_V1,
    CertificationCheckStatus,
    ControlPlaneExternalEvidence,
    certify_control_plane_backend,
    get_control_plane_backend_profile,
)


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'certification.db'}")
    apply_baseline_schema(engine)
    return engine


def _checks(report):
    return {item.check_id: item for item in report.checks}


def test_sqlite_reference_can_pass_full_deterministic_conformance_without_becoming_production(
    tmp_path,
):
    engine = _engine(tmp_path)

    report = certify_control_plane_backend(
        engine,
        profile=SQLITE_REFERENCE_V1,
        run_conformance=True,
    )

    assert report.observed_dialect == "sqlite"
    assert report.schema_version == 4
    assert report.automated_checks_passed is True
    assert report.conformance_passed is True
    assert report.reference_certified is True
    assert report.production_certified is False

    checks = _checks(report)
    assert checks["transaction_rollback"].status is CertificationCheckStatus.PASS
    assert checks["target_operation_cas"].status is CertificationCheckStatus.PASS
    assert checks["cdc_checkpoint_cas"].status is CertificationCheckStatus.PASS
    assert (
        checks["external_production_eligibility"].status
        is CertificationCheckStatus.EXTERNAL_REQUIRED
    )


def test_certification_does_not_silently_migrate_an_empty_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")

    report = certify_control_plane_backend(
        engine,
        profile=SQLITE_REFERENCE_V1,
        run_conformance=True,
    )

    checks = _checks(report)
    assert report.schema_version == 0
    assert checks["schema_version"].status is CertificationCheckStatus.FAIL
    assert checks["required_tables"].status is CertificationCheckStatus.FAIL
    assert checks["migration_history"].status is CertificationCheckStatus.FAIL
    assert checks["transaction_rollback"].status is CertificationCheckStatus.NOT_RUN
    assert report.reference_certified is False


def test_production_candidate_profile_rejects_wrong_sqlalchemy_dialect(tmp_path):
    engine = _engine(tmp_path)
    evidence = ControlPlaneExternalEvidence(
        identity_access_control_reference="ticket:iam-1",
        network_security_reference="ticket:network-1",
        backup_restore_reference="drill:restore-1",
        availability_recovery_reference="drill:ha-1",
        monitoring_alerting_reference="runbook:monitoring-1",
        retention_governance_reference="policy:retention-1",
    )

    report = certify_control_plane_backend(
        engine,
        profile=FABRIC_SQL_DATABASE_V1,
        run_conformance=True,
        external_evidence=evidence,
    )

    checks = _checks(report)
    assert checks["dialect_profile"].status is CertificationCheckStatus.FAIL
    assert report.conformance_passed is False
    assert report.production_certified is False


def test_external_evidence_alone_cannot_promote_reference_store(tmp_path):
    engine = _engine(tmp_path)
    evidence = ControlPlaneExternalEvidence(
        identity_access_control_reference="ticket:iam-1",
        network_security_reference="ticket:network-1",
        backup_restore_reference="drill:restore-1",
        availability_recovery_reference="drill:ha-1",
        monitoring_alerting_reference="runbook:monitoring-1",
        retention_governance_reference="policy:retention-1",
    )

    report = certify_control_plane_backend(
        engine,
        profile=SQLITE_REFERENCE_V1,
        run_conformance=True,
        external_evidence=evidence,
    )

    assert report.reference_certified is True
    assert report.production_certified is False


def test_production_profile_requires_each_external_evidence_category(tmp_path):
    engine = _engine(tmp_path)

    report = certify_control_plane_backend(
        engine,
        profile=AZURE_SQL_DATABASE_V1,
        external_evidence=ControlPlaneExternalEvidence(
            identity_access_control_reference="ticket:iam-1"
        ),
    )

    checks = _checks(report)
    assert (
        checks["external_identity_access_control_reference"].status
        is CertificationCheckStatus.PASS
    )
    assert (
        checks["external_network_security_reference"].status
        is CertificationCheckStatus.EXTERNAL_REQUIRED
    )
    assert report.external_evidence_complete is False
    assert report.production_certified is False


def test_backend_profiles_are_explicit_and_not_generic_mssql_claims():
    assert get_control_plane_backend_profile("sqlite_reference_v1") == SQLITE_REFERENCE_V1
    assert (
        get_control_plane_backend_profile("fabric_sql_database_v1")
        == FABRIC_SQL_DATABASE_V1
    )
    assert (
        get_control_plane_backend_profile("azure_sql_database_v1")
        == AZURE_SQL_DATABASE_V1
    )
    assert FABRIC_SQL_DATABASE_V1.allowed_sqlalchemy_dialects == ("mssql",)
    assert FABRIC_SQL_DATABASE_V1.production_eligible is True


def test_conformance_probe_rows_are_cleaned_up(tmp_path):
    engine = _engine(tmp_path)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            dataset.insert().values(
                dataset_id="business.real_dataset",
                domain="business",
                source_system="source",
                source_object="object",
                target_layer="silver",
                target_object="target",
                enabled_default=True,
                criticality="HIGH",
                execution_group="daily",
                config_schema_version=1,
                config_hash="1" * 64,
                domain_git_sha="2" * 40,
                framework_version="0.4.0",
                created_at=now,
                updated_at=None,
            )
        )

    report = certify_control_plane_backend(
        engine,
        profile=SQLITE_REFERENCE_V1,
        run_conformance=True,
    )
    assert report.reference_certified is True

    with engine.connect() as connection:
        all_ids = set(connection.execute(dataset.select()).scalars().all())
    assert "business.real_dataset" in all_ids
    assert not any(value.startswith("__cert_") for value in all_ids)
