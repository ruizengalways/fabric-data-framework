"""Production control-plane backend qualification and conformance evidence.

The framework owns relational semantics, not one physical database product. This
module makes the production boundary explicit: a backend profile states which SQL
family is eligible, deterministic conformance proves the framework's transaction/CAS
contracts, and separate external evidence proves service identity and enterprise
operational controls.

SQLite is intentionally a reference profile only. Passing every deterministic test
must never promote SQLite to a production-certified control plane.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable
from uuid import uuid4

from pydantic import Field, computed_field
from sqlalchemy import Engine, inspect, select

from .capture.cdc import build_cdc_checkpoint
from .config import FrozenModel
from .control_plane import (
    CONTROL_PLANE_MIGRATIONS,
    CONTROL_PLANE_SCHEMA_VERSION,
    cdc_checkpoint,
    current_schema_version,
    dataset,
    schema_migration_history,
    table_names,
    target_operation,
    target_operation_event,
)
from .control_plane_io import CDCCheckpointVersionConflict, commit_cdc_checkpoint
from .contracts.recovery import UnknownOutcomeResolution
from .runtime import StateCommitGate
from .target_operation_io import (
    TargetOperationVersionConflict,
    claim_target_operation,
    mark_target_operation_succeeded,
    mark_target_operation_unknown,
    reconcile_target_operation,
)
from .target_operations import TargetOperationIntent, fingerprint_semantic_payload


class ControlPlaneBackendClass(str, Enum):
    REFERENCE = "REFERENCE"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"


class CertificationCheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"
    EXTERNAL_REQUIRED = "EXTERNAL_REQUIRED"


class ControlPlaneBackendProfile(FrozenModel):
    profile_name: str = Field(min_length=1, max_length=128)
    backend_class: ControlPlaneBackendClass
    allowed_sqlalchemy_dialects: tuple[str, ...]
    production_eligible: bool
    description: str
    current_limitations: tuple[str, ...] = ()


SQLITE_REFERENCE_V1 = ControlPlaneBackendProfile(
    profile_name="sqlite_reference_v1",
    backend_class=ControlPlaneBackendClass.REFERENCE,
    allowed_sqlalchemy_dialects=("sqlite",),
    production_eligible=False,
    description="Deterministic local/CI reference store only; never production-certified.",
)

FABRIC_SQL_DATABASE_V1 = ControlPlaneBackendProfile(
    profile_name="fabric_sql_database_v1",
    backend_class=ControlPlaneBackendClass.PRODUCTION_CANDIDATE,
    allowed_sqlalchemy_dialects=("mssql",),
    production_eligible=True,
    description=(
        "Microsoft Fabric SQL Database candidate using the SQL/TDS relational contract. "
        "Real workspace security, networking, resilience and restore evidence is required."
    ),
    current_limitations=(
        "Product/tenant feature availability must be revalidated at deployment time.",
        "Do not infer private-network, key-management or HA controls from SQL compatibility alone.",
    ),
)

AZURE_SQL_DATABASE_V1 = ControlPlaneBackendProfile(
    profile_name="azure_sql_database_v1",
    backend_class=ControlPlaneBackendClass.PRODUCTION_CANDIDATE,
    allowed_sqlalchemy_dialects=("mssql",),
    production_eligible=True,
    description=(
        "Azure SQL Database candidate using the same framework SQL/TDS relational contract. "
        "Environment-specific security, networking, resilience and restore evidence is required."
    ),
)

CONTROL_PLANE_BACKEND_PROFILES = {
    profile.profile_name: profile
    for profile in (
        SQLITE_REFERENCE_V1,
        FABRIC_SQL_DATABASE_V1,
        AZURE_SQL_DATABASE_V1,
    )
}


class ControlPlaneExternalEvidence(FrozenModel):
    """References to provider/enterprise evidence deterministic DB tests cannot prove."""

    backend_service_identity_reference: str | None = Field(default=None, min_length=1)
    identity_access_control_reference: str | None = Field(default=None, min_length=1)
    network_security_reference: str | None = Field(default=None, min_length=1)
    backup_restore_reference: str | None = Field(default=None, min_length=1)
    availability_recovery_reference: str | None = Field(default=None, min_length=1)
    monitoring_alerting_reference: str | None = Field(default=None, min_length=1)
    retention_governance_reference: str | None = Field(default=None, min_length=1)

    @computed_field
    @property
    def complete(self) -> bool:
        return all(
            (
                self.backend_service_identity_reference,
                self.identity_access_control_reference,
                self.network_security_reference,
                self.backup_restore_reference,
                self.availability_recovery_reference,
                self.monitoring_alerting_reference,
                self.retention_governance_reference,
            )
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ControlPlaneExternalEvidence":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class ControlPlaneCertificationCheck(FrozenModel):
    check_id: str = Field(min_length=1, max_length=128)
    status: CertificationCheckStatus
    detail: str


class ControlPlaneCertificationReport(FrozenModel):
    profile: ControlPlaneBackendProfile
    observed_dialect: str
    schema_version: int
    conformance_requested: bool
    checks: tuple[ControlPlaneCertificationCheck, ...]
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def automated_checks_passed(self) -> bool:
        automated = [
            item
            for item in self.checks
            if item.status not in {CertificationCheckStatus.EXTERNAL_REQUIRED}
        ]
        return bool(automated) and all(
            item.status is CertificationCheckStatus.PASS for item in automated
        )

    @computed_field
    @property
    def conformance_passed(self) -> bool:
        required_ids = {
            "transaction_rollback",
            "target_operation_cas",
            "cdc_checkpoint_cas",
        }
        by_id = {item.check_id: item for item in self.checks}
        return all(
            by_id.get(check_id) is not None
            and by_id[check_id].status is CertificationCheckStatus.PASS
            for check_id in required_ids
        )

    @computed_field
    @property
    def external_evidence_complete(self) -> bool:
        external = [
            item for item in self.checks if item.check_id.startswith("external_")
        ]
        return bool(external) and all(
            item.status is CertificationCheckStatus.PASS for item in external
        )

    @computed_field
    @property
    def reference_certified(self) -> bool:
        return self.automated_checks_passed and self.conformance_passed

    @computed_field
    @property
    def production_certified(self) -> bool:
        return (
            self.profile.production_eligible
            and self.reference_certified
            and self.external_evidence_complete
        )


_REQUIRED_EXTERNAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("backend_service_identity_reference", "backend service identity evidence"),
    ("identity_access_control_reference", "identity/access-control evidence"),
    ("network_security_reference", "network security evidence"),
    ("backup_restore_reference", "backup/restore drill evidence"),
    ("availability_recovery_reference", "availability/recovery evidence"),
    ("monitoring_alerting_reference", "monitoring/alerting evidence"),
    ("retention_governance_reference", "retention/governance evidence"),
)


def get_control_plane_backend_profile(profile_name: str) -> ControlPlaneBackendProfile:
    try:
        return CONTROL_PLANE_BACKEND_PROFILES[profile_name]
    except KeyError as exc:
        raise ValueError(f"unknown control-plane backend profile: {profile_name}") from exc


def _check(
    check_id: str,
    status: CertificationCheckStatus,
    detail: str,
) -> ControlPlaneCertificationCheck:
    return ControlPlaneCertificationCheck(
        check_id=check_id,
        status=status,
        detail=detail,
    )


def _run_probe(
    check_id: str,
    probe: Callable[[], str],
) -> ControlPlaneCertificationCheck:
    try:
        detail = probe()
    except Exception as exc:  # certification reports fail-closed evidence
        return _check(
            check_id,
            CertificationCheckStatus.FAIL,
            f"{type(exc).__name__}: {exc}",
        )
    return _check(check_id, CertificationCheckStatus.PASS, detail)


def _transaction_rollback_probe(engine: Engine) -> str:
    marker = f"__cert_tx_{uuid4().hex}"
    now = datetime.now(timezone.utc)
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            dataset.insert().values(
                dataset_id=marker,
                domain="__certification__",
                source_system="__certification__",
                source_object="rollback_probe",
                target_layer="control",
                target_object="rollback_probe",
                enabled_default=False,
                criticality="LOW",
                execution_group="__certification__",
                config_schema_version=1,
                config_hash="a" * 64,
                domain_git_sha="b" * 40,
                framework_version="0.4.0",
                created_at=now,
                updated_at=None,
            )
        )
        transaction.rollback()
    with engine.connect() as connection:
        persisted = connection.execute(
            select(dataset.c.dataset_id).where(dataset.c.dataset_id == marker)
        ).first()
    if persisted is not None:
        raise RuntimeError("rolled-back control-plane mutation remained visible")
    return "transaction rollback removed the uncommitted certification marker"


def _seed_certification_dataset(engine: Engine, dataset_id: str) -> None:
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            dataset.insert().values(
                dataset_id=dataset_id,
                domain="__certification__",
                source_system="__certification__",
                source_object="cas_probe",
                target_layer="control",
                target_object="cas_probe",
                enabled_default=False,
                criticality="LOW",
                execution_group="__certification__",
                config_schema_version=1,
                config_hash="c" * 64,
                domain_git_sha="d" * 40,
                framework_version="0.4.0",
                created_at=now,
                updated_at=None,
            )
        )


def _cleanup_certification_dataset(engine: Engine, dataset_id: str) -> None:
    with engine.begin() as connection:
        operation_keys = connection.execute(
            select(target_operation.c.operation_key).where(
                target_operation.c.dataset_id == dataset_id
            )
        ).scalars().all()
        if operation_keys:
            connection.execute(
                target_operation_event.delete().where(
                    target_operation_event.c.operation_key.in_(tuple(operation_keys))
                )
            )
        connection.execute(
            target_operation.delete().where(target_operation.c.dataset_id == dataset_id)
        )
        connection.execute(
            cdc_checkpoint.delete().where(cdc_checkpoint.c.dataset_id == dataset_id)
        )
        connection.execute(dataset.delete().where(dataset.c.dataset_id == dataset_id))


def _target_operation_cas_probe(engine: Engine) -> str:
    dataset_id = f"__cert_target_{uuid4().hex}"
    _seed_certification_dataset(engine, dataset_id)
    try:
        intent = TargetOperationIntent(
            dataset_id=dataset_id,
            operation_kind="CERTIFICATION_PROBE",
            target_reference="control.certification_probe",
            effective_config_hash="e" * 64,
            input_fingerprint=fingerprint_semantic_payload({"probe": dataset_id}),
        )
        first_run = uuid4()
        claim = claim_target_operation(
            engine,
            intent=intent,
            dataset_run_id=first_run,
            attempt=1,
        )
        unknown = mark_target_operation_unknown(
            engine,
            operation_key=intent.operation_key,
            expected_version=claim.record.version,
            dataset_run_id=first_run,
            attempt=1,
            error_message="certification ambiguous outcome",
        )
        try:
            mark_target_operation_succeeded(
                engine,
                operation_key=intent.operation_key,
                expected_version=claim.record.version,
                dataset_run_id=first_run,
                attempt=1,
            )
        except TargetOperationVersionConflict:
            pass
        else:
            raise RuntimeError("stale target-operation writer was not rejected")

        reconciled = reconcile_target_operation(
            engine,
            operation_key=intent.operation_key,
            expected_version=unknown.version,
            resolution=UnknownOutcomeResolution.COMMITTED,
            dataset_run_id=uuid4(),
            attempt=2,
            outcome_reference="certification:committed",
        )
        if reconciled.status.value != "SUCCEEDED":
            raise RuntimeError(
                "target-operation reconciliation did not converge to SUCCEEDED"
            )
        return "stale expected-version writer was rejected and reconciliation CAS succeeded"
    finally:
        _cleanup_certification_dataset(engine, dataset_id)


def _cdc_checkpoint_cas_probe(engine: Engine) -> str:
    dataset_id = f"__cert_cdc_{uuid4().hex}"
    _seed_certification_dataset(engine, dataset_id)
    gate = StateCommitGate(
        target_committed=True,
        reconciliation_required=True,
        reconciliation_passed=True,
    )
    try:
        first = commit_cdc_checkpoint(
            engine,
            dataset_id=dataset_id,
            checkpoint=build_cdc_checkpoint({"certification:0": (10, 0)}),
            dataset_run_id=uuid4(),
            expected_version=0,
            gate=gate,
        )
        second = commit_cdc_checkpoint(
            engine,
            dataset_id=dataset_id,
            checkpoint=build_cdc_checkpoint({"certification:0": (11, 0)}),
            dataset_run_id=uuid4(),
            expected_version=first.version,
            gate=gate,
        )
        try:
            commit_cdc_checkpoint(
                engine,
                dataset_id=dataset_id,
                checkpoint=build_cdc_checkpoint({"certification:0": (12, 0)}),
                dataset_run_id=uuid4(),
                expected_version=first.version,
                gate=gate,
            )
        except CDCCheckpointVersionConflict:
            pass
        else:
            raise RuntimeError("stale CDC checkpoint writer was not rejected")
        if second.version != 2:
            raise RuntimeError("CDC checkpoint version did not advance deterministically")
        return "CDC checkpoint expected-version CAS rejected a stale writer"
    finally:
        _cleanup_certification_dataset(engine, dataset_id)


def certify_control_plane_backend(
    engine: Engine,
    *,
    profile: ControlPlaneBackendProfile,
    run_conformance: bool = False,
    external_evidence: ControlPlaneExternalEvidence | None = None,
) -> ControlPlaneCertificationReport:
    """Evaluate one already-migrated control-plane database.

    This function intentionally does not call ``apply_baseline_schema`` before static
    checks. Production certification must not hide an unapplied migration by silently
    changing the database. Run ``control-plane-migrate`` as an explicit deployment
    step first.

    ``run_conformance`` performs temporary writes and must only be used against a
    database/environment approved for certification probes. Probe rows use reserved
    ``__cert_*`` dataset IDs and are cleaned up after each test.
    """

    dialect = engine.dialect.name
    checks: list[ControlPlaneCertificationCheck] = []

    checks.append(
        _check(
            "dialect_profile",
            CertificationCheckStatus.PASS
            if dialect in profile.allowed_sqlalchemy_dialects
            else CertificationCheckStatus.FAIL,
            f"observed dialect {dialect!r}; allowed={profile.allowed_sqlalchemy_dialects}",
        )
    )

    schema_version = current_schema_version(engine)
    checks.append(
        _check(
            "schema_version",
            CertificationCheckStatus.PASS
            if schema_version == CONTROL_PLANE_SCHEMA_VERSION
            else CertificationCheckStatus.FAIL,
            f"observed={schema_version}, required={CONTROL_PLANE_SCHEMA_VERSION}",
        )
    )

    observed_tables = frozenset(inspect(engine).get_table_names())
    missing_tables = sorted(table_names() - observed_tables)
    checks.append(
        _check(
            "required_tables",
            CertificationCheckStatus.PASS
            if not missing_tables
            else CertificationCheckStatus.FAIL,
            "all framework tables are present"
            if not missing_tables
            else f"missing tables: {', '.join(missing_tables)}",
        )
    )

    migration_versions: set[int] = set()
    if "schema_migration_history" in observed_tables:
        with engine.connect() as connection:
            migration_versions = set(
                connection.execute(
                    select(schema_migration_history.c.version)
                ).scalars().all()
            )
    required_versions = {version for version, _ in CONTROL_PLANE_MIGRATIONS}
    missing_versions = sorted(required_versions - migration_versions)
    checks.append(
        _check(
            "migration_history",
            CertificationCheckStatus.PASS
            if not missing_versions
            else CertificationCheckStatus.FAIL,
            "all declared migrations are recorded"
            if not missing_versions
            else f"missing migration versions: {missing_versions}",
        )
    )

    static_ok = all(item.status is CertificationCheckStatus.PASS for item in checks)
    for check_id, probe in (
        ("transaction_rollback", lambda: _transaction_rollback_probe(engine)),
        ("target_operation_cas", lambda: _target_operation_cas_probe(engine)),
        ("cdc_checkpoint_cas", lambda: _cdc_checkpoint_cas_probe(engine)),
    ):
        if run_conformance and static_ok:
            checks.append(_run_probe(check_id, probe))
        else:
            checks.append(
                _check(
                    check_id,
                    CertificationCheckStatus.NOT_RUN,
                    "run_conformance was not requested"
                    if not run_conformance
                    else "static certification checks failed; destructive probe skipped",
                )
            )

    if profile.production_eligible:
        for field_name, label in _REQUIRED_EXTERNAL_FIELDS:
            reference = (
                getattr(external_evidence, field_name)
                if external_evidence is not None
                else None
            )
            checks.append(
                _check(
                    f"external_{field_name}",
                    CertificationCheckStatus.PASS
                    if reference
                    else CertificationCheckStatus.EXTERNAL_REQUIRED,
                    f"{label}: {reference}" if reference else f"{label} is required",
                )
            )
    else:
        checks.append(
            _check(
                "external_production_eligibility",
                CertificationCheckStatus.EXTERNAL_REQUIRED,
                "reference backend profile is explicitly ineligible for production certification",
            )
        )

    return ControlPlaneCertificationReport(
        profile=profile,
        observed_dialect=dialect,
        schema_version=schema_version,
        conformance_requested=run_conformance,
        checks=tuple(checks),
    )


__all__ = [
    "AZURE_SQL_DATABASE_V1",
    "CONTROL_PLANE_BACKEND_PROFILES",
    "FABRIC_SQL_DATABASE_V1",
    "SQLITE_REFERENCE_V1",
    "CertificationCheckStatus",
    "ControlPlaneBackendClass",
    "ControlPlaneBackendProfile",
    "ControlPlaneCertificationCheck",
    "ControlPlaneCertificationReport",
    "ControlPlaneExternalEvidence",
    "certify_control_plane_backend",
    "get_control_plane_backend_profile",
]
