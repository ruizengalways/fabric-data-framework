"""Unified one-call certification orchestrator for real Fabric environments.

The public facade preserves the operator API while typed internal stages own exact
identity loading, authorization-gated execution, evidence assembly, and reporting.
"""

from __future__ import annotations

from fabric_data_framework.contracts.temporal import utc_now

from collections.abc import Mapping
from pathlib import Path

from .bounded import run_bounded_certification
from .models import UnifiedCertificationReport
from .unified_stages import (
    CertificationAuthorizations,
    UnifiedCertificationRequest,
    run_unified_certification,
)


def certify(  # noqa: PLR0913 - stable operator-facing certification facade
    *,
    spark,
    candidate_manifest_path: str | Path,
    wheel_path: str | Path,
    output_dir: str | Path,
    environment: str = "DEV",
    lakehouse_base_path: str = "Files/framework_cert",
    integration_inputs_root: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    auto_notebook_token: bool = True,
    allow_control_plane_migration: bool = False,
    allow_control_plane_writes: bool = False,
    allow_pipeline_execution: bool = False,
    allow_capture_execution: bool = False,
    allow_warehouse_execution: bool = False,
    allow_warehouse_fault_injection: bool = False,
    allow_warehouse_session_termination: bool = False,
    allow_business_path_execution: bool = False,
    allow_scenario_mutation: bool = False,
) -> UnifiedCertificationReport:
    """Run bounded checks and optional framework-owned live integration gates."""

    started_at = utc_now()
    request = UnifiedCertificationRequest(
        spark=spark,
        candidate_manifest_path=Path(candidate_manifest_path),
        wheel_path=Path(wheel_path),
        output_dir=Path(output_dir),
        environment=environment,
        lakehouse_base_path=lakehouse_base_path,
        integration_inputs_root=(
            Path(integration_inputs_root) if integration_inputs_root is not None else None
        ),
        environ=environ,
        auto_notebook_token=auto_notebook_token,
    )
    authorizations = CertificationAuthorizations(
        allow_control_plane_migration=allow_control_plane_migration,
        allow_control_plane_writes=allow_control_plane_writes,
        allow_pipeline_execution=allow_pipeline_execution,
        allow_capture_execution=allow_capture_execution,
        allow_warehouse_execution=allow_warehouse_execution,
        allow_warehouse_fault_injection=allow_warehouse_fault_injection,
        allow_warehouse_session_termination=allow_warehouse_session_termination,
        allow_business_path_execution=allow_business_path_execution,
        allow_scenario_mutation=allow_scenario_mutation,
    )
    request.output_dir.mkdir(parents=True, exist_ok=True)
    bounded = run_bounded_certification(
        spark=request.spark,
        candidate_manifest_path=request.candidate_manifest_path,
        wheel_path=request.wheel_path,
        environment=request.environment,
        lakehouse_base_path=request.lakehouse_base_path,
        output_path=request.output_dir / "bounded-certification.json",
    )
    return run_unified_certification(request, authorizations, bounded, started_at)


def print_certification_summary(report: UnifiedCertificationReport) -> None:
    width = max(len(item.check_id) for item in report.checks)
    print("Fabric Framework Certification")
    print("=" * (width + 16))
    for item in report.checks:
        print(f"{item.check_id:<{width}}  {item.status.value}")
    print("-" * (width + 16))
    print(f"overall_status{' ' * max(1, width - 12)}  {report.overall_status.value}")
    print(f"release_authorized{' ' * max(1, width - 15)}  false")
    if report.blockers:
        print("blockers:")
        for blocker in report.blockers:
            print(f"- {blocker}")


__all__ = ["certify", "print_certification_summary"]
