"""Unified one-call certification orchestrator for real Fabric environments.

The orchestrator composes existing approved runners. It does not weaken any gate:
missing credentials, missing reviewed external evidence, or absent mutation/fault
authorization become NOT_RUN/BLOCKED rather than fabricated PASS results.
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib.resources import files
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine

from fabric_data_framework.adapters.fabric.auth import EnvironmentAccessTokenProvider
from fabric_data_framework.adapters.fabric.rest import FabricRestClient
from fabric_data_framework.control_plane.certification import (
    ControlPlaneExternalEvidence,
    certify_control_plane_backend,
    get_control_plane_backend_profile,
)
from fabric_data_framework.control_plane.schema import apply_baseline_schema
from fabric_data_framework.deployment.delivery import (
    load_dataset_configs,
    load_release_manifest,
    write_json_model,
)
from fabric_data_framework.evidence.approved_business_path_runner import (
    execute_approved_business_path,
    write_approved_business_path_execution_report,
)
from fabric_data_framework.evidence.approved_capture_runner import (
    execute_approved_capture,
    load_approved_capture_run_config,
)
from fabric_data_framework.evidence.approved_control_plane_runner import (
    execute_approved_control_plane_certification,
    write_control_plane_certification_report,
)
from fabric_data_framework.evidence.approved_pipeline_runner import execute_approved_pipeline
from fabric_data_framework.evidence.approved_warehouse_fault_runner import (
    execute_approved_warehouse_fault_drill,
    load_approved_warehouse_fault_drill_config,
)
from fabric_data_framework.evidence.approved_warehouse_runner import (
    execute_approved_warehouse,
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
from fabric_data_framework.evidence.business_path_release_proof import (
    build_business_path_partial_proof_bundle,
)
from fabric_data_framework.evidence.candidate_certification import (
    materialize_candidate_integration_spec,
)
from fabric_data_framework.evidence.integration_checks import run_fabric_item_read_check
from fabric_data_framework.evidence.integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    run_integration_evidence,
    validate_integration_evidence_manifest,
    write_integration_evidence_manifest,
)
from fabric_data_framework.evidence.integration_evidence_merge import (
    merge_integration_evidence_manifests,
)
from fabric_data_framework.evidence.integration_evidence_rerun import (
    prepare_explicit_pipeline_rerun_prerequisite,
)
from fabric_data_framework.evidence.integration_runner import (
    build_approved_integration_run_plan,
    load_approved_integration_runner_config,
)
from fabric_data_framework.evidence.release_readiness import ReleaseReadinessSpec
from fabric_data_framework.evidence.release_readiness_merge import (
    merge_release_readiness_proof_bundles,
)

from .bounded import run_bounded_certification
from .models import (
    CertificationCheckResult,
    CertificationCheckStatus,
    UnifiedCertificationReport,
    utcnow,
)


_STANDARD_INTEGRATION_CHECKS = (
    "fabric.item.read",
    "control.cert",
    "fabric.pipeline",
    "fabric.copy",
    "fabric.spark",
    "warehouse.commit",
    "warehouse.ambiguous_commit",
)
_BUSINESS_GATES = (
    "full.replace",
    "watermark.scd1",
    "watermark.scd2",
    "retry.idempotency",
    "reconciliation.fail_closed",
)


def _safe_result(
    check_id: str,
    status: CertificationCheckStatus,
    detail: str,
    *,
    evidence_references: tuple[str, ...] = (),
) -> CertificationCheckResult:
    return CertificationCheckResult(
        check_id=check_id,
        status=status,
        detail=detail,
        evidence_references=evidence_references,
    )


def _safe_failure(check_id: str, exc: BaseException) -> CertificationCheckResult:
    return _safe_result(
        check_id,
        CertificationCheckStatus.FAIL,
        f"{check_id} failed ({type(exc).__name__})",
    )


def _write_json(payload, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _load_resource_json(name: str, model_type):
    raw = (
        files("fabric_data_framework.certification")
        .joinpath("resources")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )
    return model_type.model_validate_json(raw)


def _runtime_environ(
    config,
    environ: Mapping[str, str] | None,
    *,
    auto_notebook_token: bool,
) -> dict[str, str]:
    resolved = dict(os.environ if environ is None else environ)
    token_name = config.fabric_access_token_env_var
    if auto_notebook_token and not resolved.get(token_name, "").strip():
        try:
            from notebookutils import credentials  # type: ignore

            token = credentials.getToken("pbi")
        except Exception:
            token = ""
        if isinstance(token, str) and token.strip():
            resolved[token_name] = token.strip()
    return resolved


def _install_exact_extensions(root: Path, release_manifest) -> tuple[str, ...]:
    dist = root / "dist"
    if not dist.is_dir():
        return ()
    installed: list[str] = []
    for wheel in sorted(dist.glob("*.whl")):
        expected = release_manifest.artifact_sha256.get(wheel.name)
        if expected is None:
            continue
        observed = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if observed != expected.lower():
            raise ValueError(f"extension wheel SHA256 mismatch for {wheel.name}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", str(wheel)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        installed.append(wheel.name)
    return tuple(installed)


def _integration_result(manifest, check_id: str) -> CertificationCheckResult:
    result = next(item for item in manifest.results if item.check_id == check_id)
    status = {
        IntegrationEvidenceStatus.PASS: CertificationCheckStatus.PASS,
        IntegrationEvidenceStatus.FAIL: CertificationCheckStatus.FAIL,
        IntegrationEvidenceStatus.NOT_RUN: CertificationCheckStatus.NOT_RUN,
    }[result.status]
    return _safe_result(
        check_id,
        status,
        f"approved integration result={result.status.value}",
        evidence_references=tuple(result.evidence_references),
    )


def _item_read(*, config, spec, environ, reference: str):
    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ=environ,
        selected_check_ids=("fabric.item.read",),
        allow_mutating_checks=False,
    )
    if not plan.ready:
        raise ValueError("read-only Fabric item preflight is not ready")
    check = next(item for item in spec.checks if item.check_id == "fabric.item.read")
    if check.kind is not IntegrationEvidenceCheckKind.FABRIC_ITEM_READ:
        raise ValueError("fabric.item.read has wrong integration kind")
    if len(plan.bindings) != 1:
        raise ValueError("fabric.item.read requires exactly one physical binding")
    binding = plan.bindings[0]
    if binding.workspace_id is None or binding.item_id is None:
        raise ValueError("fabric.item.read physical binding is incomplete")
    client = FabricRestClient(
        token_provider=EnvironmentAccessTokenProvider(
            env_var=config.fabric_access_token_env_var,
            environ=environ,
        )
    )
    return run_integration_evidence(
        spec,
        runners={
            "fabric.item.read": lambda: run_fabric_item_read_check(
                client=client,
                check_id="fabric.item.read",
                workspace_id=binding.workspace_id,
                item_id=binding.item_id,
                evidence_references=(reference,),
            )
        },
    )


def _reference_control_plane_check(
    *,
    config,
    environ,
    allow_control_plane_writes: bool,
    allow_control_plane_migration: bool,
) -> CertificationCheckResult:
    check_id = "control.reference_conformance"
    if config.control_plane_profile is None:
        return _safe_result(
            check_id,
            CertificationCheckStatus.BLOCKED,
            "control-plane profile is not configured",
        )
    env_name = config.control_plane_database_url_env_var
    if env_name is None:
        return _safe_result(
            check_id,
            CertificationCheckStatus.BLOCKED,
            "control-plane runtime URL env-var name is not configured",
        )
    database_url = environ.get(env_name, "").strip()
    if not database_url:
        return _safe_result(
            check_id,
            CertificationCheckStatus.BLOCKED,
            f"runtime prerequisite {env_name} is missing",
        )
    if not allow_control_plane_writes:
        return _safe_result(
            check_id,
            CertificationCheckStatus.NOT_RUN,
            "temporary control-plane conformance writes were not authorized",
        )
    engine = create_engine(database_url)
    try:
        if allow_control_plane_migration:
            apply_baseline_schema(engine)
        report = certify_control_plane_backend(
            engine,
            profile=get_control_plane_backend_profile(config.control_plane_profile),
            run_conformance=True,
            external_evidence=None,
        )
        if not report.reference_certified:
            return _safe_result(
                check_id,
                CertificationCheckStatus.FAIL,
                "deterministic control-plane transaction/CAS conformance did not pass",
            )
        return _safe_result(
            check_id,
            CertificationCheckStatus.PASS,
            "real control-plane schema, rollback and CAS conformance passed",
        )
    except Exception as exc:
        return _safe_failure(check_id, exc)
    finally:
        engine.dispose()


def _append_not_run(checks: list[CertificationCheckResult], ids, reason: str) -> None:
    existing = {item.check_id for item in checks}
    for check_id in ids:
        if check_id not in existing:
            checks.append(_safe_result(check_id, CertificationCheckStatus.NOT_RUN, reason))


def certify(
    *,
    spark,
    candidate_manifest_path: str | Path,
    wheel_path: str | Path,
    output_dir: str | Path,
    environment: str = "DEV",
    lakehouse_base_path: str = "Files/framework_cert",
    customer_inputs_root: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    auto_notebook_token: bool = True,
    install_extensions: bool = True,
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
    """Run bounded checks and, when an exact Customer bundle is supplied, all live gates.

    The one-call API intentionally exposes only mutation/privilege authorizations.
    Workspace/item IDs, dataset selections, recipes and non-secret runtime variable
    names come from the exact Customer input bundle.
    """

    started_at = utcnow()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    bounded = run_bounded_certification(
        spark=spark,
        candidate_manifest_path=candidate_manifest_path,
        wheel_path=wheel_path,
        environment=environment,
        lakehouse_base_path=lakehouse_base_path,
        output_path=out / "bounded-certification.json",
    )
    checks = list(bounded.checks)
    blockers: list[str] = []
    integration_path: str | None = None
    business_path_path: str | None = None

    if any(item.status is CertificationCheckStatus.FAIL for item in bounded.checks):
        blockers.append("bounded_certification_failed")
        _append_not_run(
            checks,
            _STANDARD_INTEGRATION_CHECKS,
            "not run because bounded certification failed",
        )
        _append_not_run(
            checks,
            tuple(f"business.{gate}" for gate in _BUSINESS_GATES),
            "not run because bounded certification failed",
        )
    elif customer_inputs_root is None:
        blockers.append("customer_inputs_not_supplied")
        _append_not_run(
            checks,
            _STANDARD_INTEGRATION_CHECKS,
            "exact Customer certification input bundle was not supplied",
        )
        _append_not_run(
            checks,
            tuple(f"business.{gate}" for gate in _BUSINESS_GATES),
            "exact Customer certification input bundle was not supplied",
        )
    else:
        root = Path(customer_inputs_root)
        input_manifest_path = root / "INPUTS.json"
        runner_path = root / "runner-config.json"
        release_manifest_path = root / "release-manifest.json"
        project = root / "project"
        integration_root = project / "config/certification/integration"
        config_dir = project / "config/datasets"

        inputs = json.loads(input_manifest_path.read_text(encoding="utf-8"))
        if inputs.get("candidate_git_sha") != bounded.candidate_git_sha:
            raise ValueError("Customer input bundle candidate git SHA mismatch")
        if inputs.get("candidate_wheel_sha256") != bounded.artifact_sha256:
            raise ValueError("Customer input bundle candidate wheel SHA256 mismatch")
        if inputs.get("framework_version") != bounded.framework_version:
            raise ValueError("Customer input bundle framework version mismatch")

        runner_config = load_approved_integration_runner_config(runner_path)
        release_manifest = load_release_manifest(release_manifest_path)
        configs = load_dataset_configs(config_dir)
        runtime = _runtime_environ(
            runner_config,
            environ,
            auto_notebook_token=auto_notebook_token,
        )

        if install_extensions:
            try:
                installed = _install_exact_extensions(root, release_manifest)
                checks.append(
                    _safe_result(
                        "extensions.install",
                        CertificationCheckStatus.PASS,
                        f"verified and installed {len(installed)} exact local extension wheel(s)",
                    )
                )
            except Exception as exc:
                checks.append(_safe_failure("extensions.install", exc))
                blockers.append("extension_install_failed")
        else:
            checks.append(
                _safe_result(
                    "extensions.install",
                    CertificationCheckStatus.NOT_RUN,
                    "automatic exact local extension installation disabled",
                )
            )

        template = _load_resource_json(
            "integration-evidence-template.json",
            IntegrationEvidenceSpec,
        )
        spec = materialize_candidate_integration_spec(
            template,
            environment=environment,
            domain=release_manifest.domain,
            artifact_sha256=bounded.artifact_sha256,
            domain_release_hash=release_manifest.bundle.release_hash,
        )
        _write_json(spec, out / "integration-spec.json")

        checks.append(
            _reference_control_plane_check(
                config=runner_config,
                environ=runtime,
                allow_control_plane_writes=allow_control_plane_writes,
                allow_control_plane_migration=allow_control_plane_migration,
            )
        )

        input_blockers = tuple(inputs.get("live_prerequisite_blockers", ()))
        external_blockers = tuple(
            value
            for value in input_blockers
            if value
            in {
                "control_plane_external_evidence_incomplete",
                "control_plane_external_evidence_not_review_bound",
            }
        )
        if external_blockers:
            checks.append(
                _safe_result(
                    "control.external_evidence",
                    CertificationCheckStatus.BLOCKED,
                    "reviewed control-plane external evidence is incomplete or not review-bound",
                )
            )
            blockers.extend(external_blockers)
        else:
            checks.append(
                _safe_result(
                    "control.external_evidence",
                    CertificationCheckStatus.PASS,
                    "exact Customer inputs carry complete reviewed control-plane evidence binding",
                )
            )

        fault_controller_blocked = (
            "warehouse_real_fault_controller_not_configured" in input_blockers
        )
        checks.append(
            _safe_result(
                "warehouse.fault_controller",
                CertificationCheckStatus.BLOCKED
                if fault_controller_blocked
                else CertificationCheckStatus.PASS,
                "real Warehouse fault controller is not configured"
                if fault_controller_blocked
                else "exact Customer inputs configure the reviewed real Warehouse fault controller",
            )
        )
        if fault_controller_blocked:
            blockers.append("warehouse_real_fault_controller_not_configured")

        run_id = uuid4().hex
        ref_prefix = f"certification-run:{run_id}"
        partials: dict[str, object] = {}

        try:
            item_manifest = _item_read(
                config=runner_config,
                spec=spec,
                environ=runtime,
                reference=f"{ref_prefix}:fabric.item.read",
            )
            partials["fabric.item.read"] = item_manifest
            write_integration_evidence_manifest(item_manifest, out / "partials/item-read.json")
            checks.append(_integration_result(item_manifest, "fabric.item.read"))
        except Exception as exc:
            checks.append(_safe_failure("fabric.item.read", exc))
            blockers.append("fabric_item_read_failed")

        can_run_approved_control = (
            not external_blockers
            and allow_control_plane_writes
            and "fabric.item.read" in partials
        )
        if can_run_approved_control:
            try:
                external_evidence = ControlPlaneExternalEvidence.from_json_file(
                    integration_root / "control-plane-external-evidence.json"
                )
                execution = execute_approved_control_plane_certification(
                    config=runner_config,
                    spec=spec,
                    check_id="control.cert",
                    environ=runtime,
                    external_evidence=external_evidence,
                    evidence_references=(f"{ref_prefix}:control.cert",),
                    allow_conformance_writes=True,
                )
                partials["control.cert"] = execution.manifest
                write_integration_evidence_manifest(
                    execution.manifest,
                    out / "partials/control-plane.json",
                )
                if execution.report is not None:
                    write_control_plane_certification_report(
                        execution.report,
                        out / "reports/control-plane.json",
                    )
                checks.append(_integration_result(execution.manifest, "control.cert"))
            except Exception as exc:
                checks.append(_safe_failure("control.cert", exc))
                blockers.append("control_plane_certification_failed")
        else:
            reason = (
                "reviewed external evidence is not ready"
                if external_blockers
                else "control-plane conformance writes were not authorized"
            )
            if "fabric.item.read" not in partials:
                reason = "Fabric item read prerequisite did not PASS"
            checks.append(_safe_result("control.cert", CertificationCheckStatus.NOT_RUN, reason))

        base_manifest = None
        if "fabric.item.read" in partials and "control.cert" in partials:
            try:
                base_manifest = merge_integration_evidence_manifests(
                    spec,
                    (partials["fabric.item.read"], partials["control.cert"]),
                )
                write_integration_evidence_manifest(
                    base_manifest,
                    out / "partials/base-prerequisites.json",
                )
            except Exception as exc:
                blockers.append(f"base_prerequisite_merge_failed:{type(exc).__name__}")

        pipeline_binding = next(
            (item for item in runner_config.bindings if item.check_id == "fabric.pipeline"),
            None,
        )
        pipeline_dataset_id = pipeline_binding.dataset_id if pipeline_binding else None

        if base_manifest is not None and allow_pipeline_execution and pipeline_dataset_id:
            try:
                execution = execute_approved_pipeline(
                    config=runner_config,
                    spec=spec,
                    prerequisite_manifest=base_manifest,
                    release_manifest=release_manifest,
                    configs=configs,
                    check_id="fabric.pipeline",
                    dataset_id=pipeline_dataset_id,
                    environ=runtime,
                    evidence_references=(f"{ref_prefix}:fabric.pipeline",),
                    allow_pipeline_execution=True,
                )
                partials["fabric.pipeline"] = execution.manifest
                write_integration_evidence_manifest(execution.manifest, out / "partials/pipeline.json")
                checks.append(_integration_result(execution.manifest, "fabric.pipeline"))
            except Exception as exc:
                checks.append(_safe_failure("fabric.pipeline", exc))
                blockers.append("fabric_pipeline_failed")
        else:
            checks.append(
                _safe_result(
                    "fabric.pipeline",
                    CertificationCheckStatus.NOT_RUN,
                    "base prerequisites are not ready or Pipeline execution was not authorized",
                )
            )

        for check_id, recipe_name in (
            ("fabric.copy", "copy-run.json"),
            ("fabric.spark", "spark-run.json"),
        ):
            if base_manifest is not None and allow_capture_execution:
                try:
                    capture_config = load_approved_capture_run_config(integration_root / recipe_name)
                    execution = execute_approved_capture(
                        config=runner_config,
                        spec=spec,
                        prerequisite_manifest=base_manifest,
                        release_manifest=release_manifest,
                        configs=configs,
                        capture_config=capture_config,
                        environ=runtime,
                        evidence_references=(f"{ref_prefix}:{check_id}",),
                        allow_capture_execution=True,
                    )
                    partials[check_id] = execution.manifest
                    write_integration_evidence_manifest(
                        execution.manifest,
                        out / f"partials/{check_id}.json",
                    )
                    if execution.report is not None:
                        write_json_model(execution.report, out / f"reports/{check_id}.json")
                    checks.append(_integration_result(execution.manifest, check_id))
                except Exception as exc:
                    checks.append(_safe_failure(check_id, exc))
                    blockers.append(f"{check_id.replace('.', '_')}_failed")
            else:
                checks.append(
                    _safe_result(
                        check_id,
                        CertificationCheckStatus.NOT_RUN,
                        "base prerequisites are not ready or capture execution was not authorized",
                    )
                )

        if base_manifest is not None and allow_warehouse_execution:
            try:
                warehouse_config = load_approved_warehouse_run_config(
                    integration_root / "warehouse-run.json"
                )
                execution = execute_approved_warehouse(
                    config=runner_config,
                    spec=spec,
                    prerequisite_manifest=base_manifest,
                    release_manifest=release_manifest,
                    configs=configs,
                    run_config=warehouse_config,
                    environ=runtime,
                    evidence_references=(f"{ref_prefix}:warehouse.commit",),
                    allow_warehouse_execution=True,
                )
                partials["warehouse.commit"] = execution.manifest
                write_integration_evidence_manifest(
                    execution.manifest,
                    out / "partials/warehouse-commit.json",
                )
                if execution.report is not None:
                    write_json_model(execution.report, out / "reports/warehouse-commit.json")
                checks.append(_integration_result(execution.manifest, "warehouse.commit"))
            except Exception as exc:
                checks.append(_safe_failure("warehouse.commit", exc))
                blockers.append("warehouse_commit_failed")
        else:
            checks.append(
                _safe_result(
                    "warehouse.commit",
                    CertificationCheckStatus.NOT_RUN,
                    "base prerequisites are not ready or Warehouse execution was not authorized",
                )
            )

        fault_prerequisite = None
        if base_manifest is not None and "warehouse.commit" in partials:
            try:
                fault_prerequisite = merge_integration_evidence_manifests(
                    spec,
                    (base_manifest, partials["warehouse.commit"]),
                )
                write_integration_evidence_manifest(
                    fault_prerequisite,
                    out / "partials/fault-prerequisites.json",
                )
            except Exception:
                fault_prerequisite = None

        if (
            fault_prerequisite is not None
            and not fault_controller_blocked
            and allow_warehouse_fault_injection
        ):
            try:
                fault_config = load_approved_warehouse_fault_drill_config(
                    integration_root / "warehouse-fault-run.json"
                )
                execution = execute_approved_warehouse_fault_drill(
                    config=runner_config,
                    spec=spec,
                    prerequisite_manifest=fault_prerequisite,
                    release_manifest=release_manifest,
                    configs=configs,
                    run_config=fault_config,
                    environ=runtime,
                    evidence_references=(f"{ref_prefix}:warehouse.ambiguous_commit",),
                    allow_warehouse_fault_injection=True,
                    allow_warehouse_session_termination=allow_warehouse_session_termination,
                )
                partials["warehouse.ambiguous_commit"] = execution.manifest
                write_integration_evidence_manifest(
                    execution.manifest,
                    out / "partials/warehouse-ambiguous-commit.json",
                )
                if execution.report is not None:
                    write_json_model(
                        execution.report,
                        out / "reports/warehouse-ambiguous-commit.json",
                    )
                checks.append(
                    _integration_result(execution.manifest, "warehouse.ambiguous_commit")
                )
            except Exception as exc:
                checks.append(_safe_failure("warehouse.ambiguous_commit", exc))
                blockers.append("warehouse_ambiguous_commit_failed")
        else:
            reason = (
                "real Warehouse fault controller is not configured"
                if fault_controller_blocked
                else "fault prerequisites are not ready or fault injection was not authorized"
            )
            checks.append(
                _safe_result(
                    "warehouse.ambiguous_commit",
                    CertificationCheckStatus.NOT_RUN,
                    reason,
                )
            )

        integration_manifest = None
        substantive = tuple(partials.values())
        if substantive:
            try:
                integration_manifest = merge_integration_evidence_manifests(spec, substantive)
                validate_integration_evidence_manifest(spec, integration_manifest)
                integration_path_obj = out / "integration-evidence.json"
                write_integration_evidence_manifest(integration_manifest, integration_path_obj)
                integration_path = str(integration_path_obj)
            except Exception as exc:
                blockers.append(f"integration_merge_failed:{type(exc).__name__}")

        integration_certified = False
        if integration_manifest is not None:
            try:
                validate_integration_evidence_manifest(
                    spec,
                    integration_manifest,
                    require_certified=True,
                )
                integration_certified = True
            except Exception:
                integration_certified = False

        if (
            integration_certified
            and allow_business_path_execution
            and allow_scenario_mutation
            and allow_pipeline_execution
        ):
            try:
                plan = load_approved_business_path_certification_plan(
                    project / "config/certification/business-path-plan.json",
                    release_manifest=release_manifest,
                )
                partial_proofs = []
                readiness_spec = _load_resource_json("readiness-spec.json", ReleaseReadinessSpec)
                for entry in plan.entries:
                    scenario_path = resolve_business_path_plan_file(project, entry.scenario_path)
                    driver_path = resolve_business_path_plan_file(project, entry.driver_config_path)
                    scenario = load_approved_business_path_scenario(
                        scenario_path,
                        release_manifest=release_manifest,
                    )
                    driver = load_approved_business_path_driver_config(
                        driver_path,
                        release_manifest=release_manifest,
                        expected_scenario_hash=scenario.scenario_hash,
                    )
                    prerequisite = prepare_explicit_pipeline_rerun_prerequisite(
                        spec,
                        integration_manifest,
                        check_id=entry.pipeline_check_id,
                    )
                    execution = execute_approved_business_path(
                        runner_config=runner_config,
                        integration_spec=spec,
                        prerequisite_manifest=prerequisite,
                        release_manifest=release_manifest,
                        configs=configs,
                        scenario=scenario,
                        driver_config=driver,
                        candidate_git_sha=bounded.candidate_git_sha,
                        artifact_sha256=bounded.artifact_sha256,
                        pipeline_check_id=entry.pipeline_check_id,
                        environ=runtime,
                        evidence_references=(
                            f"{ref_prefix}:business.{entry.gate_id.value}",
                        ),
                        allow_pipeline_execution=True,
                        allow_scenario_mutation=True,
                    )
                    gate_dir = out / "business-paths" / entry.gate_id.value
                    write_approved_business_path_execution_report(
                        execution,
                        gate_dir / "report.json",
                    )
                    partial = build_business_path_partial_proof_bundle(
                        execution,
                        release_manifest,
                    )
                    _write_json(partial, gate_dir / "proof.json")
                    partial_proofs.append(partial)
                    checks.append(
                        _safe_result(
                            f"business.{entry.gate_id.value}",
                            CertificationCheckStatus.PASS
                            if execution.proof.status.value == "PASS"
                            else CertificationCheckStatus.FAIL,
                            f"live business-path proof={execution.proof.status.value}",
                            evidence_references=tuple(execution.proof.evidence_references),
                        )
                    )
                merged_proofs = merge_release_readiness_proof_bundles(
                    readiness_spec,
                    partial_proofs,
                )
                proofs_path = out / "business-path-release-proofs.json"
                _write_json(merged_proofs, proofs_path)
                business_path_path = str(proofs_path)
            except Exception as exc:
                blockers.append(f"business_path_execution_failed:{type(exc).__name__}")
                _append_not_run(
                    checks,
                    tuple(f"business.{gate}" for gate in _BUSINESS_GATES),
                    "business-path execution did not complete",
                )
        else:
            reason = (
                "certified integration evidence is not complete"
                if not integration_certified
                else "business-path Pipeline/scenario mutation was not explicitly authorized"
            )
            _append_not_run(
                checks,
                tuple(f"business.{gate}" for gate in _BUSINESS_GATES),
                reason,
            )

    report = UnifiedCertificationReport(
        framework_version=bounded.framework_version,
        candidate_git_sha=bounded.candidate_git_sha,
        artifact_sha256=bounded.artifact_sha256,
        environment=environment,
        started_at=started_at,
        completed_at=utcnow(),
        checks=tuple(checks),
        blockers=tuple(dict.fromkeys(blockers)),
        integration_evidence_path=integration_path,
        business_path_proofs_path=business_path_path,
        release_authorized=False,
    )
    _write_json(report, out / "certification-report.json")
    return report


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
