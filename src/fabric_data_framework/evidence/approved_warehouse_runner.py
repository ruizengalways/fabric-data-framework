"""Exact-release approved Fabric Warehouse target-commit evidence execution.

The framework owns the SQL transaction, target-side operation marker, durable
control-plane target-operation journal and ambiguous-outcome reconciliation. A bounded
customer/domain extension may execute the representative mutation only through the
Connection supplied by the framework; it cannot commit the transaction or declare the
check PASS.

A normal successful target commit is deliberately followed by a simulated loss of the
framework acknowledgement: the control-plane operation is marked UNKNOWN and then
reconciled from the committed Warehouse marker. If the provider/driver itself raises
around ``execute_atomic``, the runner also treats the outcome as UNKNOWN and probes the
marker instead of blindly retrying.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.engine import Connection

from ..config import DatasetConfig, FrozenModel, canonical_hash, resolve_effective_config
from ..contracts.recovery import UnknownOutcomeResolution
from ..control_plane.certification import get_control_plane_backend_profile
from ..deployment.delivery import config_bundle_hash
from ..deployment.contracts import ReleaseManifest
from ..extensions import ExtensionKind, ExtensionRegistry
from .integration_checks import build_fabric_warehouse_commit_check_result
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
from ..recovery.fabric_warehouse import (
    FABRIC_WAREHOUSE_DEFAULT_MARKER_TABLE,
    FabricWarehouseAtomicMutationResult,
    FabricWarehouseMarkerStore,
    FabricWarehouseMutationEvidence,
    FabricWarehouseTargetCommitProbe,
    build_fabric_warehouse_operation_marker_table,
)
from ..recovery.target_probe import (
    TargetCommitProbeRequest,
    probe_and_reconcile_target_operation,
)
from ..control_plane.sqlalchemy_repository import SqlAlchemyControlPlaneRepository
from .safety import assert_safe_retained_text
from ..control_plane.target_operation_journal import (
    claim_target_operation,
    mark_target_operation_unknown,
    read_target_operation,
)
from ..target_operations import (
    TargetOperationAction,
    TargetOperationIntent,
    TargetOperationStatus,
)


_EXTENSION_PATTERN = r"^[a-z][a-z0-9_.-]*$"
_SQL_IDENTIFIER_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]{0,127}$"


class WarehouseAmbiguityOrigin(str, Enum):
    SIMULATED_FRAMEWORK_ACK_LOSS = "SIMULATED_FRAMEWORK_ACK_LOSS"
    PROVIDER_OR_DRIVER_EXCEPTION = "PROVIDER_OR_DRIVER_EXCEPTION"
    PREEXISTING_RECONCILE_REQUIRED = "PREEXISTING_RECONCILE_REQUIRED"
    PREEXISTING_SUCCEEDED = "PREEXISTING_SUCCEEDED"


class ApprovedWarehouseRunConfig(FrozenModel):
    """Credential-free exact-run recipe for one representative Warehouse mutation."""

    check_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    dataset_id: str = Field(min_length=1, max_length=256)
    operation_kind: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    target_reference: str = Field(min_length=1, max_length=1024)
    mutation_extension: str = Field(pattern=_EXTENSION_PATTERN)
    extension_artifact_name: str = Field(min_length=1, max_length=512)
    mutation_payload: dict[str, Any] = Field(default_factory=dict)
    marker_table_name: str = Field(
        default=FABRIC_WAREHOUSE_DEFAULT_MARKER_TABLE,
        pattern=_SQL_IDENTIFIER_PATTERN,
    )
    marker_schema: str | None = Field(default="dbo", pattern=_SQL_IDENTIFIER_PATTERN)

    @model_validator(mode="after")
    def validate_safe_recipe(self) -> "ApprovedWarehouseRunConfig":
        rendered = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
        assert_safe_retained_text(rendered, "approved Warehouse run config")
        return self

    @property
    def run_config_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))

    @property
    def input_fingerprint(self) -> str:
        return canonical_hash(self.mutation_payload)


class ApprovedWarehouseEvidenceReport(FrozenModel):
    check_id: str
    run_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_run_id: UUID
    target_reference: str
    marker_reference: str
    native_operation_id: str | None = None
    marker_executed: bool
    initial_action: str
    ambiguity_origin: WarehouseAmbiguityOrigin
    execution_exception_type: str | None = Field(default=None, max_length=256)
    probe_resolution: UnknownOutcomeResolution
    final_status: TargetOperationStatus
    reentry_action: str
    evidence_references: tuple[str, ...]

    @model_validator(mode="after")
    def validate_success_chain(self) -> "ApprovedWarehouseEvidenceReport":
        if self.probe_resolution is not UnknownOutcomeResolution.COMMITTED:
            raise ValueError("approved Warehouse PASS report requires COMMITTED marker probe")
        if self.final_status is not TargetOperationStatus.SUCCEEDED:
            raise ValueError("approved Warehouse PASS report requires SUCCEEDED journal state")
        if self.reentry_action != TargetOperationAction.SKIP_SUCCEEDED.value:
            raise ValueError("approved Warehouse PASS report requires later SKIP_SUCCEEDED")
        assert_safe_retained_text(self.model_dump_json(), "approved Warehouse evidence report")
        return self


@dataclass(frozen=True)
class ApprovedWarehouseExecution:
    plan: ApprovedIntegrationRunPlan
    manifest: IntegrationEvidenceManifest
    report: ApprovedWarehouseEvidenceReport | None


EngineFactory = Callable[[str], Engine]
WarehouseMutationExtension = Callable[
    [Connection, TargetOperationIntent, Mapping[str, Any]],
    FabricWarehouseMutationEvidence | None,
]
MarkerStoreFactory = Callable[
    [Engine, ApprovedWarehouseRunConfig],
    FabricWarehouseMarkerStore,
]


def _default_marker_store_factory(
    engine: Engine,
    run_config: ApprovedWarehouseRunConfig,
) -> FabricWarehouseMarkerStore:
    marker = build_fabric_warehouse_operation_marker_table(
        MetaData(),
        table_name=run_config.marker_table_name,
        schema=run_config.marker_schema,
    )
    return FabricWarehouseMarkerStore(engine, marker)


def load_approved_warehouse_run_config(path: str | Path) -> ApprovedWarehouseRunConfig:
    return ApprovedWarehouseRunConfig.model_validate_json(
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
    selected = results[selected_check_id]
    if selected.status is not IntegrationEvidenceStatus.NOT_RUN:
        raise ValueError(
            "approved Warehouse execution requires the selected check to remain NOT_RUN in "
            "the prerequisite manifest; explicitly select rerun evidence instead of "
            "auto-rerunning a target mutation"
        )
    for required_kind, label in (
        (IntegrationEvidenceCheckKind.FABRIC_ITEM_READ, "read-only Fabric item"),
        (
            IntegrationEvidenceCheckKind.CONTROL_PLANE_CERTIFICATION,
            "control-plane certification",
        ),
    ):
        if not any(
            item.kind is required_kind and item.status is IntegrationEvidenceStatus.PASS
            for item in prerequisite_manifest.results
        ):
            raise ValueError(
                f"approved Warehouse execution requires a retained PASS {label} prerequisite"
            )


def _require_exact_release_dataset(
    *,
    config: ApprovedIntegrationRunnerConfig,
    run_config: ApprovedWarehouseRunConfig,
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
    if run_config.extension_artifact_name not in release_manifest.artifact_sha256:
        raise ValueError(
            "approved Warehouse mutation extension artifact is not fingerprinted in the "
            "exact release manifest"
        )
    by_id = {item.dataset_id: item for item in configs}
    if len(by_id) != len(configs):
        raise ValueError("approved Warehouse config bundle contains duplicate dataset_id values")
    selected = by_id.get(run_config.dataset_id)
    if selected is None:
        raise ValueError(
            f"approved Warehouse dataset {run_config.dataset_id!r} is absent from release bundle"
        )
    return selected


def _resolve_mutation_extension(
    run_config: ApprovedWarehouseRunConfig,
    extension_registry: ExtensionRegistry | None,
) -> WarehouseMutationExtension:
    registry = extension_registry or ExtensionRegistry()
    if extension_registry is None:
        registry.discover(ExtensionKind.WAREHOUSE_MUTATION)
    return registry.factory(
        ExtensionKind.WAREHOUSE_MUTATION,
        run_config.mutation_extension,
    )


def _safe_fail_result(
    *,
    check_id: str,
    intent: TargetOperationIntent,
    dataset_run_id: UUID,
    evidence_references: tuple[str, ...],
    detail_code: str,
) -> IntegrationEvidenceCheckResult:
    assert_safe_retained_text(detail_code, "Warehouse failure detail code")
    return IntegrationEvidenceCheckResult(
        check_id=check_id,
        kind=IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT,
        status=IntegrationEvidenceStatus.FAIL,
        dataset_run_id=dataset_run_id,
        operation_key=intent.operation_key,
        evidence_references=evidence_references,
        detail=f"approved Warehouse commit/recovery chain did not PASS; reason={detail_code}",
    )


def _atomic_from_committed_marker(
    marker_store: FabricWarehouseMarkerStore,
    intent: TargetOperationIntent,
    *,
    executed: bool,
) -> FabricWarehouseAtomicMutationResult:
    markers = marker_store.read_markers(intent.operation_key)
    if not markers:
        raise RuntimeError("COMMITTED Warehouse probe had no readable operation marker")
    return FabricWarehouseAtomicMutationResult(
        marker=markers[0],
        marker_reference=marker_store.marker_reference(intent.operation_key),
        executed=executed,
    )


def execute_approved_warehouse(
    *,
    config: ApprovedIntegrationRunnerConfig,
    spec: IntegrationEvidenceSpec,
    prerequisite_manifest: IntegrationEvidenceManifest,
    release_manifest: ReleaseManifest,
    configs: Iterable[DatasetConfig],
    run_config: ApprovedWarehouseRunConfig,
    environ: Mapping[str, str],
    evidence_references: Iterable[str],
    allow_warehouse_execution: bool,
    extension_registry: ExtensionRegistry | None = None,
    control_engine_factory: EngineFactory = create_engine,
    warehouse_engine_factory: EngineFactory = create_engine,
    marker_store_factory: MarkerStoreFactory = _default_marker_store_factory,
) -> ApprovedWarehouseExecution:
    """Run same-transaction marker proof plus fail-closed UNKNOWN reconciliation."""

    config_tuple = tuple(configs)
    check_id = run_config.check_id
    plan = build_approved_integration_run_plan(
        config,
        spec,
        environ=environ,
        selected_check_ids=(check_id,),
        allow_mutating_checks=allow_warehouse_execution,
    )
    if not plan.ready:
        reasons: list[str] = []
        if plan.missing_runtime_env_vars:
            reasons.append(
                "missing runtime env vars=" + ",".join(plan.missing_runtime_env_vars)
            )
        if plan.mutating_check_ids and not plan.mutating_checks_authorized:
            reasons.append("Warehouse execution not explicitly authorized")
        raise ValueError("approved Warehouse preflight is not ready: " + "; ".join(reasons))

    selected_spec = {item.check_id: item for item in spec.checks}[check_id]
    if selected_spec.kind is not IntegrationEvidenceCheckKind.FABRIC_WAREHOUSE_TARGET_COMMIT:
        raise ValueError(
            "approved Warehouse runner requires FABRIC_WAREHOUSE_TARGET_COMMIT check kind"
        )
    _require_prerequisites(spec, prerequisite_manifest, selected_check_id=check_id)
    selected_dataset = _require_exact_release_dataset(
        config=config,
        run_config=run_config,
        release_manifest=release_manifest,
        configs=config_tuple,
    )

    if config.control_plane_profile is None or config.control_plane_database_url_env_var is None:
        raise ValueError("approved Warehouse runner requires control-plane runtime configuration")
    if config.warehouse_database_url_env_var is None:
        raise ValueError("approved Warehouse runner requires warehouse_database_url_env_var")
    profile = get_control_plane_backend_profile(config.control_plane_profile)
    if not profile.production_eligible:
        raise ValueError(
            "approved Warehouse runner requires a production-eligible control-plane profile"
        )

    references = tuple(evidence_references)
    if not references:
        raise ValueError("approved Warehouse execution requires retained evidence references")
    for index, reference in enumerate(references):
        assert_safe_retained_text(reference, f"evidence_references[{index}]")

    mutation_extension = _resolve_mutation_extension(run_config, extension_registry)
    effective = resolve_effective_config(selected_dataset)
    intent = TargetOperationIntent(
        dataset_id=selected_dataset.dataset_id,
        operation_kind=run_config.operation_kind,
        target_reference=run_config.target_reference,
        effective_config_hash=effective.effective_config_hash,
        input_fingerprint=run_config.input_fingerprint,
    )

    # Secret-bearing URL values are read only after exact release, prerequisite,
    # extension provenance, profile and explicit mutation-authorization gates pass.
    control_database_url = environ[config.control_plane_database_url_env_var]
    warehouse_database_url = environ[config.warehouse_database_url_env_var]
    report_holder: list[ApprovedWarehouseEvidenceReport] = []

    def runner() -> IntegrationEvidenceCheckResult:
        control_engine = control_engine_factory(control_database_url)
        warehouse_engine = warehouse_engine_factory(warehouse_database_url)
        dataset_run_id = uuid4()
        try:
            # This constructor is a schema/deployed-config gate. It never migrates the
            # production control plane; target_operation_io calls are no-op schema checks
            # after this exact-version validation succeeds.
            repository = SqlAlchemyControlPlaneRepository(
                control_engine,
                domain=config.domain,
                domain_git_sha=release_manifest.bundle.domain_git_sha,
                framework_version=config.framework_version,
                configs=config_tuple,
            )
            deployed = repository.get_dataset(selected_dataset.dataset_id)
            if deployed.config_hash != selected_dataset.config_hash:
                raise RuntimeError("approved Warehouse deployed/release config identity mismatch")

            marker_store = marker_store_factory(warehouse_engine, run_config)
            probe = FabricWarehouseTargetCommitProbe(marker_store=marker_store)
            claim = claim_target_operation(
                control_engine,
                intent=intent,
                dataset_run_id=dataset_run_id,
                attempt=1,
            )
            atomic_result: FabricWarehouseAtomicMutationResult | None = None
            ambiguity_origin: WarehouseAmbiguityOrigin
            execution_exception_type: str | None = None
            probe_resolution: UnknownOutcomeResolution

            if claim.action is TargetOperationAction.EXECUTE:
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
                    # A provider/driver exception around transaction completion is
                    # ambiguous. Persist UNKNOWN using only the exception type, then
                    # probe the target marker. Never infer NOT_COMMITTED from absence.
                    execution_exception_type = type(exc).__name__
                    mark_target_operation_unknown(
                        control_engine,
                        operation_key=intent.operation_key,
                        expected_version=claim.record.version,
                        dataset_run_id=dataset_run_id,
                        attempt=1,
                        error_message=(
                            "Warehouse execute_atomic raised "
                            f"{execution_exception_type}; target outcome requires marker probe"
                        ),
                    )
                    ambiguity_origin = WarehouseAmbiguityOrigin.PROVIDER_OR_DRIVER_EXCEPTION
                    reconciled = probe_and_reconcile_target_operation(
                        control_engine,
                        operation_key=intent.operation_key,
                        dataset_run_id=uuid4(),
                        attempt=2,
                        probe=probe,
                    )
                    probe_resolution = reconciled.evidence.resolution
                    if probe_resolution is not UnknownOutcomeResolution.COMMITTED:
                        return _safe_fail_result(
                            check_id=check_id,
                            intent=intent,
                            dataset_run_id=dataset_run_id,
                            evidence_references=references,
                            detail_code=(
                                "PROVIDER_EXCEPTION_MARKER_"
                                + probe_resolution.value
                            ),
                        )
                    atomic_result = _atomic_from_committed_marker(
                        marker_store,
                        intent,
                        executed=True,
                    )
                else:
                    # Simulate the framework losing the acknowledgement after the target
                    # transaction returned. This proves the UNKNOWN -> marker probe ->
                    # SUCCEEDED recovery path without pretending a network fault occurred.
                    mark_target_operation_unknown(
                        control_engine,
                        operation_key=intent.operation_key,
                        expected_version=claim.record.version,
                        dataset_run_id=dataset_run_id,
                        attempt=1,
                        error_message=(
                            "simulated framework acknowledgement loss after Warehouse "
                            "transaction returned"
                        ),
                        outcome_reference=atomic_result.marker_reference,
                    )
                    ambiguity_origin = WarehouseAmbiguityOrigin.SIMULATED_FRAMEWORK_ACK_LOSS
                    reconciled = probe_and_reconcile_target_operation(
                        control_engine,
                        operation_key=intent.operation_key,
                        dataset_run_id=uuid4(),
                        attempt=2,
                        probe=probe,
                    )
                    probe_resolution = reconciled.evidence.resolution
            elif claim.action is TargetOperationAction.RECONCILE_REQUIRED:
                ambiguity_origin = WarehouseAmbiguityOrigin.PREEXISTING_RECONCILE_REQUIRED
                reconciled = probe_and_reconcile_target_operation(
                    control_engine,
                    operation_key=intent.operation_key,
                    dataset_run_id=uuid4(),
                    attempt=max(2, claim.record.attempt + 1),
                    probe=probe,
                )
                probe_resolution = reconciled.evidence.resolution
                if probe_resolution is UnknownOutcomeResolution.COMMITTED:
                    atomic_result = _atomic_from_committed_marker(
                        marker_store,
                        intent,
                        executed=False,
                    )
            else:
                ambiguity_origin = WarehouseAmbiguityOrigin.PREEXISTING_SUCCEEDED
                direct_evidence = probe.probe(TargetCommitProbeRequest.from_record(claim.record))
                probe_resolution = direct_evidence.resolution
                if probe_resolution is UnknownOutcomeResolution.COMMITTED:
                    atomic_result = _atomic_from_committed_marker(
                        marker_store,
                        intent,
                        executed=False,
                    )

            current = read_target_operation(control_engine, intent.operation_key)
            if (
                atomic_result is None
                or probe_resolution is not UnknownOutcomeResolution.COMMITTED
                or current is None
                or current.status is not TargetOperationStatus.SUCCEEDED
            ):
                return _safe_fail_result(
                    check_id=check_id,
                    intent=intent,
                    dataset_run_id=dataset_run_id,
                    evidence_references=references,
                    detail_code=f"RECOVERY_{probe_resolution.value}",
                )

            reentry = claim_target_operation(
                control_engine,
                intent=intent,
                dataset_run_id=uuid4(),
                attempt=current.attempt + 1,
            )
            if reentry.action is not TargetOperationAction.SKIP_SUCCEEDED:
                return _safe_fail_result(
                    check_id=check_id,
                    intent=intent,
                    dataset_run_id=dataset_run_id,
                    evidence_references=references,
                    detail_code="REENTRY_NOT_SKIP_SUCCEEDED",
                )

            base = build_fabric_warehouse_commit_check_result(
                check_id=check_id,
                result=atomic_result,
                evidence_references=references,
            )
            result = IntegrationEvidenceCheckResult.model_validate(
                {
                    **base.model_dump(mode="python"),
                    "detail": (
                        "target mutation+marker commit proof reconciled through durable "
                        f"journal; ambiguity_origin={ambiguity_origin.value}; "
                        "probe=COMMITTED; final=SUCCEEDED; reentry=SKIP_SUCCEEDED"
                    ),
                }
            )
            report_holder.append(
                ApprovedWarehouseEvidenceReport(
                    check_id=check_id,
                    run_config_hash=run_config.run_config_hash,
                    operation_key=intent.operation_key,
                    dataset_run_id=atomic_result.marker.owner_dataset_run_id,
                    target_reference=intent.target_reference,
                    marker_reference=atomic_result.marker_reference,
                    native_operation_id=atomic_result.marker.native_operation_id,
                    marker_executed=atomic_result.executed,
                    initial_action=claim.action.value,
                    ambiguity_origin=ambiguity_origin,
                    execution_exception_type=execution_exception_type,
                    probe_resolution=probe_resolution,
                    final_status=current.status,
                    reentry_action=reentry.action.value,
                    evidence_references=result.evidence_references,
                )
            )
            return result
        finally:
            warehouse_engine.dispose()
            control_engine.dispose()

    manifest = run_integration_evidence(spec, runners={check_id: runner})
    report = report_holder[0] if report_holder else None
    return ApprovedWarehouseExecution(plan=plan, manifest=manifest, report=report)


__all__ = [
    "ApprovedWarehouseEvidenceReport",
    "ApprovedWarehouseExecution",
    "ApprovedWarehouseRunConfig",
    "WarehouseAmbiguityOrigin",
    "execute_approved_warehouse",
    "load_approved_warehouse_run_config",
]
