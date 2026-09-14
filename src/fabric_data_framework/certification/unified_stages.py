"""Typed stages for unified Fabric certification orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
import json
import os
from pathlib import Path
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
from fabric_data_framework.deployment.contracts import ReleaseManifest
from fabric_data_framework.deployment.delivery import (
    load_dataset_configs,
    load_release_manifest,
    write_json_model,
)
from fabric_data_framework.evidence.business_paths.approved_runner import (
    execute_approved_business_path,
    write_approved_business_path_execution_report,
)
from fabric_data_framework.evidence.business_paths.driver import (
    load_approved_business_path_driver_config,
)
from fabric_data_framework.evidence.business_paths.evidence import (
    load_approved_business_path_scenario,
)
from fabric_data_framework.evidence.business_paths.plan import (
    load_approved_business_path_certification_plan,
    resolve_business_path_plan_file,
)
from fabric_data_framework.evidence.business_paths.release_proof import (
    build_business_path_partial_proof_bundle,
)
from fabric_data_framework.evidence.integration.approved.capture import (
    execute_approved_capture,
    load_approved_capture_run_config,
)
from fabric_data_framework.evidence.integration.approved.control_plane import (
    execute_approved_control_plane_certification,
    write_control_plane_certification_report,
)
from fabric_data_framework.evidence.integration.approved.pipeline import (
    execute_approved_pipeline,
)
from fabric_data_framework.evidence.integration.approved.warehouse import (
    execute_approved_warehouse,
    load_approved_warehouse_run_config,
)
from fabric_data_framework.evidence.integration.approved.warehouse_fault import (
    execute_approved_warehouse_fault_drill,
    load_approved_warehouse_fault_drill_config,
)
from fabric_data_framework.evidence.integration.checks import run_fabric_item_read_check
from fabric_data_framework.evidence.integration.evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    run_integration_evidence,
    validate_integration_evidence_manifest,
    write_integration_evidence_manifest,
)
from fabric_data_framework.evidence.integration.merge import (
    merge_integration_evidence_manifests,
)
from fabric_data_framework.evidence.integration.rerun import (
    prepare_explicit_pipeline_rerun_prerequisite,
)
from fabric_data_framework.evidence.integration.runner import (
    ApprovedIntegrationRunnerConfig,
    build_approved_integration_run_plan,
    load_approved_integration_runner_config,
)
from fabric_data_framework.evidence.release.candidate_certification import (
    materialize_candidate_integration_spec,
)
from fabric_data_framework.evidence.release.merge import (
    merge_release_readiness_proof_bundles,
)
from fabric_data_framework.evidence.release.readiness import ReleaseReadinessSpec
from fabric_data_framework.metadata.config import DatasetConfig

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


@dataclass(frozen=True)
class UnifiedCertificationRequest:
    spark: object
    candidate_manifest_path: Path
    wheel_path: Path
    output_dir: Path
    environment: str
    lakehouse_base_path: str
    integration_inputs_root: Path | None
    environ: Mapping[str, str] | None
    auto_notebook_token: bool


@dataclass(frozen=True)
class CertificationAuthorizations:
    allow_control_plane_migration: bool = False
    allow_control_plane_writes: bool = False
    allow_pipeline_execution: bool = False
    allow_capture_execution: bool = False
    allow_warehouse_execution: bool = False
    allow_warehouse_fault_injection: bool = False
    allow_warehouse_session_termination: bool = False
    allow_business_path_execution: bool = False
    allow_scenario_mutation: bool = False


@dataclass(frozen=True)
class UnifiedCertificationContext:
    request: UnifiedCertificationRequest
    bounded: UnifiedCertificationReport
    project_root: Path
    integration_root: Path
    runner_config: ApprovedIntegrationRunnerConfig
    release_manifest: ReleaseManifest
    configs: tuple[DatasetConfig, ...]
    runtime_environ: dict[str, str]
    spec: IntegrationEvidenceSpec
    input_blockers: tuple[str, ...]
    ref_prefix: str


@dataclass(frozen=True)
class CertificationStageOutcome:
    checks: tuple[CertificationCheckResult, ...] = ()
    blockers: tuple[str, ...] = ()
    partials: tuple[tuple[str, IntegrationEvidenceManifest], ...] = ()
    base_manifest: IntegrationEvidenceManifest | None = None
    integration_manifest: IntegrationEvidenceManifest | None = None
    evidence_path: str | None = None
    fault_controller_blocked: bool = False

    def partials_dict(self) -> dict[str, IntegrationEvidenceManifest]:
        return dict(self.partials)


@dataclass(frozen=True)
class CertificationReportPaths:
    integration_evidence: str | None = None
    business_path_proofs: str | None = None


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


def _write_json(payload: object, path: Path) -> None:
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
    config: ApprovedIntegrationRunnerConfig,
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


def _integration_result(
    manifest: IntegrationEvidenceManifest,
    check_id: str,
) -> CertificationCheckResult:
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


def _append_not_run(
    checks: tuple[CertificationCheckResult, ...],
    ids: tuple[str, ...],
    reason: str,
) -> tuple[CertificationCheckResult, ...]:
    existing = {item.check_id for item in checks}
    missing = tuple(
        _safe_result(check_id, CertificationCheckStatus.NOT_RUN, reason)
        for check_id in ids
        if check_id not in existing
    )
    return checks + missing


def _item_read(
    context: UnifiedCertificationContext,
) -> IntegrationEvidenceManifest:
    config = context.runner_config
    plan = build_approved_integration_run_plan(
        config,
        context.spec,
        environ=context.runtime_environ,
        selected_check_ids=("fabric.item.read",),
        allow_mutating_checks=False,
    )
    if not plan.ready:
        raise ValueError("read-only Fabric item preflight is not ready")
    check = next(item for item in context.spec.checks if item.check_id == "fabric.item.read")
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
            environ=context.runtime_environ,
        )
    )
    return run_integration_evidence(
        context.spec,
        runners={
            "fabric.item.read": lambda: run_fabric_item_read_check(
                client=client,
                check_id="fabric.item.read",
                workspace_id=binding.workspace_id,
                item_id=binding.item_id,
                evidence_references=(f"{context.ref_prefix}:fabric.item.read",),
            )
        },
    )


def _reference_control_plane_check(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
) -> CertificationCheckResult:
    check_id = "control.reference_conformance"
    config = context.runner_config
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
    database_url = context.runtime_environ.get(env_name, "").strip()
    if not database_url:
        return _safe_result(
            check_id,
            CertificationCheckStatus.BLOCKED,
            f"runtime prerequisite {env_name} is missing",
        )
    if not authorizations.allow_control_plane_writes:
        return _safe_result(
            check_id,
            CertificationCheckStatus.NOT_RUN,
            "temporary control-plane conformance writes were not authorized",
        )
    engine = create_engine(database_url)
    try:
        if authorizations.allow_control_plane_migration:
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


def preintegration_outcome(
    request: UnifiedCertificationRequest,
    bounded: UnifiedCertificationReport,
) -> CertificationStageOutcome | None:
    checks = tuple(bounded.checks)
    if any(item.status is CertificationCheckStatus.FAIL for item in bounded.checks):
        checks = _append_not_run(
            checks,
            _STANDARD_INTEGRATION_CHECKS,
            "not run because bounded certification failed",
        )
        checks = _append_not_run(
            checks,
            tuple(f"business.{gate}" for gate in _BUSINESS_GATES),
            "not run because bounded certification failed",
        )
        return CertificationStageOutcome(
            checks=checks,
            blockers=("bounded_certification_failed",),
        )
    if request.integration_inputs_root is None:
        checks = _append_not_run(
            checks,
            _STANDARD_INTEGRATION_CHECKS,
            "exact framework integration input bundle was not supplied",
        )
        checks = _append_not_run(
            checks,
            tuple(f"business.{gate}" for gate in _BUSINESS_GATES),
            "exact framework integration input bundle was not supplied",
        )
        return CertificationStageOutcome(
            checks=checks,
            blockers=("integration_inputs_not_supplied",),
        )
    return None


def load_integration_context(
    request: UnifiedCertificationRequest,
    bounded: UnifiedCertificationReport,
) -> tuple[UnifiedCertificationContext, CertificationStageOutcome]:
    assert request.integration_inputs_root is not None
    root = request.integration_inputs_root
    project = root / "project"
    integration_root = project / "config/certification/integration"
    inputs = json.loads((root / "INPUTS.json").read_text(encoding="utf-8"))
    if inputs.get("candidate_git_sha") != bounded.candidate_git_sha:
        raise ValueError("integration input bundle candidate git SHA mismatch")
    if inputs.get("candidate_wheel_sha256") != bounded.artifact_sha256:
        raise ValueError("integration input bundle candidate wheel SHA256 mismatch")
    if inputs.get("framework_version") != bounded.framework_version:
        raise ValueError("integration input bundle framework version mismatch")
    integration_inputs_hash = inputs.get("integration_inputs_hash")
    if not isinstance(integration_inputs_hash, str):
        raise ValueError("integration input bundle is missing integration_inputs_hash")

    runner_config = load_approved_integration_runner_config(root / "runner-config.json")
    if runner_config.framework_artifact_sha256 != bounded.artifact_sha256:
        raise ValueError("runner config framework artifact SHA256 mismatch")
    if runner_config.integration_inputs_hash != integration_inputs_hash:
        raise ValueError("runner config integration input hash mismatch")
    release_manifest = load_release_manifest(root / "release-manifest.json")
    configs = tuple(load_dataset_configs(project / "config/datasets"))
    if release_manifest.artifact_sha256.get(request.wheel_path.name) != bounded.artifact_sha256:
        raise ValueError(
            "integration release manifest does not fingerprint the exact candidate wheel"
        )
    runtime = _runtime_environ(
        runner_config,
        request.environ,
        auto_notebook_token=request.auto_notebook_token,
    )
    template = _load_resource_json(
        "integration-evidence-template.json",
        IntegrationEvidenceSpec,
    )
    spec = materialize_candidate_integration_spec(
        template,
        environment=request.environment,
        domain=release_manifest.domain,
        artifact_sha256=bounded.artifact_sha256,
        integration_inputs_hash=integration_inputs_hash,
    )
    _write_json(spec, request.output_dir / "integration-spec.json")
    context = UnifiedCertificationContext(
        request=request,
        bounded=bounded,
        project_root=project,
        integration_root=integration_root,
        runner_config=runner_config,
        release_manifest=release_manifest,
        configs=configs,
        runtime_environ=runtime,
        spec=spec,
        input_blockers=tuple(inputs.get("live_prerequisite_blockers", ())),
        ref_prefix=f"certification-run:{uuid4().hex}",
    )
    fixture = _safe_result(
        "certification.fixtures",
        CertificationCheckStatus.PASS,
        "certification fixtures are owned by and fingerprinted to the candidate framework wheel",
    )
    return context, CertificationStageOutcome(checks=(fixture,))


def run_prerequisite_stage(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
) -> CertificationStageOutcome:
    checks: tuple[CertificationCheckResult, ...] = (
        _reference_control_plane_check(context, authorizations),
    )
    blockers: tuple[str, ...] = ()
    external_blockers = tuple(
        value
        for value in context.input_blockers
        if value == "control_plane_external_evidence_incomplete"
    )
    if external_blockers:
        checks += (
            _safe_result(
                "control.external_evidence",
                CertificationCheckStatus.BLOCKED,
                "enterprise control-plane evidence is incomplete",
            ),
        )
        blockers += external_blockers
    else:
        checks += (
            _safe_result(
                "control.external_evidence",
                CertificationCheckStatus.PASS,
                "framework integration inputs carry complete enterprise control-plane evidence references",
            ),
        )

    fault_controller_blocked = (
        "warehouse_real_fault_controller_not_configured" in context.input_blockers
    )
    checks += (
        _safe_result(
            "warehouse.fault_controller",
            CertificationCheckStatus.BLOCKED
            if fault_controller_blocked
            else CertificationCheckStatus.PASS,
            "real Warehouse fault controller is not configured"
            if fault_controller_blocked
            else "framework integration inputs configure the real Warehouse fault controller",
        ),
    )
    if fault_controller_blocked:
        blockers += ("warehouse_real_fault_controller_not_configured",)

    partials: dict[str, IntegrationEvidenceManifest] = {}
    try:
        item_manifest = _item_read(context)
        partials["fabric.item.read"] = item_manifest
        write_integration_evidence_manifest(
            item_manifest,
            context.request.output_dir / "partials/item-read.json",
        )
        checks += (_integration_result(item_manifest, "fabric.item.read"),)
    except Exception as exc:
        checks += (_safe_failure("fabric.item.read", exc),)
        blockers += ("fabric_item_read_failed",)

    control_outcome = _run_approved_control(context, authorizations, external_blockers, partials)
    checks += control_outcome.checks
    blockers += control_outcome.blockers
    partials.update(control_outcome.partials_dict())
    base_manifest, base_blockers = _merge_base_prerequisites(context, partials)
    return CertificationStageOutcome(
        checks=checks,
        blockers=blockers + base_blockers,
        partials=tuple(partials.items()),
        base_manifest=base_manifest,
        fault_controller_blocked=fault_controller_blocked,
    )


def _run_approved_control(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
    external_blockers: tuple[str, ...],
    partials: Mapping[str, IntegrationEvidenceManifest],
) -> CertificationStageOutcome:
    can_run = (
        not external_blockers
        and authorizations.allow_control_plane_writes
        and "fabric.item.read" in partials
    )
    if not can_run:
        reason = (
            "enterprise external evidence is not ready"
            if external_blockers
            else "control-plane conformance writes were not authorized"
        )
        if "fabric.item.read" not in partials:
            reason = "Fabric item read prerequisite did not PASS"
        return CertificationStageOutcome(
            checks=(_safe_result("control.cert", CertificationCheckStatus.NOT_RUN, reason),)
        )
    try:
        external_evidence = ControlPlaneExternalEvidence.from_json_file(
            context.integration_root / "control-plane-external-evidence.json"
        )
        execution = execute_approved_control_plane_certification(
            config=context.runner_config,
            spec=context.spec,
            check_id="control.cert",
            environ=context.runtime_environ,
            external_evidence=external_evidence,
            evidence_references=(f"{context.ref_prefix}:control.cert",),
            allow_conformance_writes=True,
        )
        write_integration_evidence_manifest(
            execution.manifest,
            context.request.output_dir / "partials/control-plane.json",
        )
        if execution.report is not None:
            write_control_plane_certification_report(
                execution.report,
                context.request.output_dir / "reports/control-plane.json",
            )
        return CertificationStageOutcome(
            checks=(_integration_result(execution.manifest, "control.cert"),),
            partials=(("control.cert", execution.manifest),),
        )
    except Exception as exc:
        return CertificationStageOutcome(
            checks=(_safe_failure("control.cert", exc),),
            blockers=("control_plane_certification_failed",),
        )


def _merge_base_prerequisites(
    context: UnifiedCertificationContext,
    partials: Mapping[str, IntegrationEvidenceManifest],
) -> tuple[IntegrationEvidenceManifest | None, tuple[str, ...]]:
    if "fabric.item.read" not in partials or "control.cert" not in partials:
        return None, ()
    try:
        base_manifest = merge_integration_evidence_manifests(
            context.spec,
            (partials["fabric.item.read"], partials["control.cert"]),
        )
        write_integration_evidence_manifest(
            base_manifest,
            context.request.output_dir / "partials/base-prerequisites.json",
        )
        return base_manifest, ()
    except Exception as exc:
        return None, (f"base_prerequisite_merge_failed:{type(exc).__name__}",)


def run_pipeline_capture_stage(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
    base_manifest: IntegrationEvidenceManifest | None,
) -> CertificationStageOutcome:
    pipeline = _run_pipeline(context, authorizations, base_manifest)
    captures = _run_captures(context, authorizations, base_manifest)
    return CertificationStageOutcome(
        checks=pipeline.checks + captures.checks,
        blockers=pipeline.blockers + captures.blockers,
        partials=pipeline.partials + captures.partials,
    )


def _run_pipeline(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
    base_manifest: IntegrationEvidenceManifest | None,
) -> CertificationStageOutcome:
    binding = next(
        (
            item
            for item in context.runner_config.bindings
            if item.check_id == "fabric.pipeline"
        ),
        None,
    )
    dataset_id = binding.dataset_id if binding else None
    if base_manifest is None or not authorizations.allow_pipeline_execution or not dataset_id:
        return CertificationStageOutcome(
            checks=(
                _safe_result(
                    "fabric.pipeline",
                    CertificationCheckStatus.NOT_RUN,
                    "base prerequisites are not ready or Pipeline execution was not authorized",
                ),
            )
        )
    try:
        execution = execute_approved_pipeline(
            config=context.runner_config,
            spec=context.spec,
            prerequisite_manifest=base_manifest,
            release_manifest=context.release_manifest,
            configs=context.configs,
            check_id="fabric.pipeline",
            dataset_id=dataset_id,
            environ=context.runtime_environ,
            evidence_references=(f"{context.ref_prefix}:fabric.pipeline",),
            allow_pipeline_execution=True,
        )
        write_integration_evidence_manifest(
            execution.manifest,
            context.request.output_dir / "partials/pipeline.json",
        )
        return CertificationStageOutcome(
            checks=(_integration_result(execution.manifest, "fabric.pipeline"),),
            partials=(("fabric.pipeline", execution.manifest),),
        )
    except Exception as exc:
        return CertificationStageOutcome(
            checks=(_safe_failure("fabric.pipeline", exc),),
            blockers=("fabric_pipeline_failed",),
        )


def _run_captures(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
    base_manifest: IntegrationEvidenceManifest | None,
) -> CertificationStageOutcome:
    outcomes = tuple(
        _run_capture(context, authorizations, base_manifest, check_id, recipe_name)
        for check_id, recipe_name in (
            ("fabric.copy", "copy-run.json"),
            ("fabric.spark", "spark-run.json"),
        )
    )
    return CertificationStageOutcome(
        checks=tuple(check for outcome in outcomes for check in outcome.checks),
        blockers=tuple(blocker for outcome in outcomes for blocker in outcome.blockers),
        partials=tuple(partial for outcome in outcomes for partial in outcome.partials),
    )


def _run_capture(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
    base_manifest: IntegrationEvidenceManifest | None,
    check_id: str,
    recipe_name: str,
) -> CertificationStageOutcome:
    if base_manifest is None or not authorizations.allow_capture_execution:
        return CertificationStageOutcome(
            checks=(
                _safe_result(
                    check_id,
                    CertificationCheckStatus.NOT_RUN,
                    "base prerequisites are not ready or capture execution was not authorized",
                ),
            )
        )
    try:
        capture_config = load_approved_capture_run_config(
            context.integration_root / recipe_name
        )
        execution = execute_approved_capture(
            config=context.runner_config,
            spec=context.spec,
            prerequisite_manifest=base_manifest,
            release_manifest=context.release_manifest,
            configs=context.configs,
            capture_config=capture_config,
            environ=context.runtime_environ,
            evidence_references=(f"{context.ref_prefix}:{check_id}",),
            allow_capture_execution=True,
        )
        write_integration_evidence_manifest(
            execution.manifest,
            context.request.output_dir / f"partials/{check_id}.json",
        )
        if execution.report is not None:
            write_json_model(
                execution.report,
                context.request.output_dir / f"reports/{check_id}.json",
            )
        return CertificationStageOutcome(
            checks=(_integration_result(execution.manifest, check_id),),
            partials=((check_id, execution.manifest),),
        )
    except Exception as exc:
        return CertificationStageOutcome(
            checks=(_safe_failure(check_id, exc),),
            blockers=(f"{check_id.replace('.', '_')}_failed",),
        )


def run_warehouse_stage(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
    prerequisites: CertificationStageOutcome,
) -> CertificationStageOutcome:
    warehouse = _run_warehouse(context, authorizations, prerequisites.base_manifest)
    partials = warehouse.partials_dict()
    fault_prerequisite = _merge_fault_prerequisite(
        context,
        prerequisites.base_manifest,
        partials.get("warehouse.commit"),
    )
    fault = _run_warehouse_fault(
        context,
        authorizations,
        fault_prerequisite,
        prerequisites.fault_controller_blocked,
    )
    return CertificationStageOutcome(
        checks=warehouse.checks + fault.checks,
        blockers=warehouse.blockers + fault.blockers,
        partials=warehouse.partials + fault.partials,
    )


def _run_warehouse(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
    base_manifest: IntegrationEvidenceManifest | None,
) -> CertificationStageOutcome:
    if base_manifest is None or not authorizations.allow_warehouse_execution:
        return CertificationStageOutcome(
            checks=(
                _safe_result(
                    "warehouse.commit",
                    CertificationCheckStatus.NOT_RUN,
                    "base prerequisites are not ready or Warehouse execution was not authorized",
                ),
            )
        )
    try:
        warehouse_config = load_approved_warehouse_run_config(
            context.integration_root / "warehouse-run.json"
        )
        execution = execute_approved_warehouse(
            config=context.runner_config,
            spec=context.spec,
            prerequisite_manifest=base_manifest,
            release_manifest=context.release_manifest,
            configs=context.configs,
            run_config=warehouse_config,
            environ=context.runtime_environ,
            evidence_references=(f"{context.ref_prefix}:warehouse.commit",),
            allow_warehouse_execution=True,
        )
        write_integration_evidence_manifest(
            execution.manifest,
            context.request.output_dir / "partials/warehouse-commit.json",
        )
        if execution.report is not None:
            write_json_model(
                execution.report,
                context.request.output_dir / "reports/warehouse-commit.json",
            )
        return CertificationStageOutcome(
            checks=(_integration_result(execution.manifest, "warehouse.commit"),),
            partials=(("warehouse.commit", execution.manifest),),
        )
    except Exception as exc:
        return CertificationStageOutcome(
            checks=(_safe_failure("warehouse.commit", exc),),
            blockers=("warehouse_commit_failed",),
        )


def _merge_fault_prerequisite(
    context: UnifiedCertificationContext,
    base_manifest: IntegrationEvidenceManifest | None,
    warehouse_manifest: IntegrationEvidenceManifest | None,
) -> IntegrationEvidenceManifest | None:
    if base_manifest is None or warehouse_manifest is None:
        return None
    try:
        prerequisite = merge_integration_evidence_manifests(
            context.spec,
            (base_manifest, warehouse_manifest),
        )
        write_integration_evidence_manifest(
            prerequisite,
            context.request.output_dir / "partials/fault-prerequisites.json",
        )
        return prerequisite
    except Exception:
        return None


def _run_warehouse_fault(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
    fault_prerequisite: IntegrationEvidenceManifest | None,
    fault_controller_blocked: bool,
) -> CertificationStageOutcome:
    if (
        fault_prerequisite is None
        or fault_controller_blocked
        or not authorizations.allow_warehouse_fault_injection
    ):
        reason = (
            "real Warehouse fault controller is not configured"
            if fault_controller_blocked
            else "fault prerequisites are not ready or fault injection was not authorized"
        )
        return CertificationStageOutcome(
            checks=(
                _safe_result(
                    "warehouse.ambiguous_commit",
                    CertificationCheckStatus.NOT_RUN,
                    reason,
                ),
            )
        )
    try:
        fault_config = load_approved_warehouse_fault_drill_config(
            context.integration_root / "warehouse-fault-run.json"
        )
        execution = execute_approved_warehouse_fault_drill(
            config=context.runner_config,
            spec=context.spec,
            prerequisite_manifest=fault_prerequisite,
            release_manifest=context.release_manifest,
            configs=context.configs,
            run_config=fault_config,
            environ=context.runtime_environ,
            evidence_references=(
                f"{context.ref_prefix}:warehouse.ambiguous_commit",
            ),
            allow_warehouse_fault_injection=True,
            allow_warehouse_session_termination=(
                authorizations.allow_warehouse_session_termination
            ),
        )
        write_integration_evidence_manifest(
            execution.manifest,
            context.request.output_dir / "partials/warehouse-ambiguous-commit.json",
        )
        if execution.report is not None:
            write_json_model(
                execution.report,
                context.request.output_dir / "reports/warehouse-ambiguous-commit.json",
            )
        return CertificationStageOutcome(
            checks=(
                _integration_result(execution.manifest, "warehouse.ambiguous_commit"),
            ),
            partials=(("warehouse.ambiguous_commit", execution.manifest),),
        )
    except Exception as exc:
        return CertificationStageOutcome(
            checks=(_safe_failure("warehouse.ambiguous_commit", exc),),
            blockers=("warehouse_ambiguous_commit_failed",),
        )


def merge_integration_stage(
    context: UnifiedCertificationContext,
    *outcomes: CertificationStageOutcome,
) -> CertificationStageOutcome:
    partials = tuple(partial for outcome in outcomes for partial in outcome.partials)
    manifests = tuple(manifest for _, manifest in partials)
    if not manifests:
        return CertificationStageOutcome(partials=partials)
    try:
        integration_manifest = merge_integration_evidence_manifests(
            context.spec,
            manifests,
        )
        validate_integration_evidence_manifest(context.spec, integration_manifest)
        path = context.request.output_dir / "integration-evidence.json"
        write_integration_evidence_manifest(integration_manifest, path)
        return CertificationStageOutcome(
            partials=partials,
            integration_manifest=integration_manifest,
            evidence_path=str(path),
        )
    except Exception as exc:
        return CertificationStageOutcome(
            partials=partials,
            blockers=(f"integration_merge_failed:{type(exc).__name__}",),
        )


def _integration_certified(
    context: UnifiedCertificationContext,
    manifest: IntegrationEvidenceManifest | None,
) -> bool:
    if manifest is None:
        return False
    try:
        validate_integration_evidence_manifest(
            context.spec,
            manifest,
            require_certified=True,
        )
    except Exception:
        return False
    return True


def run_business_path_stage(
    context: UnifiedCertificationContext,
    authorizations: CertificationAuthorizations,
    integration_manifest: IntegrationEvidenceManifest | None,
) -> CertificationStageOutcome:
    certified = _integration_certified(context, integration_manifest)
    allowed = (
        certified
        and authorizations.allow_business_path_execution
        and authorizations.allow_scenario_mutation
        and authorizations.allow_pipeline_execution
    )
    if not allowed:
        reason = (
            "certified integration evidence is not complete"
            if not certified
            else "business-path Pipeline/scenario mutation was not explicitly authorized"
        )
        return CertificationStageOutcome(
            checks=_append_not_run(
                (),
                tuple(f"business.{gate}" for gate in _BUSINESS_GATES),
                reason,
            )
        )
    assert integration_manifest is not None
    return _execute_business_paths(context, integration_manifest)


def _run_business_path_entry(
    context: UnifiedCertificationContext,
    integration_manifest: IntegrationEvidenceManifest,
    entry,
):
    scenario_path = resolve_business_path_plan_file(
        context.project_root,
        entry.scenario_path,
    )
    driver_path = resolve_business_path_plan_file(
        context.project_root,
        entry.driver_config_path,
    )
    scenario = load_approved_business_path_scenario(
        scenario_path,
        release_manifest=context.release_manifest,
    )
    driver = load_approved_business_path_driver_config(
        driver_path,
        release_manifest=context.release_manifest,
        expected_scenario_hash=scenario.scenario_hash,
    )
    prerequisite = prepare_explicit_pipeline_rerun_prerequisite(
        context.spec,
        integration_manifest,
        check_id=entry.pipeline_check_id,
    )
    execution = execute_approved_business_path(
        runner_config=context.runner_config,
        integration_spec=context.spec,
        prerequisite_manifest=prerequisite,
        release_manifest=context.release_manifest,
        configs=context.configs,
        scenario=scenario,
        driver_config=driver,
        candidate_git_sha=context.bounded.candidate_git_sha,
        artifact_sha256=context.bounded.artifact_sha256,
        pipeline_check_id=entry.pipeline_check_id,
        environ=context.runtime_environ,
        evidence_references=(
            f"{context.ref_prefix}:business.{entry.gate_id.value}",
        ),
        allow_pipeline_execution=True,
        allow_scenario_mutation=True,
    )
    gate_dir = context.request.output_dir / "business-paths" / entry.gate_id.value
    write_approved_business_path_execution_report(execution, gate_dir / "report.json")
    partial = build_business_path_partial_proof_bundle(
        execution,
        context.release_manifest,
    )
    _write_json(partial, gate_dir / "proof.json")
    check = _safe_result(
        f"business.{entry.gate_id.value}",
        CertificationCheckStatus.PASS
        if execution.proof.status.value == "PASS"
        else CertificationCheckStatus.FAIL,
        f"live business-path proof={execution.proof.status.value}",
        evidence_references=tuple(execution.proof.evidence_references),
    )
    return check, partial


def _execute_business_paths(
    context: UnifiedCertificationContext,
    integration_manifest: IntegrationEvidenceManifest,
) -> CertificationStageOutcome:
    checks: tuple[CertificationCheckResult, ...] = ()
    partial_proofs = []
    try:
        plan = load_approved_business_path_certification_plan(
            context.project_root / "config/certification/business-path-plan.json",
            release_manifest=context.release_manifest,
        )
        readiness_spec = _load_resource_json("readiness-spec.json", ReleaseReadinessSpec)
        for entry in plan.entries:
            check, partial = _run_business_path_entry(
                context,
                integration_manifest,
                entry,
            )
            checks += (check,)
            partial_proofs.append(partial)
        merged_proofs = merge_release_readiness_proof_bundles(
            readiness_spec,
            partial_proofs,
        )
        path = context.request.output_dir / "business-path-release-proofs.json"
        _write_json(merged_proofs, path)
        return CertificationStageOutcome(checks=checks, evidence_path=str(path))
    except Exception as exc:
        checks = _append_not_run(
            checks,
            tuple(f"business.{gate}" for gate in _BUSINESS_GATES),
            "business-path execution did not complete",
        )
        return CertificationStageOutcome(
            checks=checks,
            blockers=(f"business_path_execution_failed:{type(exc).__name__}",),
        )


def assemble_report(
    request: UnifiedCertificationRequest,
    bounded: UnifiedCertificationReport,
    started_at,
    outcomes: tuple[CertificationStageOutcome, ...],
    paths: CertificationReportPaths = CertificationReportPaths(),
) -> UnifiedCertificationReport:
    checks = tuple(check for outcome in outcomes for check in outcome.checks)
    blockers = tuple(blocker for outcome in outcomes for blocker in outcome.blockers)
    report = UnifiedCertificationReport(
        framework_version=bounded.framework_version,
        candidate_git_sha=bounded.candidate_git_sha,
        artifact_sha256=bounded.artifact_sha256,
        environment=request.environment,
        started_at=started_at,
        completed_at=utcnow(),
        checks=checks,
        blockers=tuple(dict.fromkeys(blockers)),
        integration_evidence_path=paths.integration_evidence,
        business_path_proofs_path=paths.business_path_proofs,
        release_authorized=False,
    )
    _write_json(report, request.output_dir / "certification-report.json")
    return report


def run_unified_certification(
    request: UnifiedCertificationRequest,
    authorizations: CertificationAuthorizations,
    bounded: UnifiedCertificationReport,
    started_at,
) -> UnifiedCertificationReport:
    terminal = preintegration_outcome(request, bounded)
    if terminal is not None:
        return assemble_report(request, bounded, started_at, (terminal,))
    context, loaded = load_integration_context(request, bounded)
    prerequisites = run_prerequisite_stage(context, authorizations)
    data_execution = run_pipeline_capture_stage(
        context,
        authorizations,
        prerequisites.base_manifest,
    )
    warehouse = run_warehouse_stage(context, authorizations, prerequisites)
    integration = merge_integration_stage(
        context,
        prerequisites,
        data_execution,
        warehouse,
    )
    business = run_business_path_stage(
        context,
        authorizations,
        integration.integration_manifest,
    )
    outcomes = (
        CertificationStageOutcome(checks=tuple(bounded.checks)),
        loaded,
        prerequisites,
        data_execution,
        warehouse,
        integration,
        business,
    )
    paths = CertificationReportPaths(
        integration_evidence=integration.evidence_path,
        business_path_proofs=business.evidence_path,
    )
    return assemble_report(request, bounded, started_at, outcomes, paths)


__all__ = [
    "CertificationAuthorizations",
    "CertificationStageOutcome",
    "UnifiedCertificationContext",
    "UnifiedCertificationRequest",
    "run_unified_certification",
]
