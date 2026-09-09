"""Minimal public entry point for Fabric notebook operators."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import json
import os
from pathlib import Path

from sqlalchemy import create_engine

from fabric_data_framework.deployment.delivery import (
    load_dataset_configs,
    load_release_manifest,
    materialize_semantic_metadata,
)
from fabric_data_framework.evidence.integration.runner import (
    load_approved_integration_runner_config,
)

from .bounded import run_bounded_certification
from .models import CertificationCheckStatus
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


def _runtime_names(integration_inputs_root: Path) -> tuple[str, ...]:
    runner = load_approved_integration_runner_config(
        integration_inputs_root / "runner-config.json"
    )
    values = (
        runner.fabric_access_token_env_var,
        runner.control_plane_database_url_env_var,
        runner.warehouse_database_url_env_var,
        runner.warehouse_admin_database_url_env_var,
    )
    return tuple(dict.fromkeys(value for value in values if value is not None))


def _notebook_fabric_token() -> str:
    try:
        from notebookutils import credentials  # type: ignore

        value = credentials.getToken("pbi")
    except Exception:
        return ""
    return value.strip() if isinstance(value, str) else ""


def _resolve_runtime_environment(
    integration_inputs_root: Path | None,
    supplied: Mapping[str, str] | None,
) -> tuple[Mapping[str, str] | None, tuple[str, ...]]:
    if integration_inputs_root is None:
        return supplied, ()

    names = _runtime_names(integration_inputs_root)
    resolved = dict(os.environ if supplied is None else supplied)
    runner = load_approved_integration_runner_config(
        integration_inputs_root / "runner-config.json"
    )
    token_name = runner.fabric_access_token_env_var
    if not resolved.get(token_name, "").strip():
        token = _notebook_fabric_token()
        if token:
            resolved[token_name] = token
    return resolved, names


@contextmanager
def _scoped_process_runtime(
    runtime_environment: Mapping[str, str] | None,
    declared_names: tuple[str, ...],
) -> Iterator[None]:
    """Mirror only declared runtime values into ``os.environ`` during certification."""

    if runtime_environment is None or not declared_names:
        yield
        return

    previous = {name: os.environ.get(name) for name in declared_names}
    existed = {name: name in os.environ for name in declared_names}
    try:
        for name in declared_names:
            value = runtime_environment.get(name)
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name in declared_names:
            if existed[name]:
                assert previous[name] is not None
                os.environ[name] = previous[name]
            else:
                os.environ.pop(name, None)


def _integration_identity_matches_bounded(
    integration_inputs_root: Path,
    bounded_report,
) -> None:
    inputs = json.loads(
        (integration_inputs_root / "INPUTS.json").read_text(encoding="utf-8")
    )
    if inputs.get("candidate_git_sha") != bounded_report.candidate_git_sha:
        raise ValueError("integration input bundle candidate git SHA mismatch")
    if inputs.get("candidate_wheel_sha256") != bounded_report.artifact_sha256:
        raise ValueError("integration input bundle candidate wheel SHA256 mismatch")
    if inputs.get("framework_version") != bounded_report.framework_version:
        raise ValueError("integration input bundle framework version mismatch")


def _bootstrap_control_plane_after_bounded_preflight(
    *,
    spark,
    candidate_manifest: Path,
    wheel: Path,
    integration_inputs_root: Path,
    output_dir: Path,
    environment: str,
    lakehouse_base_path: str,
    runtime_environment: Mapping[str, str] | None,
) -> None:
    """Bootstrap a dedicated certification Control Plane only after bounded PASS."""

    bounded = run_bounded_certification(
        spark=spark,
        candidate_manifest_path=candidate_manifest,
        wheel_path=wheel,
        environment=environment,
        lakehouse_base_path=lakehouse_base_path,
        output_path=output_dir / "control-plane-bootstrap-bounded-preflight.json",
    )
    if any(
        item.status is not CertificationCheckStatus.PASS for item in bounded.checks
    ):
        return

    _integration_identity_matches_bounded(integration_inputs_root, bounded)
    runner = load_approved_integration_runner_config(
        integration_inputs_root / "runner-config.json"
    )
    env_name = runner.control_plane_database_url_env_var
    if env_name is None or runtime_environment is None:
        return
    database_url = runtime_environment.get(env_name, "").strip()
    if not database_url:
        return

    release_manifest = load_release_manifest(
        integration_inputs_root / "release-manifest.json"
    )
    configs = load_dataset_configs(integration_inputs_root / "project/config/datasets")
    engine = create_engine(database_url)
    try:
        observed_hash = materialize_semantic_metadata(
            engine,
            configs=configs,
            domain=release_manifest.domain,
            domain_git_sha=release_manifest.bundle.domain_git_sha,
            framework_version=release_manifest.bundle.framework_version,
        )
    finally:
        engine.dispose()
    if observed_hash != release_manifest.bundle.config_bundle_hash:
        raise RuntimeError(
            "certification Control Plane semantic metadata hash mismatch after bootstrap"
        )


def certify(
    *,
    spark,
    certification_root: str | Path = DEFAULT_CERTIFICATION_ROOT,
    environment: str = "DEV",
    integration_inputs_root: str | Path | None = None,
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
          integration-inputs/        # optional framework-owned exact bundle

    Without integration inputs this executes bounded real-Fabric checks only. With the
    exact framework-owned integration bundle, one ``allow_live_mutations`` flag
    authorizes normal bounded certification mutations already owned by approved
    framework runners. Admin-level Warehouse session termination remains separate.

    ``runtime_environment`` contains runtime-only values such as Control Plane and
    Warehouse database URLs. The integration runner config declares the allowed
    environment-variable names. Only those names are mirrored into process environment
    for the duration of the call and are restored before this function returns.

    ``allow_control_plane_migration=True`` is only for first-time bootstrap of a
    dedicated certification database after exact bounded checks PASS. It must not be
    used to silently modify shared or production Control Plane state.
    """

    root = Path(certification_root)
    candidate_manifest = root / "CANDIDATE.json"
    if not candidate_manifest.is_file():
        raise ValueError(
            f"candidate manifest is absent from certification root: {candidate_manifest}"
        )
    wheel = _discover_wheel(root)

    resolved_inputs = (
        Path(integration_inputs_root)
        if integration_inputs_root
        else root / "integration-inputs"
    )
    resolved_inputs_value = resolved_inputs if resolved_inputs.is_dir() else None

    resolved_output = Path(output_dir) if output_dir else root / "certification-output"
    resolved_runtime, declared_runtime_names = _resolve_runtime_environment(
        resolved_inputs_value,
        runtime_environment,
    )

    with _scoped_process_runtime(resolved_runtime, declared_runtime_names):
        if (
            resolved_inputs_value is not None
            and allow_live_mutations
            and allow_control_plane_migration
        ):
            _bootstrap_control_plane_after_bounded_preflight(
                spark=spark,
                candidate_manifest=candidate_manifest,
                wheel=wheel,
                integration_inputs_root=resolved_inputs_value,
                output_dir=resolved_output,
                environment=environment,
                lakehouse_base_path=lakehouse_base_path,
                runtime_environment=resolved_runtime,
            )

        return run_unified_certification(
            spark=spark,
            candidate_manifest_path=candidate_manifest,
            wheel_path=wheel,
            output_dir=resolved_output,
            environment=environment,
            lakehouse_base_path=lakehouse_base_path,
            integration_inputs_root=resolved_inputs_value,
            environ=resolved_runtime,
            auto_notebook_token=False if resolved_inputs_value is not None else True,
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
