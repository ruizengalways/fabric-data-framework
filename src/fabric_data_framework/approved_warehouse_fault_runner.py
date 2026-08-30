"""Exact-release approved real-fault drill for ambiguous Fabric Warehouse COMMIT.

This runner is separate from the normal approved Warehouse commit runner. PASS requires
an actually observed provider/driver exception, verified provider-specific fault
injection, committed target-side marker evidence, journal reconciliation to SUCCEEDED,
and later SKIP_SUCCEEDED re-entry. A normal transaction return can never PASS this drill.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.engine import Connection

from .config import DatasetConfig, FrozenModel, canonical_hash, resolve_effective_config
from .contracts.recovery import UnknownOutcomeResolution
from .control_plane_certification import get_control_plane_backend_profile
from .delivery import config_bundle_hash
from .deployment import ReleaseManifest
from .extensions import ExtensionKind, ExtensionRegistry
from .integration_evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    run_integration_evidence,
    validate_integration_evidence_manifest,
)
from .integration_runner import (
    ApprovedIntegrationRunPlan,
    ApprovedIntegrationRunnerConfig,
    build_approved_integration_run_plan,
)
from .recovery.fabric_warehouse import (
    FABRIC_WAREHOUSE_DEFAULT_MARKER_TABLE,
    FabricWarehouseAtomicMutationResult,
    FabricWarehouseMarkerStore,
    FabricWarehouseMutationEvidence,
    FabricWarehouseTargetCommitProbe,
    build_fabric_warehouse_operation_marker_table,
)
from .recovery.target_probe import probe_and_reconcile_target_operation
from .recovery.warehouse_fault_injection import (
    FabricWarehouseCommitFaultArmEvidence,
    FabricWarehouseCommitFaultInjector,
    FabricWarehouseCommitFaultRequest,
    FabricWarehouseCommitFaultVerification,
    WarehouseCommitFaultPhase,
)
from .relational_repository import SqlAlchemyControlPlaneRepository
from .retained_evidence_safety import assert_safe_retained_text
from .target_operation_io import (
    claim_target_operation,
    mark_target_operation_not_committed,
    mark_target_operation_unknown,
)
from .target_operations import (
    TargetOperationAction,
    TargetOperationIntent,
    TargetOperationStatus,
)


_EXTENSION_PATTERN = r"^[a-z][a-z0-9_.-]*$"
_SQL_IDENTIFIER_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]{0,127}$"


class ApprovedWarehouseFaultDrillConfig(FrozenModel):
    """Credential-free exact recipe for one real ambiguous-COMMIT drill."""

    check_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    dataset_id: str = Field(min_length=1, max_length=256)
    operation_kind: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    target_reference: str = Field(min_length=1, max_length=1024)
    mutation_extension: str = Field(pattern=_EXTENSION_PATTERN)
    mutation_extension_artifact_name: str = Field(min_length=1, max_length=512)
    mutation_payload: dict[str, Any] = Field(default_factory=dict)
    fault_injector_extension: str = Field(pattern=_EXTENSION_PATTERN)
    fault_injector_artifact_name: str = Field(min_length=1, max_length=512)
    fault_payload: dict[str, Any] = Field(default_factory=dict)
    marker_table_name: str = Field(
        default=FABRIC_WAREHOUSE_DEFAULT_MARKER_TABLE,
        pattern=_SQL_IDENTIFIER_PATTERN,
    )
    marker_schema: str | None = Field(default="dbo", pattern=_SQL_IDENTIFIER_PATTERN)

    @model_validator(mode="after")
    def validate_safe_recipe(self) -> "ApprovedWarehouseFaultDrillConfig":
        rendered = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
        assert_safe_retained_text(rendered, "approved Warehouse fault drill config")
        return self

    @property
    def run_config_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))

    @property
    def input_fingerprint(self) -> str:
        return canonical_hash(
            {
                "mutation_payload": self.mutation_payload,
                "fault_injector_extension": self.fault_injector_extension,
                "fault_payload": self.fault_payload,
                "fault_phase": WarehouseCommitFaultPhase.COMMIT_ACKNOWLEDGEMENT.value,
            }
        )


class ApprovedWarehouseFaultDrillReport(FrozenModel):
    check_id: str
    run_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_run_id: UUID
    target_reference: str
    fault_phase: WarehouseCommitFaultPhase
    fault_armed: bool
    provider_exception_observed: bool
    execution_exception_type: str | None = Field(default=None, max_length=256)
    disarm_exception_type: str | None = Field(default=None, max_length=256)
    verification_exception_type: str | None = Field(default=None, max_length=256)
    fault_verified: bool
    fault_identity_matches: bool
    fault_evidence_reference: str | None = Field(default=None, max_length=2048)
    provider_fault_id: str | None = Field(default=None, max_length=1024)
    marker_reference: str | None = Field(default=None, max_length=2048)
    probe_resolution: UnknownOutcomeResolution | None = None
    final_status: TargetOperationStatus | None = None
    reentry_action: str | None = None
    evidence_status: IntegrationEvidenceStatus
    failure_reason: str | None = Field(default=None, max_length=512)
    evidence_references: tuple[str, ...]

    @model_validator(mode="after")
    def validate_report(self) -> "ApprovedWarehouseFaultDrillReport":
        if self.evidence_status is IntegrationEvidenceStatus.PASS:
            passed = (
                self.fault_armed
                and self.provider_exception_observed
                and self.execution_exception_type is not None
                and self.disarm_exception_type is None
                and self.verification_exception_type is None
                and self.fault_verified
                and self.fault_identity_matches
                and self.probe_resolution is UnknownOutcomeResolution.COMMITTED
                and self.final_status is TargetOperationStatus.SUCCEEDED
                and self.reentry_action == TargetOperationAction.SKIP_SUCCEEDED.value
                and self.marker_reference is not None
                and self.failure_reason is None
            )
            if not passed:
                raise ValueError(
                    "approved Warehouse ambiguous-COMMIT drill PASS requires an observed and "
                    "verified real fault plus COMMITTED->SUCCEEDED->SKIP_SUCCEEDED recovery"
                )
        assert_safe_retained_text(
            self.model_dump_json(),
            "approved Warehouse fault drill report",
        )
        return self


@dataclass(frozen=True)
class ApprovedWarehouseFaultDrillExecution:
    plan: ApprovedIntegrationRunPlan
    manifest: IntegrationEvidenceManifest
    report: ApprovedWarehouseFaultDrillReport | None


EngineFactory = Callable[[str], Engine]
WarehouseMutationExtension = Callable[
    [Connection, TargetOperationIntent, Mapping[str, Any]],
    FabricWarehouseMutationEvidence | None,
]
WarehouseFaultInjectorFactory = Callable[
    [Engine, FabricWarehouseCommitFaultRequest, Mapping[str, Any]],
    FabricWarehouseCommitFaultInjector,
]
MarkerStoreFactory = Callable[
    [Engine, ApprovedWarehouseFaultDrillConfig],
    FabricWarehouseMarkerStore,
]


def _default_marker_store_factory(
    engine: Engine,
    run_config: ApprovedWarehouseFaultDrillConfig,
) -> FabricWarehouseMarkerStore:
    marker = build_fabric_warehouse_operation_marker_table(
        MetaData(),
        table_name=run_config.marker_table_name,
        schema=run_config.marker_schema,
    )
    return FabricWarehouseMarkerStore(engine, marker)


def load_approved_warehouse_fault_drill_config(
    path: str | Path,
) -> ApprovedWarehouseFaultDrillConfig:
    return ApprovedWarehouseFaultDrillConfig.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def _require_prerequisites(
    spec: IntegrationEvidenceSpec,
    prerequisite_manifest: IntegrationEvidenceManifest,
    *,
    selected_check_id: str,
) -> None:
    validate_integration_evidence_manifest(spec, prerequisite_manifest)
    results = {item.check_id: item for item in prerequisite_manifest.results}
    if results[selected_check_id].status is not IntegrationEvidenceStatus.NOT_RUN:
        raise ValueError(
            "approved Warehouse fault drill requires the selected check to remain NOT_RUN in "
            "the prerequisite manifest"
        )
    required = (
        (IntegrationEvidenceCheckKind.FABRIC_ITEM_READ, "read-only Fabric item"),
        (
            IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            "control-plane certification",
        ),
        (
            IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
            "normal approved Warehouse commit/recovery",
        ),
    )
    for kind, label in required:
        if not any(
            item.kind is kind and item.status is IntegrationEvidenceStatus.PASS
            for item in prerequisite_manifest.results
        ):
            raise ValueError(
                f"approved Warehouse fault drill requires a retained PASS {label} prerequisite"
            )


def _require_exact_release_dataset(
    *,
    config: ApprovedIntegrationRunnerConfig,
    run_config: ApprovedWarehouseFaultDrillConfig,
    release_manifest: ReleaseManifest,
    configs: tuple[DatasetConfig, ...],
) -> DatasetConfig:
    if release_manifest.domain != config.domain:
        raise ValueError("release manifest and approved runner config domain differ")
    if release_manifest.bundle.framework_version != config.framework_version:
        raise ValueError("release manifest and approved runner framework version differ")
    if release_manifest.bundle.release_hash != config.release_hash:
        raise ValueError("release manifest and approved runner release hash differ")
    if config_bundle_hash(configs) != release_manifest.bundle.config_bundle_hash:
        raise ValueError("dataset config bundle hash does not match exact release manifest")
    for artifact_name, label in (
        (run_config.mutation_extension_artifact_name, "mutation"),
        (run_config.fault_injector_artifact_name, "fault injector"),
    ):
        if artifact_name not in release_manifest.artifact_sha256:
            raise ValueError(
                f"approved Warehouse {label} extension artifact is not fingerprinted in the "
                "exact release manifest"
            )
    by_id = {item.dataset_id: item for item in configs}
    if len(by_id) != len(configs):
        raise ValueError("approved Warehouse fault config bundle contains duplicate dataset_id values")
    selected = by_id.get(run_config.dataset_id)
    if selected is None:
        raise ValueError(
            f"approved Warehouse fault dataset {run_config.dataset_id!r} is absent from release bundle"
        )
    return selected


def _resolve_extensions(
    run_config: ApprovedWarehouseFaultDrillConfig,
    extension_registry: ExtensionRegistry | None,
) -> tuple[WarehouseMutationExtension, WarehouseFaultInjectorFactory]:
    registry = extension_registry or ExtensionRegistry()
    if extension_registry is None:
        registry.discover(ExtensionKind.WAREHOUSE_MUTATION)
        registry.discover(ExtensionKind.WAREHOUSE_COMMIT_FAULT_INJECTOR)
    return (
        registry.factory(
            ExtensionKind.WAREHOUSE_MUTATION,
            run_config.mutation_extension,
        ),
        registry.factory(
            ExtensionKind.WAREHOUSE_COMMIT_FAULT_INJECTOR,
            run_config.fault_injector_extension,
        ),
    )


def _dedupe_references(*groups: Iterable[str | None]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            if value is None or value in seen:
                continue
            assert_safe_retained_text(value, "Warehouse fault evidence reference")
            seen.add(value)
            result.append(value)
    return tuple(result)


def _fault_identity_matches(
    arm: FabricWarehouseCommitFaultArmEvidence,
    verification: FabricWarehouseCommitFaultVerification | None,
) -> bool:
    if verification is None or arm.phase is not verification.phase:
        return False
    if arm.provider_fault_id is not None:
        return verification.provider_fault_id == arm.provider_fault_id
    if arm.evidence_reference is not None:
        return verification.evidence_reference == arm.evidence_reference
    return False


def _build_result(
    *,
    check_id: str,
    status: IntegrationEvidenceStatus,
    intent: TargetOperationIntent,
    dataset_run_id: UUID,
    native_operation_id: str | None,
    evidence_references: tuple[str, ...],
    detail_code: str,
) -> IntegrationEvidenceCheckResult:
    assert_safe_retained_text(detail_code, "Warehouse fault drill detail code")
    return IntegrationEvidenceCheckResult(
        check_id=check_id,
        kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL,
        status=status,
        dataset_run_id=dataset_run_id,
        operation_key=intent.operation_key,
        native_operation_id=native_operation_id,
        evidence_references=evidence_references,
        detail=(
            "approved Warehouse ambiguous-COMMIT fault drill "
            f"{status.value}; reason={detail_code}"
        ),
    )


def _atomic_from_committed_marker(
    marker_store: FabricWarehouseMarkerStore,
    intent: TargetOperationIntent,
) -> FabricWarehouseAtomicMutationResult | None:
    markers = marker_store.read_markers(intent.operation_key)
    if not markers:
        return None
    return FabricWarehouseAtomicMutationResult(
        marker=markers[0],
        marker_reference=marker_store.marker_reference(intent.operation_key),
        executed=True,
    )


def _report(
    *,
    run_config: ApprovedWarehouseFaultDrillConfig,
    intent: TargetOperationIntent,
    dataset_run_id: UUID,
    request: FabricWarehouseCommitFaultRequest,
    arm: FabricWarehouseCommitFaultArmEvidence,
    status: IntegrationEvidenceStatus,
    references: tuple[str, ...],
    provider_exception_observed: bool = False,
    execution_exception_type: str | None = None,
    disarm_exception_type: str | None = None,
    verification_exception_type: str | None = None,
    verification: FabricWarehouseCommitFaultVerification | None = None,
    identity_matches: bool = False,
    atomic_result: FabricWarehouseAtomicMutationResult | None = None,
    probe_resolution: UnknownOutcomeResolution | None = None,
    final_status: TargetOperationStatus | None = None,
    reentry_action: str | None = None,
    failure_reason: str | None = None,
) -> ApprovedWarehouseFaultDrillReport:
    return ApprovedWarehouseFaultDrillReport(
        check_id=run_config.check_id,
        run_config_hash=run_config.run_config_hash,
        operation_key=intent.operation_key,
        dataset_run_id=dataset_run_id,
        target_reference=intent.target_reference,
        fault_phase=request.phase,
        fault_armed=arm.armed,
        provider_exception_observed=provider_exception_observed,
        execution_exception_type=execution_exception_type,
        disarm_exception_type=disarm_exception_type,
        verification_exception_type=verification_exception_type,
        fault_verified=bool(verification and verification.triggered),
        fault_identity_matches=identity_matches,
        fault_evidence_reference=(
            verification.evidence_reference
            if verification is not None
            else arm.evidence_reference
        ),
        provider_fault_id=(
            verification.provider_fault_id
            if verification is not None
            else arm.provider_fault_id
        ),
        marker_reference=(
            atomic_result.marker_reference if atomic_result is not None else None
        ),
        probe_resolution=probe_resolution,
        final_status=final_status,
        reentry_action=reentry_action,
        evidence_status=status,
        failure_reason=failure_reason,
        evidence_references=references,
    )


def execute_approved_warehouse_fault_drill(
    *,
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
    prerequisite_manifest: IntegrationEvidenceManifest,
    release_manifest: ReleaseManifest,
    configs: Iterable[DatasetConfig],
    run_config: ApprovedWarehouseFaultDrillConfig,
    environ: Mapping[str, str],
    evidence_references: Iterable[str],
    allow_warehouse_fault_injection: bool,
    extension_registry: ExtensionRegistry | None = None,
    control_engine_factory: EngineFactory = create_engine,
    warehouse_engine_factory: EngineFactory = create_engine,
    marker_store_factory: MarkerStoreFactory = _default_marker_store_factory,
) -> ApprovedWarehouseFaultDrillExecution:
    """Execute one approved real-fault drill and retain fail-closed recovery evidence."""

    config_tuple = tuple(configs)
    check_id = run_config.check_id
    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ=environ,
        selected_check_ids=(check_id,),
        allow_mutating_checks=allow_warehouse_fault_injection,
    )
    if not plan.ready:
        reasons: list[str] = []
        if plan.missing_runtime_env_vars:
            reasons.append(
                "missing runtime env vars=" + ",".join(plan.missing_runtime_env_vars)
            )
        if plan.mutating_check_ids and not plan.mutating_checks_authorized:
            reasons.append("Warehouse fault injection not explicitly authorized")
        raise ValueError(
            "approved Warehouse fault-drill preflight is not ready: " + "; ".join(reasons)
        )

    selected_spec = {item.check_id: item for item in spec.checks}[check_id]
    if (
        selected_spec.kind
        is not IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
    ):
        raise ValueError(
            "approved Warehouse fault runner requires "
            "FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL check kind"
        )
    _require_prerequisites(spec, prerequisite_manifest, selected_check_id=check_id)
    selected_dataset = _require_exact_release_dataset(
        config=config,
        run_config=run_config,
        release_manifest=release_manifest,
        configs=config_tuple,
    )
    if config.control_plane_profile is None or config.control_plane_database_url_env_var is None:
        raise ValueError("approved Warehouse fault runner requires control-plane configuration")
    if config.warehouse_database_url_env_var is None:
        raise ValueError("approved Warehouse fault runner requires warehouse_database_url_env_var")
    profile = get_control_plane_backend_profile(config.control_plane_profile)
    if not profile.production_eligible:
        raise ValueError(
            "approved Warehouse fault runner requires a production-eligible control-plane profile"
        )

    references = tuple(evidence_references)
    if not references:
        raise ValueError("approved Warehouse fault drill requires retained evidence references")
    for index, reference in enumerate(references):
        assert_safe_retained_text(reference, f"evidence_references[{index}]")

    mutation_extension, fault_factory = _resolve_extensions(run_config, extension_registry)
    effective = resolve_effective_config(selected_dataset)
    intent = TargetOperationIntent(
        dataset_id=selected_dataset.dataset_id,
        operation_kind=run_config.operation_kind,
        target_reference=run_config.target_reference,
        effective_config_hash=effective.effective_config_hash,
        input_fingerprint=run_config.input_fingerprint,
    )

    # Secret-bearing values are retrieved only after all non-secret gates pass.
    control_database_url = environ[config.control_plane_database_url_env_var]
    warehouse_database_url = environ[config.warehouse_database_url_env_var]
    reports: list[ApprovedWarehouseFaultDrillReport] = []

    def runner() -> IntegrationEvidenceCheckResult:
        control_engine = control_engine_factory(control_database_url)
        warehouse_engine = warehouse_engine_factory(warehouse_database_url)
        dataset_run_id = uuid4()
        try:
            repository = SqlAlchemyControlPlaneRepository(
                control_engine,
                domain=config.domain,
                domain_git_sha=release_manifest.bundle.domain_git_sha,
                framework_version=config.framework_version,
                configs=config_tuple,
            )
            deployed = repository.get_dataset(selected_dataset.dataset_id)
            if deployed.config_hash != selected_dataset.config_hash:
                raise RuntimeError(
                    "approved Warehouse fault drill deployed/release config identity mismatch"
                )

            marker_store = marker_store_factory(warehouse_engine, run_config)
            probe = FabricWarehouseTargetCommitProbe(marker_store=marker_store)
            claim = claim_target_operation(
                control_engine,
                intent=intent,
                dataset_run_id=dataset_run_id,
                attempt=1,
            )
            if claim.action is not TargetOperationAction.EXECUTE:
                return _build_result(
                    check_id=check_id,
                    status=IntegrationEvidenceStatus.FAIL,
                    intent=intent,
                    dataset_run_id=dataset_run_id,
                    native_operation_id=None,
                    evidence_references=references,
                    detail_code=f"FRESH_EXECUTE_REQUIRED_{claim.action.value}",
                )

            request = FabricWarehouseCommitFaultRequest(
                operation_key=intent.operation_key,
                dataset_id=intent.dataset_id,
                dataset_run_id=dataset_run_id,
                attempt=1,
                target_reference=intent.target_reference,
            )
            injector = fault_factory(warehouse_engine, request, run_config.fault_payload)
            if not isinstance(injector, FabricWarehouseCommitFaultInjector):
                raise TypeError(
                    "Warehouse fault injector extension did not return the required controller"
                )
            arm = injector.arm(request)
            if arm.phase is not request.phase:
                raise ValueError("Warehouse fault injector armed the wrong fault phase")
            if not arm.armed:
                current = mark_target_operation_not_committed(
                    control_engine,
                    operation_key=intent.operation_key,
                    expected_version=claim.record.version,
                    dataset_run_id=dataset_run_id,
                    attempt=1,
                    outcome_reference=arm.evidence_reference,
                )
                retained = _dedupe_references(references, (arm.evidence_reference,))
                reports.append(
                    _report(
                        run_config=run_config,
                        intent=intent,
                        dataset_run_id=dataset_run_id,
                        request=request,
                        arm=arm,
                        status=IntegrationEvidenceStatus.FAIL,
                        references=retained,
                        final_status=current.status,
                        failure_reason="FAULT_NOT_ARMED",
                    )
                )
                return _build_result(
                    check_id=check_id,
                    status=IntegrationEvidenceStatus.FAIL,
                    intent=intent,
                    dataset_run_id=dataset_run_id,
                    native_operation_id=None,
                    evidence_references=retained,
                    detail_code="FAULT_NOT_ARMED",
                )

            atomic_result: FabricWarehouseAtomicMutationResult | None = None
            execution_exception_type: str | None = None
            disarm_exception_type: str | None = None

            def mutation(connection: Connection, observed_intent: TargetOperationIntent):
                return mutation_extension(
                    connection,
                    observed_intent,
                    run_config.mutation_payload,
                )

            try:
                atomic_result = marker_store.execute_atomic(
                    intent=intent,
                    dataset_run_id=dataset_run_id,
                    attempt=1,
                    mutation=mutation,
                )
            except Exception as exc:
                execution_exception_type = type(exc).__name__
            finally:
                try:
                    injector.disarm(request)
                except Exception as exc:
                    disarm_exception_type = type(exc).__name__

            unknown = mark_target_operation_unknown(
                control_engine,
                operation_key=intent.operation_key,
                expected_version=claim.record.version,
                dataset_run_id=dataset_run_id,
                attempt=1,
                error_message=(
                    "approved Warehouse fault drill observed provider/driver exception "
                    f"{execution_exception_type}"
                    if execution_exception_type is not None
                    else "approved Warehouse fault drill target transaction returned without exception"
                ),
                outcome_reference=(
                    atomic_result.marker_reference if atomic_result is not None else None
                ),
            )
            reconciled = probe_and_reconcile_target_operation(
                control_engine,
                operation_key=intent.operation_key,
                dataset_run_id=uuid4(),
                attempt=max(2, unknown.attempt + 1),
                probe=probe,
            )
            probe_evidence = reconciled.evidence
            current = reconciled.record
            if (
                atomic_result is None
                and probe_evidence.resolution is UnknownOutcomeResolution.COMMITTED
            ):
                atomic_result = _atomic_from_committed_marker(marker_store, intent)

            verification: FabricWarehouseCommitFaultVerification | None = None
            verification_exception_type: str | None = None
            try:
                verification = injector.verify(
                    request,
                    observed_exception_type=execution_exception_type,
                    probe_evidence=probe_evidence,
                )
            except Exception as exc:
                verification_exception_type = type(exc).__name__
            if verification is not None and verification.phase is not request.phase:
                verification = None
                verification_exception_type = "FaultPhaseMismatch"

            identity_matches = _fault_identity_matches(arm, verification)
            reentry_action: str | None = None
            if current.status is TargetOperationStatus.SUCCEEDED:
                reentry = claim_target_operation(
                    control_engine,
                    intent=intent,
                    dataset_run_id=uuid4(),
                    attempt=current.attempt + 1,
                )
                reentry_action = reentry.action.value

            retained = _dedupe_references(
                references,
                (arm.evidence_reference,),
                (
                    verification.evidence_reference
                    if verification is not None
                    else None,
                ),
                (
                    atomic_result.marker_reference
                    if atomic_result is not None
                    else probe_evidence.evidence_reference,
                ),
            )
            fault_verified = bool(verification and verification.triggered)
            passed = (
                execution_exception_type is not None
                and disarm_exception_type is None
                and verification_exception_type is None
                and fault_verified
                and identity_matches
                and probe_evidence.resolution is UnknownOutcomeResolution.COMMITTED
                and current.status is TargetOperationStatus.SUCCEEDED
                and reentry_action == TargetOperationAction.SKIP_SUCCEEDED.value
                and atomic_result is not None
            )
            if execution_exception_type is None:
                failure_reason = "NO_PROVIDER_OR_DRIVER_EXCEPTION"
            elif disarm_exception_type is not None:
                failure_reason = "FAULT_DISARM_FAILED"
            elif verification_exception_type is not None:
                failure_reason = "FAULT_VERIFICATION_FAILED"
            elif not fault_verified:
                failure_reason = "FAULT_NOT_VERIFIED"
            elif not identity_matches:
                failure_reason = "FAULT_IDENTITY_MISMATCH"
            elif probe_evidence.resolution is not UnknownOutcomeResolution.COMMITTED:
                failure_reason = f"MARKER_{probe_evidence.resolution.value}"
            elif current.status is not TargetOperationStatus.SUCCEEDED:
                failure_reason = f"FINAL_{current.status.value}"
            elif reentry_action != TargetOperationAction.SKIP_SUCCEEDED.value:
                failure_reason = "REENTRY_NOT_SKIP_SUCCEEDED"
            else:
                failure_reason = None

            status = IntegrationEvidenceStatus.PASS if passed else IntegrationEvidenceStatus.FAIL
            native_operation_id = (
                atomic_result.marker.native_operation_id
                if atomic_result is not None
                else probe_evidence.native_operation_id
            )
            reports.append(
                _report(
                    run_config=run_config,
                    intent=intent,
                    dataset_run_id=dataset_run_id,
                    request=request,
                    arm=arm,
                    status=status,
                    references=retained,
                    provider_exception_observed=execution_exception_type is not None,
                    execution_exception_type=execution_exception_type,
                    disarm_exception_type=disarm_exception_type,
                    verification_exception_type=verification_exception_type,
                    verification=verification,
                    identity_matches=identity_matches,
                    atomic_result=atomic_result,
                    probe_resolution=probe_evidence.resolution,
                    final_status=current.status,
                    reentry_action=reentry_action,
                    failure_reason=failure_reason,
                )
            )
            return _build_result(
                check_id=check_id,
                status=status,
                intent=intent,
                dataset_run_id=dataset_run_id,
                native_operation_id=native_operation_id,
                evidence_references=retained,
                detail_code=failure_reason or "REAL_FAULT_COMMITTED_RECOVERED",
            )
        finally:
            warehouse_engine.dispose()
            control_engine.dispose()

    manifest = run_integration_evidence(spec, runners={check_id: runner})
    return ApprovedWarehouseFaultDrillExecution(
        plan=plan,
        manifest=manifest,
        report=reports[0] if reports else None,
    )


__all__ = [
    "ApprovedWarehouseFaultDrillConfig",
    "ApprovedWarehouseFaultDrillExecution",
    "ApprovedWarehouseFaultDrillReport",
    "execute_approved_warehouse_fault_drill",
    "load_approved_warehouse_fault_drill_config",
]
