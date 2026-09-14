"""Typed execution stages for the approved Fabric Warehouse fault drill."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine

from fabric_data_framework.contracts.audit_safety import assert_safe_retained_text
from fabric_data_framework.contracts.recovery import UnknownOutcomeResolution
from fabric_data_framework.contracts.target_operation import (
    TargetOperationAction,
    TargetOperationClaim,
    TargetOperationIntent,
    TargetOperationRecord,
    TargetOperationStatus,
)
from fabric_data_framework.control_plane.certification import get_control_plane_backend_profile
from fabric_data_framework.control_plane.sqlalchemy_repository import (
    SqlAlchemyControlPlaneRepository,
)
from fabric_data_framework.control_plane.target_operation_journal import (
    claim_target_operation,
    mark_target_operation_not_committed,
    mark_target_operation_unknown,
)
from fabric_data_framework.deployment.delivery import config_bundle_hash
from fabric_data_framework.deployment.contracts import ReleaseManifest
from fabric_data_framework.extensions import ExtensionKind, ExtensionRegistry
from fabric_data_framework.metadata.config import DatasetConfig, resolve_effective_config
from fabric_data_framework.recovery.fabric_warehouse import (
    FabricWarehouseAtomicMutationResult,
    FabricWarehouseMarkerStore,
    FabricWarehouseTargetCommitProbe,
)
from fabric_data_framework.recovery.fabric_warehouse_session_absence import (
    FabricWarehouseSessionAuthority,
    FabricWarehouseSessionBinding,
    FabricWarehouseSessionTerminationAbsenceCertifier,
)
from fabric_data_framework.recovery.target_probe import (
    TargetCommitProbeEvidence,
    probe_and_reconcile_target_operation,
)
from fabric_data_framework.recovery.warehouse_fault_injection import (
    FabricWarehouseCommitFaultArmEvidence,
    FabricWarehouseCommitFaultInjector,
    FabricWarehouseCommitFaultRequest,
    FabricWarehouseCommitFaultVerification,
)

from ..evidence import (
    IntegrationEvidenceCheckKind,
    IntegrationEvidenceCheckResult,
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
    run_integration_evidence,
    validate_integration_evidence_manifest,
)
from ..runner import (
    ApprovedIntegrationRunPlan,
    ApprovedIntegrationRunnerConfig,
    build_approved_integration_run_plan,
)
from .warehouse_fault import (
    ApprovedWarehouseFaultDrillConfig,
    ApprovedWarehouseFaultDrillExecution,
    ApprovedWarehouseFaultDrillReport,
    EngineFactory,
    MarkerStoreFactory,
    SessionAuthorityFactory,
    SessionBindingCapture,
    WarehouseFaultInjectorFactory,
    WarehouseMutationExtension,
)


@dataclass(frozen=True)
class WarehouseFaultDrillRequest:
    config: ApprovedIntegrationRunnerConfig
    spec: IntegrationEvidenceSpec
    prerequisite_manifest: IntegrationEvidenceManifest
    release_manifest: ReleaseManifest
    configs: tuple[DatasetConfig, ...]
    run_config: ApprovedWarehouseFaultDrillConfig
    environ: Mapping[str, str]
    evidence_references: tuple[str, ...]
    allow_warehouse_fault_injection: bool
    allow_warehouse_session_termination: bool


@dataclass(frozen=True)
class WarehouseFaultDrillServices:
    extension_registry: ExtensionRegistry | None
    control_engine_factory: EngineFactory
    warehouse_engine_factory: EngineFactory
    warehouse_admin_engine_factory: EngineFactory
    marker_store_factory: MarkerStoreFactory
    session_binding_capture: SessionBindingCapture
    session_authority_factory: SessionAuthorityFactory


@dataclass(frozen=True)
class WarehouseFaultPreflight:
    plan: ApprovedIntegrationRunPlan
    selected_dataset: DatasetConfig
    references: tuple[str, ...]
    mutation_extension: WarehouseMutationExtension
    fault_factory: WarehouseFaultInjectorFactory
    intent: TargetOperationIntent
    control_database_url: str
    warehouse_database_url: str


@dataclass(frozen=True)
class FaultMutationOutcome:
    dataset_run_id: UUID
    claim: TargetOperationClaim
    fault_request: FabricWarehouseCommitFaultRequest
    arm: FabricWarehouseCommitFaultArmEvidence
    atomic_result: FabricWarehouseAtomicMutationResult | None
    session_binding: FabricWarehouseSessionBinding | None
    session_binding_capture_exception_type: str | None
    execution_exception_type: str | None
    disarm_exception_type: str | None


@dataclass(frozen=True)
class FaultProbeOutcome:
    probe_evidence: TargetCommitProbeEvidence
    record: TargetOperationRecord
    atomic_result: FabricWarehouseAtomicMutationResult | None


@dataclass(frozen=True)
class FaultVerificationOutcome:
    verification: FabricWarehouseCommitFaultVerification | None
    verification_exception_type: str | None
    identity_matches: bool
    fault_verified: bool


@dataclass(frozen=True)
class SessionRecoveryOutcome:
    probe_evidence: TargetCommitProbeEvidence
    record: TargetOperationRecord
    atomic_result: FabricWarehouseAtomicMutationResult | None
    attempted: bool
    exception_type: str | None
    absence_safe_to_retry: bool | None


@dataclass(frozen=True)
class WarehouseFaultAssessment:
    status: IntegrationEvidenceStatus
    failure_reason: str | None
    reentry_action: str | None
    retry_eligible: bool
    references: tuple[str, ...]
    native_operation_id: str | None


@dataclass(frozen=True)
class WarehouseFaultDrillTrace:
    mutation: FaultMutationOutcome
    probe: FaultProbeOutcome | None
    verification: FaultVerificationOutcome | None
    recovery: SessionRecoveryOutcome | None
    assessment: WarehouseFaultAssessment


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
    request: WarehouseFaultDrillRequest,
) -> DatasetConfig:
    if request.release_manifest.domain != request.config.domain:
        raise ValueError("release manifest and approved runner config domain differ")
    if (
        request.release_manifest.bundle.framework_version
        != request.config.framework_version
    ):
        raise ValueError("release manifest and approved runner framework version differ")
    if (
        config_bundle_hash(request.configs)
        != request.release_manifest.bundle.config_bundle_hash
    ):
        raise ValueError("dataset config bundle hash does not match exact release manifest")
    for artifact_name, label in (
        (request.run_config.mutation_extension_artifact_name, "mutation"),
        (request.run_config.fault_injector_artifact_name, "fault injector"),
    ):
        if artifact_name not in request.release_manifest.artifact_sha256:
            raise ValueError(
                f"approved Warehouse {label} extension artifact is not fingerprinted in the "
                "exact release manifest"
            )
    by_id = {item.dataset_id: item for item in request.configs}
    if len(by_id) != len(request.configs):
        raise ValueError(
            "approved Warehouse fault config bundle contains duplicate dataset_id values"
        )
    selected = by_id.get(request.run_config.dataset_id)
    if selected is None:
        raise ValueError(
            "approved Warehouse fault dataset "
            f"{request.run_config.dataset_id!r} is absent from release bundle"
        )
    return selected


def _validate_session_termination_preflight(
    request: WarehouseFaultDrillRequest,
) -> None:
    if not request.run_config.enable_session_termination_recovery:
        return
    if not request.allow_warehouse_session_termination:
        raise ValueError(
            "Warehouse session termination recovery is not explicitly authorized"
        )
    env_var = request.config.warehouse_admin_database_url_env_var
    if env_var is None:
        raise ValueError(
            "session termination recovery requires warehouse_admin_database_url_env_var"
        )
    value = request.environ.get(env_var)
    if not value or not value.strip():
        raise ValueError(
            "approved Warehouse fault-drill preflight is not ready: missing runtime env vars="
            + env_var
        )


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


def _preflight(
    request: WarehouseFaultDrillRequest,
    services: WarehouseFaultDrillServices,
) -> WarehouseFaultPreflight:
    check_id = request.run_config.check_id
    plan = build_approved_integration_run_plan(
        request.config,
        request.spec,
        environ=request.environ,
        selected_check_ids=(check_id,),
        allow_mutating_checks=request.allow_warehouse_fault_injection,
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
            "approved Warehouse fault-drill preflight is not ready: "
            + "; ".join(reasons)
        )

    selected_spec = {item.check_id: item for item in request.spec.checks}[check_id]
    if (
        selected_spec.kind
        is not IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL
    ):
        raise ValueError(
            "approved Warehouse fault runner requires "
            "FABRIC_WAREHOUSE_AMBIGUOUS_COMMIT_DRILL check kind"
        )
    _require_prerequisites(
        request.spec,
        request.prerequisite_manifest,
        selected_check_id=check_id,
    )
    selected_dataset = _require_exact_release_dataset(request)
    if (
        request.config.control_plane_profile is None
        or request.config.control_plane_database_url_env_var is None
    ):
        raise ValueError(
            "approved Warehouse fault runner requires control-plane configuration"
        )
    if request.config.warehouse_database_url_env_var is None:
        raise ValueError(
            "approved Warehouse fault runner requires warehouse_database_url_env_var"
        )
    profile = get_control_plane_backend_profile(request.config.control_plane_profile)
    if not profile.production_eligible:
        raise ValueError(
            "approved Warehouse fault runner requires a production-eligible control-plane profile"
        )
    _validate_session_termination_preflight(request)

    references = request.evidence_references
    if not references:
        raise ValueError(
            "approved Warehouse fault drill requires retained evidence references"
        )
    for index, reference in enumerate(references):
        assert_safe_retained_text(reference, f"evidence_references[{index}]")

    mutation_extension, fault_factory = _resolve_extensions(
        request.run_config,
        services.extension_registry,
    )
    effective = resolve_effective_config(selected_dataset)
    intent = TargetOperationIntent(
        dataset_id=selected_dataset.dataset_id,
        operation_kind=request.run_config.operation_kind,
        target_reference=request.run_config.target_reference,
        effective_config_hash=effective.effective_config_hash,
        input_fingerprint=request.run_config.input_fingerprint,
    )

    # Secret-bearing ordinary runtime values are retrieved only after all non-secret gates pass.
    control_database_url = request.environ[
        request.config.control_plane_database_url_env_var
    ]
    warehouse_database_url = request.environ[
        request.config.warehouse_database_url_env_var
    ]
    return WarehouseFaultPreflight(
        plan=plan,
        selected_dataset=selected_dataset,
        references=references,
        mutation_extension=mutation_extension,
        fault_factory=fault_factory,
        intent=intent,
        control_database_url=control_database_url,
        warehouse_database_url=warehouse_database_url,
    )


def _validate_deployed_identity(
    control_engine: Engine,
    *,
    request: WarehouseFaultDrillRequest,
    preflight: WarehouseFaultPreflight,
) -> None:
    repository = SqlAlchemyControlPlaneRepository(
        control_engine,
        domain=request.config.domain,
        domain_git_sha=request.release_manifest.bundle.domain_git_sha,
        framework_version=request.config.framework_version,
        configs=request.configs,
    )
    deployed = repository.get_dataset(preflight.selected_dataset.dataset_id)
    if deployed.config_hash != preflight.selected_dataset.config_hash:
        raise RuntimeError(
            "approved Warehouse fault drill deployed/release config identity mismatch"
        )


def _claim_fresh_operation(
    control_engine: Engine,
    preflight: WarehouseFaultPreflight,
    dataset_run_id: UUID,
) -> TargetOperationClaim:
    return claim_target_operation(
        control_engine,
        intent=preflight.intent,
        dataset_run_id=dataset_run_id,
        attempt=1,
    )


def _build_fault_request(
    intent: TargetOperationIntent,
    dataset_run_id: UUID,
) -> FabricWarehouseCommitFaultRequest:
    return FabricWarehouseCommitFaultRequest(
        operation_key=intent.operation_key,
        dataset_id=intent.dataset_id,
        dataset_run_id=dataset_run_id,
        attempt=1,
        target_reference=intent.target_reference,
    )


def _arm_fault(
    warehouse_engine: Engine,
    *,
    request: WarehouseFaultDrillRequest,
    preflight: WarehouseFaultPreflight,
    fault_request: FabricWarehouseCommitFaultRequest,
) -> tuple[FabricWarehouseCommitFaultInjector, FabricWarehouseCommitFaultArmEvidence]:
    injector = preflight.fault_factory(
        warehouse_engine,
        fault_request,
        request.run_config.fault_payload,
    )
    if not isinstance(injector, FabricWarehouseCommitFaultInjector):
        raise TypeError(
            "Warehouse fault injector extension did not return the required controller"
        )
    arm = injector.arm(fault_request)
    if arm.phase is not fault_request.phase:
        raise ValueError("Warehouse fault injector armed the wrong fault phase")
    return injector, arm


def _execute_faulted_mutation(
    marker_store: FabricWarehouseMarkerStore,
    injector: FabricWarehouseCommitFaultInjector,
    *,
    request: WarehouseFaultDrillRequest,
    services: WarehouseFaultDrillServices,
    preflight: WarehouseFaultPreflight,
    claim: TargetOperationClaim,
    dataset_run_id: UUID,
    fault_request: FabricWarehouseCommitFaultRequest,
    arm: FabricWarehouseCommitFaultArmEvidence,
) -> FaultMutationOutcome:
    session_binding: FabricWarehouseSessionBinding | None = None
    session_binding_capture_exception_type: str | None = None

    def mutation(connection, observed_intent):
        nonlocal session_binding, session_binding_capture_exception_type
        if (
            request.run_config.enable_session_termination_recovery
            and session_binding is None
        ):
            try:
                session_binding = services.session_binding_capture(connection)
            except Exception as exc:
                session_binding_capture_exception_type = type(exc).__name__
                raise
        return preflight.mutation_extension(
            connection,
            observed_intent,
            request.run_config.mutation_payload,
        )

    atomic_result: FabricWarehouseAtomicMutationResult | None = None
    execution_exception_type: str | None = None
    disarm_exception_type: str | None = None
    try:
        atomic_result = marker_store.execute_atomic(
            intent=preflight.intent,
            dataset_run_id=dataset_run_id,
            attempt=1,
            mutation=mutation,
        )
    except Exception as exc:
        execution_exception_type = type(exc).__name__
    finally:
        try:
            injector.disarm(fault_request)
        except Exception as exc:
            disarm_exception_type = type(exc).__name__

    return FaultMutationOutcome(
        dataset_run_id=dataset_run_id,
        claim=claim,
        fault_request=fault_request,
        arm=arm,
        atomic_result=atomic_result,
        session_binding=session_binding,
        session_binding_capture_exception_type=session_binding_capture_exception_type,
        execution_exception_type=execution_exception_type,
        disarm_exception_type=disarm_exception_type,
    )


def _mark_unknown_and_probe(
    control_engine: Engine,
    marker_store: FabricWarehouseMarkerStore,
    plain_probe: FabricWarehouseTargetCommitProbe,
    *,
    preflight: WarehouseFaultPreflight,
    mutation: FaultMutationOutcome,
) -> FaultProbeOutcome:
    unknown = mark_target_operation_unknown(
        control_engine,
        operation_key=preflight.intent.operation_key,
        expected_version=mutation.claim.record.version,
        dataset_run_id=mutation.dataset_run_id,
        attempt=1,
        error_message=(
            "approved Warehouse fault drill observed provider/driver exception "
            f"{mutation.execution_exception_type}"
            if mutation.execution_exception_type is not None
            else "approved Warehouse fault drill target transaction returned without exception"
        ),
        outcome_reference=(
            mutation.atomic_result.marker_reference
            if mutation.atomic_result is not None
            else None
        ),
    )
    reconciled = probe_and_reconcile_target_operation(
        control_engine,
        operation_key=preflight.intent.operation_key,
        dataset_run_id=uuid4(),
        attempt=max(2, unknown.attempt + 1),
        probe=plain_probe,
    )
    atomic_result = mutation.atomic_result
    if (
        atomic_result is None
        and reconciled.evidence.resolution is UnknownOutcomeResolution.COMMITTED
    ):
        atomic_result = _atomic_from_committed_marker(marker_store, preflight.intent)
    return FaultProbeOutcome(
        probe_evidence=reconciled.evidence,
        record=reconciled.record,
        atomic_result=atomic_result,
    )


def _verify_fault(
    injector: FabricWarehouseCommitFaultInjector,
    *,
    mutation: FaultMutationOutcome,
    probe: FaultProbeOutcome,
) -> FaultVerificationOutcome:
    verification: FabricWarehouseCommitFaultVerification | None = None
    verification_exception_type: str | None = None
    try:
        verification = injector.verify(
            mutation.fault_request,
            observed_exception_type=mutation.execution_exception_type,
            probe_evidence=probe.probe_evidence,
        )
    except Exception as exc:
        verification_exception_type = type(exc).__name__
    if (
        verification is not None
        and verification.phase is not mutation.fault_request.phase
    ):
        verification = None
        verification_exception_type = "FaultPhaseMismatch"
    identity_matches = _fault_identity_matches(mutation.arm, verification)
    return FaultVerificationOutcome(
        verification=verification,
        verification_exception_type=verification_exception_type,
        identity_matches=identity_matches,
        fault_verified=bool(verification and verification.triggered),
    )


def _session_recovery_eligible(
    request: WarehouseFaultDrillRequest,
    mutation: FaultMutationOutcome,
    probe: FaultProbeOutcome,
    verification: FaultVerificationOutcome,
) -> bool:
    return (
        request.run_config.enable_session_termination_recovery
        and mutation.execution_exception_type is not None
        and mutation.session_binding_capture_exception_type is None
        and mutation.session_binding is not None
        and mutation.disarm_exception_type is None
        and verification.verification_exception_type is None
        and verification.fault_verified
        and verification.identity_matches
        and probe.probe_evidence.resolution is UnknownOutcomeResolution.UNRESOLVED
        and probe.record.status is TargetOperationStatus.UNKNOWN
    )


def _recover_session(
    control_engine: Engine,
    marker_store: FabricWarehouseMarkerStore,
    plain_probe: FabricWarehouseTargetCommitProbe,
    *,
    request: WarehouseFaultDrillRequest,
    services: WarehouseFaultDrillServices,
    preflight: WarehouseFaultPreflight,
    mutation: FaultMutationOutcome,
    probe: FaultProbeOutcome,
    verification: FaultVerificationOutcome,
) -> SessionRecoveryOutcome:
    if not _session_recovery_eligible(request, mutation, probe, verification):
        return SessionRecoveryOutcome(
            probe_evidence=probe.probe_evidence,
            record=probe.record,
            atomic_result=probe.atomic_result,
            attempted=False,
            exception_type=None,
            absence_safe_to_retry=None,
        )

    admin_engine: Engine | None = None
    try:
        admin_env_var = request.config.warehouse_admin_database_url_env_var
        assert admin_env_var is not None
        # Read Admin credentials only after the exact unresolved verified-fault gate.
        admin_database_url = request.environ[admin_env_var]
        admin_engine = services.warehouse_admin_engine_factory(admin_database_url)
        authority = services.session_authority_factory(admin_engine)
        if not isinstance(authority, FabricWarehouseSessionAuthority):
            raise TypeError(
                "Warehouse session authority factory returned an invalid controller"
            )
        assert mutation.session_binding is not None
        absence_certifier = FabricWarehouseSessionTerminationAbsenceCertifier(
            binding=mutation.session_binding,
            authority=authority,
            marker_store=marker_store,
        )
        recovery_probe = FabricWarehouseTargetCommitProbe(
            marker_store=marker_store,
            absence_certifier=absence_certifier,
        )
        recovered = probe_and_reconcile_target_operation(
            control_engine,
            operation_key=preflight.intent.operation_key,
            dataset_run_id=uuid4(),
            attempt=max(2, probe.record.attempt + 1),
            probe=recovery_probe,
        )
        probe_evidence = recovered.evidence
        record = recovered.record
        atomic_result = probe.atomic_result
        absence_safe_to_retry = (
            probe_evidence.resolution is UnknownOutcomeResolution.NOT_COMMITTED
            and record.status is TargetOperationStatus.NOT_COMMITTED
        )

        # A marker can win the termination race. Only an observed marker may upgrade
        # unresolved state; absence alone never proves a commit.
        if (
            probe_evidence.resolution is UnknownOutcomeResolution.UNRESOLVED
            and record.status is TargetOperationStatus.UNKNOWN
        ):
            final_probe = probe_and_reconcile_target_operation(
                control_engine,
                operation_key=preflight.intent.operation_key,
                dataset_run_id=uuid4(),
                attempt=max(2, record.attempt + 1),
                probe=plain_probe,
            )
            probe_evidence = final_probe.evidence
            record = final_probe.record
            if (
                atomic_result is None
                and probe_evidence.resolution is UnknownOutcomeResolution.COMMITTED
            ):
                atomic_result = _atomic_from_committed_marker(
                    marker_store,
                    preflight.intent,
                )
        return SessionRecoveryOutcome(
            probe_evidence=probe_evidence,
            record=record,
            atomic_result=atomic_result,
            attempted=True,
            exception_type=None,
            absence_safe_to_retry=absence_safe_to_retry,
        )
    except Exception as exc:
        return SessionRecoveryOutcome(
            probe_evidence=probe.probe_evidence,
            record=probe.record,
            atomic_result=probe.atomic_result,
            attempted=True,
            exception_type=type(exc).__name__,
            absence_safe_to_retry=None,
        )
    finally:
        if admin_engine is not None:
            admin_engine.dispose()


def _claim_reentry(
    control_engine: Engine,
    *,
    preflight: WarehouseFaultPreflight,
    record: TargetOperationRecord,
) -> str | None:
    if record.status is not TargetOperationStatus.SUCCEEDED:
        return None
    reentry = claim_target_operation(
        control_engine,
        intent=preflight.intent,
        dataset_run_id=uuid4(),
        attempt=record.attempt + 1,
    )
    return reentry.action.value


def _failure_reason(
    request: WarehouseFaultDrillRequest,
    mutation: FaultMutationOutcome,
    verification: FaultVerificationOutcome,
    recovery: SessionRecoveryOutcome,
    *,
    reentry_action: str | None,
    retry_eligible: bool,
) -> str | None:
    if mutation.session_binding_capture_exception_type is not None:
        return "SESSION_BINDING_CAPTURE_FAILED"
    if mutation.execution_exception_type is None:
        return "NO_PROVIDER_OR_DRIVER_EXCEPTION"
    if mutation.disarm_exception_type is not None:
        return "FAULT_DISARM_FAILED"
    if verification.verification_exception_type is not None:
        return "FAULT_VERIFICATION_FAILED"
    if not verification.fault_verified:
        return "FAULT_NOT_VERIFIED"
    if not verification.identity_matches:
        return "FAULT_IDENTITY_MISMATCH"
    if recovery.exception_type is not None:
        return "SESSION_TERMINATION_RECOVERY_FAILED"
    if retry_eligible and recovery.absence_safe_to_retry:
        return "SAFE_NOT_COMMITTED_AFTER_SESSION_TERMINATION"
    if (
        request.run_config.enable_session_termination_recovery
        and recovery.probe_evidence.resolution is UnknownOutcomeResolution.UNRESOLVED
        and mutation.session_binding is None
    ):
        return "SESSION_BINDING_NOT_CAPTURED"
    if recovery.probe_evidence.resolution is not UnknownOutcomeResolution.COMMITTED:
        return f"MARKER_{recovery.probe_evidence.resolution.value}"
    if recovery.record.status is not TargetOperationStatus.SUCCEEDED:
        return f"FINAL_{recovery.record.status.value}"
    if reentry_action != TargetOperationAction.SKIP_SUCCEEDED.value:
        return "REENTRY_NOT_SKIP_SUCCEEDED"
    return None


def _assess(
    control_engine: Engine,
    *,
    request: WarehouseFaultDrillRequest,
    preflight: WarehouseFaultPreflight,
    mutation: FaultMutationOutcome,
    verification: FaultVerificationOutcome,
    recovery: SessionRecoveryOutcome,
) -> WarehouseFaultAssessment:
    reentry_action = _claim_reentry(
        control_engine,
        preflight=preflight,
        record=recovery.record,
    )
    retry_eligible = recovery.record.status is TargetOperationStatus.NOT_COMMITTED
    passed = (
        mutation.execution_exception_type is not None
        and mutation.session_binding_capture_exception_type is None
        and mutation.disarm_exception_type is None
        and verification.verification_exception_type is None
        and verification.fault_verified
        and verification.identity_matches
        and recovery.probe_evidence.resolution is UnknownOutcomeResolution.COMMITTED
        and recovery.record.status is TargetOperationStatus.SUCCEEDED
        and reentry_action == TargetOperationAction.SKIP_SUCCEEDED.value
        and recovery.atomic_result is not None
    )
    failure_reason = _failure_reason(
        request,
        mutation,
        verification,
        recovery,
        reentry_action=reentry_action,
        retry_eligible=retry_eligible,
    )
    references = _dedupe_references(
        preflight.references,
        (mutation.arm.evidence_reference,),
        (
            verification.verification.evidence_reference
            if verification.verification is not None
            else None,
        ),
        (
            recovery.atomic_result.marker_reference
            if recovery.atomic_result is not None
            else recovery.probe_evidence.evidence_reference,
        ),
        (
            mutation.session_binding.evidence_reference
            if mutation.session_binding is not None and recovery.attempted
            else None,
        ),
    )
    native_operation_id = (
        recovery.atomic_result.marker.native_operation_id
        if recovery.atomic_result is not None
        else recovery.probe_evidence.native_operation_id
    )
    return WarehouseFaultAssessment(
        status=(
            IntegrationEvidenceStatus.PASS
            if passed
            else IntegrationEvidenceStatus.FAIL
        ),
        failure_reason=failure_reason,
        reentry_action=reentry_action,
        retry_eligible=retry_eligible,
        references=references,
        native_operation_id=native_operation_id,
    )


def _report_from_trace(
    request: WarehouseFaultDrillRequest,
    preflight: WarehouseFaultPreflight,
    trace: WarehouseFaultDrillTrace,
) -> ApprovedWarehouseFaultDrillReport:
    mutation = trace.mutation
    verification = trace.verification
    recovery = trace.recovery
    observed_verification = (
        verification.verification if verification is not None else None
    )
    atomic_result = (
        recovery.atomic_result
        if recovery is not None
        else mutation.atomic_result
    )
    final_status = recovery.record.status if recovery is not None else None
    probe_resolution = (
        recovery.probe_evidence.resolution if recovery is not None else None
    )
    return ApprovedWarehouseFaultDrillReport(
        check_id=request.run_config.check_id,
        run_config_hash=request.run_config.run_config_hash,
        operation_key=preflight.intent.operation_key,
        dataset_run_id=mutation.dataset_run_id,
        target_reference=preflight.intent.target_reference,
        fault_phase=mutation.fault_request.phase,
        fault_armed=mutation.arm.armed,
        provider_exception_observed=mutation.execution_exception_type is not None,
        execution_exception_type=mutation.execution_exception_type,
        disarm_exception_type=mutation.disarm_exception_type,
        verification_exception_type=(
            verification.verification_exception_type
            if verification is not None
            else None
        ),
        fault_verified=bool(observed_verification and observed_verification.triggered),
        fault_identity_matches=bool(
            verification and verification.identity_matches
        ),
        fault_evidence_reference=(
            observed_verification.evidence_reference
            if observed_verification is not None
            else mutation.arm.evidence_reference
        ),
        provider_fault_id=(
            observed_verification.provider_fault_id
            if observed_verification is not None
            else mutation.arm.provider_fault_id
        ),
        marker_reference=(
            atomic_result.marker_reference if atomic_result is not None else None
        ),
        probe_resolution=probe_resolution,
        final_status=final_status,
        reentry_action=trace.assessment.reentry_action,
        session_termination_recovery_enabled=(
            request.run_config.enable_session_termination_recovery
        ),
        session_termination_authorized=(
            request.allow_warehouse_session_termination
        ),
        session_binding_captured=mutation.session_binding is not None,
        session_id=(
            mutation.session_binding.session_id
            if mutation.session_binding is not None
            else None
        ),
        connection_id=(
            mutation.session_binding.connection_id
            if mutation.session_binding is not None
            else None
        ),
        session_binding_capture_exception_type=(
            mutation.session_binding_capture_exception_type
        ),
        session_termination_recovery_attempted=bool(
            recovery and recovery.attempted
        ),
        session_recovery_exception_type=(
            recovery.exception_type if recovery is not None else None
        ),
        absence_safe_to_retry=(
            recovery.absence_safe_to_retry if recovery is not None else None
        ),
        retry_eligible=trace.assessment.retry_eligible,
        evidence_status=trace.assessment.status,
        failure_reason=trace.assessment.failure_reason,
        evidence_references=trace.assessment.references,
    )


def _fault_not_armed(
    control_engine: Engine,
    *,
    request: WarehouseFaultDrillRequest,
    preflight: WarehouseFaultPreflight,
    dataset_run_id: UUID,
    claim: TargetOperationClaim,
    fault_request: FabricWarehouseCommitFaultRequest,
    arm: FabricWarehouseCommitFaultArmEvidence,
) -> tuple[IntegrationEvidenceCheckResult, ApprovedWarehouseFaultDrillReport]:
    current = mark_target_operation_not_committed(
        control_engine,
        operation_key=preflight.intent.operation_key,
        expected_version=claim.record.version,
        dataset_run_id=dataset_run_id,
        attempt=1,
        outcome_reference=arm.evidence_reference,
    )
    retained = _dedupe_references(
        preflight.references,
        (arm.evidence_reference,),
    )
    mutation = FaultMutationOutcome(
        dataset_run_id=dataset_run_id,
        claim=claim,
        fault_request=fault_request,
        arm=arm,
        atomic_result=None,
        session_binding=None,
        session_binding_capture_exception_type=None,
        execution_exception_type=None,
        disarm_exception_type=None,
    )
    assessment = WarehouseFaultAssessment(
        status=IntegrationEvidenceStatus.FAIL,
        failure_reason="FAULT_NOT_ARMED",
        reentry_action=None,
        retry_eligible=True,
        references=retained,
        native_operation_id=None,
    )
    trace = WarehouseFaultDrillTrace(
        mutation=mutation,
        probe=None,
        verification=None,
        recovery=None,
        assessment=assessment,
    )
    report = _report_from_trace(request, preflight, trace).model_copy(
        update={"final_status": current.status}
    )
    result = _build_result(
        check_id=request.run_config.check_id,
        status=IntegrationEvidenceStatus.FAIL,
        intent=preflight.intent,
        dataset_run_id=dataset_run_id,
        native_operation_id=None,
        evidence_references=retained,
        detail_code="FAULT_NOT_ARMED",
    )
    return result, report


def _run_one(
    request: WarehouseFaultDrillRequest,
    services: WarehouseFaultDrillServices,
    preflight: WarehouseFaultPreflight,
) -> tuple[IntegrationEvidenceCheckResult, ApprovedWarehouseFaultDrillReport | None]:
    control_engine = services.control_engine_factory(preflight.control_database_url)
    warehouse_engine = services.warehouse_engine_factory(
        preflight.warehouse_database_url
    )
    dataset_run_id = uuid4()
    try:
        _validate_deployed_identity(
            control_engine,
            request=request,
            preflight=preflight,
        )
        marker_store = services.marker_store_factory(
            warehouse_engine,
            request.run_config,
        )
        plain_probe = FabricWarehouseTargetCommitProbe(marker_store=marker_store)
        claim = _claim_fresh_operation(
            control_engine,
            preflight,
            dataset_run_id,
        )
        if claim.action is not TargetOperationAction.EXECUTE:
            return (
                _build_result(
                    check_id=request.run_config.check_id,
                    status=IntegrationEvidenceStatus.FAIL,
                    intent=preflight.intent,
                    dataset_run_id=dataset_run_id,
                    native_operation_id=None,
                    evidence_references=preflight.references,
                    detail_code=f"FRESH_EXECUTE_REQUIRED_{claim.action.value}",
                ),
                None,
            )

        fault_request = _build_fault_request(preflight.intent, dataset_run_id)
        injector, arm = _arm_fault(
            warehouse_engine,
            request=request,
            preflight=preflight,
            fault_request=fault_request,
        )
        if not arm.armed:
            return _fault_not_armed(
                control_engine,
                request=request,
                preflight=preflight,
                dataset_run_id=dataset_run_id,
                claim=claim,
                fault_request=fault_request,
                arm=arm,
            )

        mutation = _execute_faulted_mutation(
            marker_store,
            injector,
            request=request,
            services=services,
            preflight=preflight,
            claim=claim,
            dataset_run_id=dataset_run_id,
            fault_request=fault_request,
            arm=arm,
        )
        probe = _mark_unknown_and_probe(
            control_engine,
            marker_store,
            plain_probe,
            preflight=preflight,
            mutation=mutation,
        )
        verification = _verify_fault(
            injector,
            mutation=mutation,
            probe=probe,
        )
        recovery = _recover_session(
            control_engine,
            marker_store,
            plain_probe,
            request=request,
            services=services,
            preflight=preflight,
            mutation=mutation,
            probe=probe,
            verification=verification,
        )
        assessment = _assess(
            control_engine,
            request=request,
            preflight=preflight,
            mutation=mutation,
            verification=verification,
            recovery=recovery,
        )
        trace = WarehouseFaultDrillTrace(
            mutation=mutation,
            probe=probe,
            verification=verification,
            recovery=recovery,
            assessment=assessment,
        )
        report = _report_from_trace(request, preflight, trace)
        result = _build_result(
            check_id=request.run_config.check_id,
            status=assessment.status,
            intent=preflight.intent,
            dataset_run_id=dataset_run_id,
            native_operation_id=assessment.native_operation_id,
            evidence_references=assessment.references,
            detail_code=(
                assessment.failure_reason
                or "REAL_FAULT_COMMITTED_RECOVERED"
            ),
        )
        return result, report
    finally:
        warehouse_engine.dispose()
        control_engine.dispose()


def execute_approved_warehouse_fault_drill_staged(
    request: WarehouseFaultDrillRequest,
    services: WarehouseFaultDrillServices,
) -> ApprovedWarehouseFaultDrillExecution:
    """Run the exact fault drill through explicit fail-closed typed stages."""

    preflight = _preflight(request, services)
    reports: list[ApprovedWarehouseFaultDrillReport] = []

    def runner() -> IntegrationEvidenceCheckResult:
        result, report = _run_one(request, services, preflight)
        if report is not None:
            reports.append(report)
        return result

    manifest = run_integration_evidence(
        request.spec,
        runners={request.run_config.check_id: runner},
    )
    return ApprovedWarehouseFaultDrillExecution(
        plan=preflight.plan,
        manifest=manifest,
        report=reports[0] if reports else None,
    )


__all__ = [
    "WarehouseFaultDrillRequest",
    "WarehouseFaultDrillServices",
    "execute_approved_warehouse_fault_drill_staged",
]
