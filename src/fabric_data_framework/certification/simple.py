"""Minimal public entry point for Fabric notebook operators."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .unified import certify as run_unified_certification


DEFAULT_CERTIFICATION_ROOT = Path("/lakehouse/default/Files/framework_cert")


def _discover_wheel(root: Path) -> Path:
    wheels = sorted(root.glob("fabric_data_framework-*.whl"))
    if len(wheels) != 1:
        raise ValueError(
            "certification root must contain exactly one fabric_data_framework-*.whl; "
            f"observed={len(wheels)}"
        )
    return wheels[0]


def certify(
    *,
    spark,
    certification_root: str | Path = DEFAULT_CERTIFICATION_ROOT,
    environment: str = "DEV",
    customer_inputs_root: str | Path | None = None,
    output_dir: str | Path | None = None,
    lakehouse_base_path: str = "Files/framework_cert",
    runtime_environment: Mapping[str, str] | None = None,
    allow_live_mutations: bool = False,
    allow_control_plane_migration: bool = False,
    allow_warehouse_session_termination: bool = False,
):
    """Run the fullest safe certification possible from one conventional directory.

    Expected layout::

        framework_cert/
          CANDIDATE.json
          fabric_data_framework-<version>-py3-none-any.whl
          customer-inputs/        # optional exact Customer artifact

    With no Customer bundle this executes bounded real-Fabric checks only.  When the
    exact bundle is present, one ``allow_live_mutations`` flag authorizes the normal
    DEV/UAT certification mutations already owned by the approved runners, including
    the reviewed fault drill when configured. Admin-level Warehouse session
    termination remains a separate explicit authorization.

    ``runtime_environment`` is an optional process-local mapping for runtime-only
    values such as the Control Plane and Warehouse database URLs.  The Customer runner
    config declares the required environment-variable *names*; secret values are not
    retained in source-controlled certification inputs or report payloads.  When this
    mapping is omitted, the runner reads the current process environment instead.
    """

    root = Path(certification_root)
    candidate_manifest = root / "CANDIDATE.json"
    if not candidate_manifest.is_file():
        raise ValueError(f"candidate manifest is absent from certification root: {candidate_manifest}")
    wheel = _discover_wheel(root)

    resolved_customer = Path(customer_inputs_root) if customer_inputs_root else root / "customer-inputs"
    if not resolved_customer.is_dir():
        resolved_customer_value = None
    else:
        resolved_customer_value = resolved_customer

    resolved_output = Path(output_dir) if output_dir else root / "certification-output"

    return run_unified_certification(
        spark=spark,
        candidate_manifest_path=candidate_manifest,
        wheel_path=wheel,
        output_dir=resolved_output,
        environment=environment,
        lakehouse_base_path=lakehouse_base_path,
        customer_inputs_root=resolved_customer_value,
        environ=runtime_environment,
        auto_notebook_token=True,
        install_extensions=True,
        allow_control_plane_migration=allow_control_plane_migration,
        allow_control_plane_writes=allow_live_mutations,
        allow_pipeline_execution=allow_live_mutations,
        allow_capture_execution=allow_live_mutations,
        allow_warehouse_execution=allow_live_mutations,
        allow_warehouse_fault_injection=allow_live_mutations,
        allow_warehouse_session_termination=allow_warehouse_session_termination,
        allow_business_path_execution=allow_live_mutations,
        allow_scenario_mutation=allow_live_mutations,
    )


__all__ = ["DEFAULT_CERTIFICATION_ROOT", "certify"]
