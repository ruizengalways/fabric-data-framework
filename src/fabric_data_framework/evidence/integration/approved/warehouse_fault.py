"""Exact-release approved real-fault drill for ambiguous Fabric Warehouse COMMIT.

This runner is separate from the normal approved Warehouse commit runner. PASS requires
an actually observed provider/driver exception, verified provider-specific fault
injection, committed target-side marker evidence, journal reconciliation to SUCCEEDED,
and later SKIP_SUCCEEDED re-entry. A normal transaction return can never PASS this drill.

Optional session-termination recovery is a separate operational outcome. It may prove an
ambiguous mutation NOT_COMMITTED and make a later retry safe, but it never upgrades the
COMMITTED fault-drill evidence check to PASS.
"""

from __future__ import annotations

from fabric_data_framework.contracts.hashing import canonical_hash

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.engine import Connection

from fabric_data_framework.metadata.config import (
    DatasetConfig,)
from fabric_data_framework.contracts.base import FrozenModel
from ....contracts.recovery import UnknownOutcomeResolution
from ....deployment.contracts import ReleaseManifest
from ....extensions import ExtensionRegistry
from ..evidence import (
    IntegrationEvidenceManifest,
    IntegrationEvidenceSpec,
    IntegrationEvidenceStatus,
)
from ..runner import (
    ApprovedIntegrationRunPlan,
    ApprovedIntegrationRunnerConfig,
)
from ....recovery.fabric_warehouse import (
    FABRIC_WAREHOUSE_DEFAULT_MARKER_TABLE,
    FabricWarehouseMarkerStore,
    FabricWarehouseMutationEvidence,
    build_fabric_warehouse_operation_marker_table,
)
from ....recovery.fabric_warehouse_session_absence import (
    FabricWarehouseSessionAuthority,
    FabricWarehouseSessionBinding,
    SqlAlchemyFabricWarehouseSessionAuthority,
    capture_fabric_warehouse_session_binding,
)
from ....recovery.warehouse_fault_injection import (
    FabricWarehouseCommitFaultInjector,
    FabricWarehouseCommitFaultRequest,
    WarehouseCommitFaultPhase,
)
from fabric_data_framework.contracts.audit_safety import assert_safe_retained_text
from fabric_data_framework.contracts.target_operation import (
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
    enable_session_termination_recovery: bool = False
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
        # Recovery mechanism is deliberately excluded. The semantic target mutation and
        # fault case remain the same operation regardless of whether an independently
        # authorized recovery authority is available after ambiguity.
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
    session_termination_recovery_enabled: bool = False
    session_termination_authorized: bool = False
    session_binding_captured: bool = False
    session_id: int | None = Field(default=None, ge=1)
    connection_id: UUID | None = None
    session_binding_capture_exception_type: str | None = Field(default=None, max_length=256)
    session_termination_recovery_attempted: bool = False
    session_recovery_exception_type: str | None = Field(default=None, max_length=256)
    absence_safe_to_retry: bool | None = None
    retry_eligible: bool = False
    evidence_status: IntegrationEvidenceStatus
    failure_reason: str | None = Field(default=None, max_length=512)
    evidence_references: tuple[str, ...]

    @model_validator(mode="after")
    def validate_report(self) -> "ApprovedWarehouseFaultDrillReport":
        if self.session_binding_captured != (
            self.session_id is not None and self.connection_id is not None
        ):
            raise ValueError(
                "session binding capture flag must match retained session_id + connection_id"
            )
        if self.retry_eligible and self.final_status is not TargetOperationStatus.NOT_COMMITTED:
            raise ValueError("retry_eligible requires durable NOT_COMMITTED target state")
        if self.absence_safe_to_retry is True and not self.retry_eligible:
            raise ValueError("safe-to-retry absence evidence requires retry_eligible state")
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
                and not self.retry_eligible
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
SessionBindingCapture = Callable[[Connection], FabricWarehouseSessionBinding]
SessionAuthorityFactory = Callable[[Engine], FabricWarehouseSessionAuthority]


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


def _default_session_authority_factory(engine: Engine) -> FabricWarehouseSessionAuthority:
    return SqlAlchemyFabricWarehouseSessionAuthority(engine)


def load_approved_warehouse_fault_drill_config(
    path: str | Path,
) -> ApprovedWarehouseFaultDrillConfig:
    return ApprovedWarehouseFaultDrillConfig.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def execute_approved_warehouse_fault_drill(  # noqa: PLR0913
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
    allow_warehouse_session_termination: bool = False,
    extension_registry: ExtensionRegistry | None = None,
    control_engine_factory: EngineFactory = create_engine,
    warehouse_engine_factory: EngineFactory = create_engine,
    warehouse_admin_engine_factory: EngineFactory = create_engine,
    marker_store_factory: MarkerStoreFactory = _default_marker_store_factory,
    session_binding_capture: SessionBindingCapture = capture_fabric_warehouse_session_binding,
    session_authority_factory: SessionAuthorityFactory = _default_session_authority_factory,
) -> ApprovedWarehouseFaultDrillExecution:
    """Execute one approved real-fault drill through fail-closed typed stages."""

    from .warehouse_fault_stages import (
        WarehouseFaultDrillRequest,
        WarehouseFaultDrillServices,
        execute_approved_warehouse_fault_drill_staged,
    )

    request = WarehouseFaultDrillRequest(
        config=config,
        spec=spec,
        prerequisite_manifest=prerequisite_manifest,
        release_manifest=release_manifest,
        configs=tuple(configs),
        run_config=run_config,
        environ=environ,
        evidence_references=tuple(evidence_references),
        allow_warehouse_fault_injection=allow_warehouse_fault_injection,
        allow_warehouse_session_termination=allow_warehouse_session_termination,
    )
    services = WarehouseFaultDrillServices(
        extension_registry=extension_registry,
        control_engine_factory=control_engine_factory,
        warehouse_engine_factory=warehouse_engine_factory,
        warehouse_admin_engine_factory=warehouse_admin_engine_factory,
        marker_store_factory=marker_store_factory,
        session_binding_capture=session_binding_capture,
        session_authority_factory=session_authority_factory,
    )
    return execute_approved_warehouse_fault_drill_staged(request, services)


__all__ = [
    "ApprovedWarehouseFaultDrillConfig",
    "ApprovedWarehouseFaultDrillExecution",
    "ApprovedWarehouseFaultDrillReport",
    "execute_approved_warehouse_fault_drill",
    "load_approved_warehouse_fault_drill_config",
]
