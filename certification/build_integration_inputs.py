"""Build an exact framework-owned integration input bundle for one candidate wheel.

The bundle is credential-free. It binds the exact framework candidate to the reference
certification project, physical non-secret Fabric item IDs, integration recipes and
runtime environment-variable names. It does not execute Fabric and cannot create PASS
evidence.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version as installed_version
import json
from pathlib import Path
import re
import shutil

from fabric_data_framework.contracts.environment import EnvironmentName
from fabric_data_framework.control_plane.certification import ControlPlaneExternalEvidence
from fabric_data_framework.control_plane.enterprise import (
    ENTERPRISE_FABRIC_CONTROL_PLANE_PROFILE_NAME,
    assert_enterprise_fabric_control_plane_profile,
)
from fabric_data_framework.deployment.delivery import (
    artifact_sha256,
    build_release_manifest,
    load_dataset_configs,
    write_json_model,
)
from fabric_data_framework.evidence.approved_capture_runner import load_approved_capture_run_config
from fabric_data_framework.evidence.approved_warehouse_fault_runner import (
    load_approved_warehouse_fault_drill_config,
)
from fabric_data_framework.evidence.approved_warehouse_runner import (
    load_approved_warehouse_run_config,
)
from fabric_data_framework.evidence.business_path_driver import (
    load_approved_business_path_driver_config,
)
from fabric_data_framework.evidence.business_path_evidence import (
    load_approved_business_path_scenario,
)
from fabric_data_framework.evidence.business_path_plan import (
    load_approved_business_path_certification_plan,
    resolve_business_path_plan_file,
)
from fabric_data_framework.evidence.integration_runner import (
    ApprovedIntegrationRunnerConfig,
    IntegrationCheckPhysicalBinding,
)


_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_DOMAIN = "framework-certification"
_INPUT_SCHEMA_VERSION = 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("certification/integration_project"),
    )
    parser.add_argument("--framework-wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-git-sha", required=True)
    parser.add_argument("--candidate-wheel-sha256", required=True)
    parser.add_argument("--framework-version", required=True)
    parser.add_argument("--environment", choices=("DEV", "UAT", "PROD"), required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--item-read-id", required=True)
    parser.add_argument("--pipeline-item-id", required=True)
    parser.add_argument("--copy-job-id", required=True)
    parser.add_argument("--spark-job-id", required=True)
    parser.add_argument(
        "--control-plane-profile",
        choices=(ENTERPRISE_FABRIC_CONTROL_PLANE_PROFILE_NAME,),
        required=True,
    )
    return parser


def _require_identity(args: argparse.Namespace) -> None:
    if _SHA40.fullmatch(args.candidate_git_sha) is None:
        raise ValueError("candidate_git_sha must be a 40-character lowercase git SHA")
    if _SHA64.fullmatch(args.candidate_wheel_sha256) is None:
        raise ValueError("candidate_wheel_sha256 must be lowercase SHA256")
    if not args.framework_wheel.is_file():
        raise ValueError(f"framework wheel does not exist: {args.framework_wheel}")
    if artifact_sha256(args.framework_wheel) != args.candidate_wheel_sha256:
        raise ValueError("framework wheel SHA256 does not match requested candidate")
    observed = installed_version("fabric-data-framework")
    if observed != args.framework_version:
        raise ValueError(
            f"installed framework version {observed!r} != requested {args.framework_version!r}"
        )
    expected_name = f"fabric_data_framework-{args.framework_version}-py3-none-any.whl"
    if args.framework_wheel.name != expected_name:
        raise ValueError(
            f"candidate wheel filename must be {expected_name!r}; "
            f"observed={args.framework_wheel.name!r}"
        )
    assert_enterprise_fabric_control_plane_profile(args.control_plane_profile)


def _artifact_inputs(project_root: Path, framework_wheel: Path) -> dict[str, Path]:
    cert_root = project_root / "config/certification"
    files = sorted(path for path in cert_root.rglob("*") if path.is_file())
    if not files:
        raise ValueError("integration project contains no certification artifacts")
    result: dict[str, Path] = {}
    for path in files:
        name = path.name
        if name in result:
            raise ValueError(f"duplicate certification artifact basename: {name}")
        result[name] = path
    if framework_wheel.name in result:
        raise ValueError("framework wheel name collides with certification artifact")
    result[framework_wheel.name] = framework_wheel
    return result


def _project_file_hashes(project_root: Path) -> dict[str, str]:
    files = sorted(path for path in project_root.rglob("*") if path.is_file())
    if not files:
        raise ValueError("integration project is empty")
    return {
        path.relative_to(project_root).as_posix(): artifact_sha256(path)
        for path in files
    }


def _integration_inputs_hash(
    *,
    project_root: Path,
    environment: str,
    control_plane_profile: str,
    bindings: tuple[IntegrationCheckPhysicalBinding, ...],
) -> str:
    """Hash only certification inputs, never framework candidate bytes.

    The hash covers the complete reference project plus environment-local non-secret
    physical bindings and runtime variable *names*. Candidate git SHA, framework
    version and framework wheel SHA are deliberately excluded because the framework
    artifact has its own independent identity.
    """

    payload = {
        "input_schema_version": _INPUT_SCHEMA_VERSION,
        "domain": _DOMAIN,
        "environment": environment,
        "project_files": _project_file_hashes(project_root),
        "control_plane_profile": control_plane_profile,
        "runtime_env_vars": {
            "fabric_access_token": "FABRIC_ACCESS_TOKEN",
            "control_plane_database_url": "CONTROL_PLANE_DATABASE_URL",
            "warehouse_database_url": "WAREHOUSE_DATABASE_URL",
            "warehouse_admin_database_url": "WAREHOUSE_ADMIN_DATABASE_URL",
        },
        "bindings": [item.model_dump(mode="json") for item in bindings],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_project(
    project_root: Path,
    manifest,
    framework_wheel: Path,
) -> tuple[bool, list[str]]:
    configs = load_dataset_configs(project_root / "config/datasets")
    dataset_ids = {item.dataset_id for item in configs}
    if len(dataset_ids) != 8:
        raise ValueError("framework certification project must contain exactly eight datasets")

    cert_root = project_root / "config/certification"
    plan = load_approved_business_path_certification_plan(
        cert_root / "business-path-plan.json",
        release_manifest=manifest,
    )
    if len(plan.entries) != 5:
        raise ValueError("certification plan must contain exactly five business-path gates")
    for entry in plan.entries:
        scenario_path = resolve_business_path_plan_file(project_root, entry.scenario_path)
        driver_path = resolve_business_path_plan_file(project_root, entry.driver_config_path)
        scenario = load_approved_business_path_scenario(
            scenario_path,
            release_manifest=manifest,
        )
        if scenario.dataset_id not in dataset_ids:
            raise ValueError(f"business-path dataset absent from bundle: {scenario.dataset_id}")
        if scenario.extension_artifact_name != framework_wheel.name:
            raise ValueError("business-path observer must come from the candidate framework wheel")
        driver = load_approved_business_path_driver_config(
            driver_path,
            release_manifest=manifest,
            expected_scenario_hash=scenario.scenario_hash,
        )
        if driver.extension_artifact_name != framework_wheel.name:
            raise ValueError("business-path driver must come from the candidate framework wheel")

    integration = cert_root / "integration"
    copy_config = load_approved_capture_run_config(integration / "copy-run.json")
    spark_config = load_approved_capture_run_config(integration / "spark-run.json")
    warehouse_config = load_approved_warehouse_run_config(integration / "warehouse-run.json")
    fault_config = load_approved_warehouse_fault_drill_config(
        integration / "warehouse-fault-run.json"
    )
    if copy_config.check_id != "fabric.copy" or spark_config.check_id != "fabric.spark":
        raise ValueError("capture certification recipes own the wrong check IDs")
    if warehouse_config.check_id != "warehouse.commit":
        raise ValueError("Warehouse certification recipe owns the wrong check ID")
    if fault_config.check_id != "warehouse.ambiguous_commit":
        raise ValueError("Warehouse fault recipe owns the wrong check ID")
    for selected in (
        copy_config.dataset_id,
        spark_config.dataset_id,
        warehouse_config.dataset_id,
        fault_config.dataset_id,
    ):
        if selected not in dataset_ids:
            raise ValueError(f"integration recipe dataset absent from bundle: {selected}")
    for artifact_name in (
        copy_config.extension_artifact_name,
        spark_config.extension_artifact_name,
        warehouse_config.extension_artifact_name,
        fault_config.mutation_extension_artifact_name,
        fault_config.fault_injector_artifact_name,
    ):
        if artifact_name != framework_wheel.name:
            raise ValueError("integration extension must come from the candidate framework wheel")
        if manifest.artifact_sha256.get(artifact_name) != artifact_sha256(framework_wheel):
            raise ValueError("candidate framework wheel is not fingerprinted in release manifest")

    external = ControlPlaneExternalEvidence.from_json_file(
        integration / "control-plane-external-evidence.json"
    )
    blockers: list[str] = []
    if not external.complete:
        blockers.append("control_plane_external_evidence_incomplete")
    controller = fault_config.fault_payload.get("controller_url")
    if not isinstance(controller, str) or ".invalid" in controller:
        blockers.append("warehouse_real_fault_controller_not_configured")
    return not blockers, blockers


def main() -> int:
    args = _parser().parse_args()
    _require_identity(args)
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        raise ValueError(f"project root does not exist: {project_root}")

    configs = load_dataset_configs(project_root / "config/datasets")
    manifest = build_release_manifest(
        domain=_DOMAIN,
        domain_release_version=f"{args.framework_version}-integration",
        domain_git_sha=args.candidate_git_sha,
        framework_version=args.framework_version,
        configs=configs,
        config_schema_version=max(item.config_schema_version for item in configs),
        fabric_item_manifest_version="framework-certification-v1",
        build_id=f"candidate:{args.candidate_git_sha}:integration",
        artifacts=_artifact_inputs(project_root, args.framework_wheel),
    )
    live_ready, blockers = _validate_project(project_root, manifest, args.framework_wheel)

    bindings = (
        IntegrationCheckPhysicalBinding(
            check_id="fabric.item.read",
            workspace_id=args.workspace_id,
            item_id=args.item_read_id,
        ),
        IntegrationCheckPhysicalBinding(
            check_id="fabric.pipeline",
            workspace_id=args.workspace_id,
            item_id=args.pipeline_item_id,
            dataset_id="cert.full_replace",
        ),
        IntegrationCheckPhysicalBinding(
            check_id="fabric.copy",
            workspace_id=args.workspace_id,
            item_id=args.copy_job_id,
        ),
        IntegrationCheckPhysicalBinding(
            check_id="fabric.spark",
            workspace_id=args.workspace_id,
            item_id=args.spark_job_id,
        ),
    )
    integration_inputs_hash = _integration_inputs_hash(
        project_root=project_root,
        environment=args.environment,
        control_plane_profile=args.control_plane_profile,
        bindings=bindings,
    )
    runner = ApprovedIntegrationRunnerConfig(
        environment=EnvironmentName(args.environment),
        domain=_DOMAIN,
        framework_version=args.framework_version,
        framework_artifact_sha256=args.candidate_wheel_sha256,
        integration_inputs_hash=integration_inputs_hash,
        fabric_access_token_env_var="FABRIC_ACCESS_TOKEN",
        control_plane_database_url_env_var="CONTROL_PLANE_DATABASE_URL",
        warehouse_database_url_env_var="WAREHOUSE_DATABASE_URL",
        warehouse_admin_database_url_env_var="WAREHOUSE_ADMIN_DATABASE_URL",
        control_plane_profile=args.control_plane_profile,
        bindings=bindings,
    )

    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(project_root, output / "project")
    write_json_model(manifest, output / "release-manifest.json")
    write_json_model(runner, output / "runner-config.json")
    input_manifest = {
        "input_schema_version": _INPUT_SCHEMA_VERSION,
        "candidate_git_sha": args.candidate_git_sha,
        "candidate_wheel_sha256": args.candidate_wheel_sha256,
        "framework_version": args.framework_version,
        "integration_inputs_hash": integration_inputs_hash,
        "config_bundle_hash": manifest.bundle.config_bundle_hash,
        "framework_wheel_filename": args.framework_wheel.name,
        "live_prerequisites_configured": live_ready,
        "live_prerequisite_blockers": blockers,
    }
    (output / "INPUTS.json").write_text(
        json.dumps(input_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "built exact framework integration inputs "
        f"datasets={len(configs)} integration_inputs_hash={integration_inputs_hash} "
        f"live_prerequisites_configured={str(live_ready).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
