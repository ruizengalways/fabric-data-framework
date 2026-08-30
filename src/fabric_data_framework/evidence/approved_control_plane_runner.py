"""Exact-release approved control-plane certification execution.

This module is the environment-facing bridge between the credential-free approved
integration runner configuration and the existing control-plane certification logic.
Database URLs are read only from the configured runtime environment-variable name and
are never copied into the returned plan, report wrapper or integration manifest.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path

from sqlalchemy import Engine, create_engine

from ..control_plane_certification import (
    ControlPlaneBackendProfile,
    ControlPlaneCertificationReport,
    ControlPlaneExternalEvidence,
    certify_control_plane_backend,
    get_control_plane_backend_profile,
)
from .integration_checks import build_control_plane_certification_check_result
from .integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    run_integration_evidence,
)
from .integration_runner import (
    ApprovedIntegrationRunPlan,
    ApprovedIntegrationRunnerConfig,
    build_approved_integration_run_plan,
)
from ..retained_evidence_safety import assert_safe_retained_text


EngineFactory = Callable[[str], Engine]
CertificationFunction = Callable[..., ControlPlaneCertificationReport]


@dataclass(frozen=True)
class ApprovedControlPlaneCertificationExecution:
    """Credential-free result wrapper for one staged certification execution."""

    plan: ApprovedIntegrationRunPlan
    manifest: IntegrationEvidenceManifest
    report: ControlPlaneCertificationReport | None


def _require_safe_external_evidence(evidence: ControlPlaneExternalEvidence) -> None:
    if not evidence.complete:
        raise ValueError(
            "approved production control-plane certification requires complete external evidence"
        )
    for field_name in (
        "backend_service_identity_reference",
        "identity_access_control_reference",
        "network_security_reference",
        "backup_restore_reference",
        "availability_recovery_reference",
        "monitoring_alerting_reference",
        "retention_governance_reference",
    ):
        value = getattr(evidence, field_name)
        if value is None:
            raise ValueError(f"missing control-plane external evidence field {field_name}")
        assert_safe_retained_text(value, field_name)


def _require_safe_report(report: ControlPlaneCertificationReport) -> None:
    for check in report.checks:
        assert_safe_retained_text(
            check.detail,
            f"control-plane certification check {check.check_id!r} detail",
        )


def _profile_for_approved_run(
    config: ApprovedIntegrationRunnerConfig,
) -> ControlPlaneBackendProfile:
    if config.control_plane_profile is None:
        raise ValueError("approved control-plane certification requires control_plane_profile")
    profile = get_control_plane_backend_profile(config.control_plane_profile)
    if not profile.production_eligible:
        raise ValueError(
            "approved control-plane evidence runner requires a production-eligible backend profile"
        )
    return profile


def execute_approved_control_plane_certification(
    *,
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
    check_id: str,
    environ: Mapping[str, str],
    external_evidence: ControlPlaneExternalEvidence,
    evidence_references: Iterable[str],
    allow_conformance_writes: bool,
    engine_factory: EngineFactory = create_engine,
    certifier: CertificationFunction = certify_control_plane_backend,
) -> ApprovedControlPlaneCertificationExecution:
    """Run exactly one approved production control-plane certification check.

    The function first validates exact release identity, selected check kind, runtime
    prerequisite *presence* and explicit mutation authorization. Only after that gate
    passes is the configured database URL value read from ``environ``.

    The certification routine never migrates the database. It executes the existing
    deterministic rollback/CAS probes with ``run_conformance=True`` and requires a
    production-eligible profile plus complete external evidence.
    """

    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ=environ,
        selected_check_ids=(check_id,),
        allow_mutating_checks=allow_conformance_writes,
    )
    if not plan.ready:
        reasons: list[str] = []
        if plan.missing_runtime_env_vars:
            reasons.append(
                "missing runtime env vars=" + ",".join(plan.missing_runtime_env_vars)
            )
        if plan.mutating_check_ids and not plan.mutating_checks_authorized:
            reasons.append("control-plane conformance writes not explicitly authorized")
        raise ValueError("approved control-plane certification preflight is not ready: " + "; ".join(reasons))

    check_by_id = {item.check_id: item for item in spec.checks}
    selected = check_by_id[check_id]
    if selected.kind is not IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION:
        raise ValueError(
            "approved control-plane certification runner requires CONTROL_PLANE_CERTIFICATION check kind"
        )

    profile = _profile_for_approved_run(config)
    _require_safe_external_evidence(external_evidence)
    if config.control_plane_database_url_env_var is None:
        raise ValueError("approved control-plane certification requires database URL env-var name")

    # Read the secret-bearing runtime value only after exact-release preflight and
    # explicit conformance-write authorization have passed.
    database_url = environ[config.control_plane_database_url_env_var]
    references = tuple(evidence_references)
    for index, reference in enumerate(references):
        assert_safe_retained_text(reference, f"evidence_references[{index}]")

    retained_report: ControlPlaneCertificationReport | None = None

    def runner():
        nonlocal retained_report
        engine = engine_factory(database_url)
        try:
            candidate = certifier(
                engine,
                profile=profile,
                run_conformance=True,
                external_evidence=external_evidence,
            )
            _require_safe_report(candidate)
            retained_report = candidate
            return build_control_plane_certification_check_result(
                check_id=check_id,
                report=candidate,
                evidence_references=references,
                require_production_certified=True,
            )
        finally:
            engine.dispose()

    manifest = run_integration_evidence(spec, runners={check_id: runner})
    return ApprovedControlPlaneCertificationExecution(
        plan=plan,
        manifest=manifest,
        report=retained_report,
    )


def write_control_plane_certification_report(
    report: ControlPlaneCertificationReport,
    path: str | Path,
) -> None:
    """Write an already safety-validated certification report."""

    _require_safe_report(report)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "ApprovedControlPlaneCertificationExecution",
    "execute_approved_control_plane_certification",
    "write_control_plane_certification_report",
]
