"""Fabric Warehouse target-native commit proof.

The framework control-plane journal decides whether a semantic target operation is
allowed to execute. This module provides an independent target-side proof: the target
mutation and a framework operation marker are written through the *same* SQLAlchemy
transaction. A later read-only probe resolves a committed marker to COMMITTED.

Marker absence is deliberately not interpreted as NOT_COMMITTED unless an injected
absence certifier provides independent provider/session evidence that retry is safe.
Warehouse Query Insights can be retained as secondary correlation, but its eventual
history visibility is not used as primary commit truth.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field, model_validator
from sqlalchemy import Column, DateTime, Engine, Integer, MetaData, String, Table, inspect, select
from sqlalchemy.engine import Connection

from ..config import FrozenModel
from ..contracts.recovery import UnknownOutcomeResolution
from ..target_operations import TargetOperationIntent
from .target_probe import TargetCommitProbeEvidence, TargetCommitProbeRequest


FABRIC_WAREHOUSE_MARKER_VERSION = 1
FABRIC_WAREHOUSE_DEFAULT_MARKER_TABLE = "fabric_framework_target_operation_marker"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _warehouse_datetime(value: datetime) -> datetime:
    """Persist UTC wall-clock time using Warehouse-supported datetime2 semantics."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Warehouse marker timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_fabric_warehouse_operation_marker_table(
    metadata: MetaData,
    *,
    table_name: str = FABRIC_WAREHOUSE_DEFAULT_MARKER_TABLE,
    schema: str | None = "dbo",
) -> Table:
    """Define the canonical target-side marker table without creating it.

    Deployment of this table is an explicit environment change. Runtime construction
    verifies the table exists and never performs DDL implicitly.

    The table intentionally does not rely on an enforced PK/UNIQUE constraint for
    concurrency. Fabric Warehouse constraints can be NOT ENFORCED; the framework
    control-plane target-operation CAS remains the execution serialization authority.
    """

    if not table_name.strip():
        raise ValueError("table_name cannot be empty")
    if schema is not None and not schema.strip():
        raise ValueError("schema cannot be empty when supplied")
    return Table(
        table_name,
        metadata,
        Column("marker_version", Integer, nullable=False),
        Column("operation_key", String(64), nullable=False),
        Column("dataset_id", String(255), nullable=False),
        Column("operation_kind", String(64), nullable=False),
        Column("target_reference", String(1024), nullable=False),
        Column("effective_config_hash", String(64), nullable=False),
        Column("input_fingerprint", String(64), nullable=False),
        Column("semantic_version", Integer, nullable=False),
        Column("owner_dataset_run_id", String(36), nullable=False),
        Column("attempt", Integer, nullable=False),
        Column("native_operation_id", String(1024), nullable=True),
        Column("query_label", String(512), nullable=True),
        Column("detail", String(4000), nullable=True),
        Column("recorded_at", DateTime(timezone=False), nullable=False),
        schema=schema,
    )


class FabricWarehouseOperationMarker(FrozenModel):
    marker_version: int = Field(default=FABRIC_WAREHOUSE_MARKER_VERSION, ge=1)
    operation_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_id: str = Field(min_length=1, max_length=255)
    operation_kind: str = Field(min_length=1, max_length=64)
    target_reference: str = Field(min_length=1, max_length=1024)
    effective_config_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    semantic_version: int = Field(ge=1)
    owner_dataset_run_id: UUID
    attempt: int = Field(ge=1)
    native_operation_id: str | None = Field(default=None, max_length=1024)
    query_label: str | None = Field(default=None, max_length=512)
    detail: str | None = Field(default=None, max_length=4000)
    recorded_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_marker(self) -> "FabricWarehouseOperationMarker":
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        intent = TargetOperationIntent(
            dataset_id=self.dataset_id,
            operation_kind=self.operation_kind,
            target_reference=self.target_reference,
            effective_config_hash=self.effective_config_hash,
            input_fingerprint=self.input_fingerprint,
            semantic_version=self.semantic_version,
        )
        if intent.operation_key != self.operation_key:
            raise ValueError("Warehouse marker operation_key does not match semantic identity")
        return self


class FabricWarehouseMutationEvidence(FrozenModel):
    """Optional target-native correlation returned by the mutation implementation."""

    native_operation_id: str | None = Field(default=None, max_length=1024)
    query_label: str | None = Field(default=None, max_length=512)
    detail: str | None = Field(default=None, max_length=4000)


FabricWarehouseMutation = Callable[
    [Connection, TargetOperationIntent], FabricWarehouseMutationEvidence | None
]


class FabricWarehouseAtomicMutationResult(FrozenModel):
    marker: FabricWarehouseOperationMarker
    marker_reference: str
    executed: bool


class FabricWarehouseMarkerConflict(RuntimeError):
    """The target contains marker rows that do not agree on semantic identity."""


class FabricWarehouseMarkerStore:
    """Read/write target-native operation markers in one Fabric Warehouse target."""

    _REQUIRED_COLUMNS = frozenset(
        {
            "marker_version",
            "operation_key",
            "dataset_id",
            "operation_kind",
            "target_reference",
            "effective_config_hash",
            "input_fingerprint",
            "semantic_version",
            "owner_dataset_run_id",
            "attempt",
            "native_operation_id",
            "query_label",
            "detail",
            "recorded_at",
        }
    )

    def __init__(self, engine: Engine, marker_table: Table) -> None:
        missing = self._REQUIRED_COLUMNS - set(marker_table.c.keys())
        if missing:
            raise ValueError(
                "Warehouse marker table contract is missing columns: "
                + ", ".join(sorted(missing))
            )
        if not inspect(engine).has_table(marker_table.name, schema=marker_table.schema):
            qualified = (
                f"{marker_table.schema}.{marker_table.name}"
                if marker_table.schema
                else marker_table.name
            )
            raise RuntimeError(
                f"Fabric Warehouse marker table is not deployed: {qualified}; "
                "runtime never creates target proof tables implicitly"
            )
        self.engine = engine
        self.table = marker_table

    @property
    def qualified_table_name(self) -> str:
        return (
            f"{self.table.schema}.{self.table.name}"
            if self.table.schema
            else self.table.name
        )

    def marker_reference(self, operation_key: str) -> str:
        return f"fabric-warehouse-marker:{self.qualified_table_name}:{operation_key}"

    @staticmethod
    def _from_row(row: dict[str, object]) -> FabricWarehouseOperationMarker:
        return FabricWarehouseOperationMarker(
            marker_version=int(row["marker_version"]),
            operation_key=str(row["operation_key"]),
            dataset_id=str(row["dataset_id"]),
            operation_kind=str(row["operation_kind"]),
            target_reference=str(row["target_reference"]),
            effective_config_hash=str(row["effective_config_hash"]),
            input_fingerprint=str(row["input_fingerprint"]),
            semantic_version=int(row["semantic_version"]),
            owner_dataset_run_id=UUID(str(row["owner_dataset_run_id"])),
            attempt=int(row["attempt"]),
            native_operation_id=(
                str(row["native_operation_id"])
                if row["native_operation_id"] is not None
                else None
            ),
            query_label=(
                str(row["query_label"]) if row["query_label"] is not None else None
            ),
            detail=str(row["detail"]) if row["detail"] is not None else None,
            recorded_at=_aware_utc(row["recorded_at"]),
        )

    def _read_with_connection(
        self,
        connection: Connection,
        operation_key: str,
    ) -> tuple[FabricWarehouseOperationMarker, ...]:
        rows = connection.execute(
            select(self.table).where(self.table.c.operation_key == operation_key)
        ).mappings().all()
        return tuple(self._from_row(dict(row)) for row in rows)

    def read_markers(
        self,
        operation_key: str,
    ) -> tuple[FabricWarehouseOperationMarker, ...]:
        with self.engine.connect() as connection:
            return self._read_with_connection(connection, operation_key)

    @staticmethod
    def _marker_matches_intent(
        marker: FabricWarehouseOperationMarker,
        intent: TargetOperationIntent,
    ) -> bool:
        return (
            marker.operation_key == intent.operation_key
            and marker.dataset_id == intent.dataset_id
            and marker.operation_kind == intent.operation_kind
            and marker.target_reference == intent.target_reference
            and marker.effective_config_hash.lower() == intent.effective_config_hash.lower()
            and marker.input_fingerprint.lower() == intent.input_fingerprint.lower()
            and marker.semantic_version == intent.semantic_version
        )

    @classmethod
    def _require_consistent_markers(
        cls,
        markers: tuple[FabricWarehouseOperationMarker, ...],
        intent: TargetOperationIntent,
    ) -> None:
        if any(not cls._marker_matches_intent(marker, intent) for marker in markers):
            raise FabricWarehouseMarkerConflict(
                "Fabric Warehouse operation marker semantic identity conflict"
            )

    def execute_atomic(
        self,
        *,
        intent: TargetOperationIntent,
        dataset_run_id: UUID,
        attempt: int,
        mutation: FabricWarehouseMutation,
    ) -> FabricWarehouseAtomicMutationResult:
        """Execute target mutation + marker in one target database transaction.

        The method assumes the caller already owns the framework target-operation
        EXECUTE claim. Existing consistent marker rows are treated as committed proof
        and the mutation is not re-executed. This is a secondary safety belt; the
        framework journal remains the primary execution/reconciliation gate.
        """

        if attempt < 1:
            raise ValueError("attempt must be >= 1")

        with self.engine.begin() as connection:
            existing = self._read_with_connection(connection, intent.operation_key)
            if existing:
                self._require_consistent_markers(existing, intent)
                return FabricWarehouseAtomicMutationResult(
                    marker=existing[0],
                    marker_reference=self.marker_reference(intent.operation_key),
                    executed=False,
                )

            mutation_evidence = mutation(connection, intent) or FabricWarehouseMutationEvidence()
            marker = FabricWarehouseOperationMarker(
                operation_key=intent.operation_key,
                dataset_id=intent.dataset_id,
                operation_kind=intent.operation_kind,
                target_reference=intent.target_reference,
                effective_config_hash=intent.effective_config_hash,
                input_fingerprint=intent.input_fingerprint,
                semantic_version=intent.semantic_version,
                owner_dataset_run_id=dataset_run_id,
                attempt=attempt,
                native_operation_id=mutation_evidence.native_operation_id,
                query_label=mutation_evidence.query_label,
                detail=mutation_evidence.detail,
            )
            connection.execute(
                self.table.insert().values(
                    marker_version=marker.marker_version,
                    operation_key=marker.operation_key,
                    dataset_id=marker.dataset_id,
                    operation_kind=marker.operation_kind,
                    target_reference=marker.target_reference,
                    effective_config_hash=marker.effective_config_hash.lower(),
                    input_fingerprint=marker.input_fingerprint.lower(),
                    semantic_version=marker.semantic_version,
                    owner_dataset_run_id=str(marker.owner_dataset_run_id),
                    attempt=marker.attempt,
                    native_operation_id=marker.native_operation_id,
                    query_label=marker.query_label,
                    detail=marker.detail,
                    recorded_at=_warehouse_datetime(marker.recorded_at),
                )
            )

        return FabricWarehouseAtomicMutationResult(
            marker=marker,
            marker_reference=self.marker_reference(intent.operation_key),
            executed=True,
        )


class FabricWarehouseAbsenceEvidence(FrozenModel):
    """Independent evidence needed before marker absence may mean NOT_COMMITTED."""

    safe_to_retry: bool
    evidence_reference: str | None = Field(default=None, max_length=2048)
    native_operation_id: str | None = Field(default=None, max_length=1024)
    detail: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_resolution_evidence(self) -> "FabricWarehouseAbsenceEvidence":
        if (
            self.safe_to_retry
            and self.evidence_reference is None
            and self.native_operation_id is None
        ):
            raise ValueError(
                "safe_to_retry absence evidence requires an evidence reference or native operation id"
            )
        return self


@runtime_checkable
class FabricWarehouseAbsenceCertifier(Protocol):
    def certify_absence(
        self,
        request: TargetCommitProbeRequest,
    ) -> FabricWarehouseAbsenceEvidence:
        """Provide independent proof that an absent marker cannot still commit later."""


class FabricWarehouseSecondaryCorrelation(FrozenModel):
    """Optional Query Insights/statement correlation; never primary commit truth."""

    native_operation_id: str | None = Field(default=None, max_length=1024)
    evidence_reference: str | None = Field(default=None, max_length=2048)
    detail: str | None = Field(default=None, max_length=4000)


@runtime_checkable
class FabricWarehouseSecondaryCorrelationReader(Protocol):
    def lookup(
        self,
        request: TargetCommitProbeRequest,
    ) -> tuple[FabricWarehouseSecondaryCorrelation, ...]:
        """Read delayed/diagnostic provider correlation such as Query Insights."""


def _request_matches_marker(
    request: TargetCommitProbeRequest,
    marker: FabricWarehouseOperationMarker,
) -> bool:
    return (
        marker.operation_key == request.operation_key
        and marker.dataset_id == request.dataset_id
        and marker.operation_kind == request.operation_kind
        and marker.target_reference == request.target_reference
        and marker.effective_config_hash.lower() == request.effective_config_hash.lower()
        and marker.input_fingerprint.lower() == request.input_fingerprint.lower()
    )


class FabricWarehouseTargetCommitProbe:
    """Resolve ambiguous Warehouse target outcomes from committed marker evidence."""

    def __init__(
        self,
        *,
        marker_store: FabricWarehouseMarkerStore,
        absence_certifier: FabricWarehouseAbsenceCertifier | None = None,
        secondary_correlation_reader: FabricWarehouseSecondaryCorrelationReader | None = None,
    ) -> None:
        self._marker_store = marker_store
        self._absence_certifier = absence_certifier
        self._secondary_reader = secondary_correlation_reader

    def _secondary(
        self,
        request: TargetCommitProbeRequest,
    ) -> tuple[tuple[FabricWarehouseSecondaryCorrelation, ...], str | None]:
        if self._secondary_reader is None:
            return (), None
        try:
            return self._secondary_reader.lookup(request), None
        except Exception as exc:
            # Provider/driver diagnostic text may embed connection/user-info material.
            # Retain only the exception type in framework evidence.
            return (), f"secondary correlation lookup failed: {type(exc).__name__}"

    @staticmethod
    def _secondary_detail(
        correlations: tuple[FabricWarehouseSecondaryCorrelation, ...],
        lookup_error: str | None,
    ) -> str | None:
        parts: list[str] = []
        if correlations:
            parts.append(f"secondary_correlations={len(correlations)}")
        if lookup_error:
            parts.append(lookup_error)
        return "; ".join(parts) or None

    def probe(self, request: TargetCommitProbeRequest) -> TargetCommitProbeEvidence:
        markers = self._marker_store.read_markers(request.operation_key)
        correlations, secondary_error = self._secondary(request)
        secondary_detail = self._secondary_detail(correlations, secondary_error)
        secondary_native_id = next(
            (
                item.native_operation_id
                for item in correlations
                if item.native_operation_id is not None
            ),
            None,
        )

        if markers:
            if any(not _request_matches_marker(request, marker) for marker in markers):
                return TargetCommitProbeEvidence(
                    provider="fabric_warehouse",
                    resolution=UnknownOutcomeResolution.UNRESOLVED,
                    native_operation_id=secondary_native_id,
                    detail=(
                        "committed marker rows exist but semantic identity conflicts; "
                        + (secondary_detail or "no secondary correlation")
                    ),
                )
            marker_native_id = next(
                (
                    marker.native_operation_id
                    for marker in markers
                    if marker.native_operation_id is not None
                ),
                None,
            )
            detail_parts = [f"committed marker rows={len(markers)}"]
            if secondary_detail:
                detail_parts.append(secondary_detail)
            return TargetCommitProbeEvidence(
                provider="fabric_warehouse",
                resolution=UnknownOutcomeResolution.COMMITTED,
                evidence_reference=self._marker_store.marker_reference(request.operation_key),
                native_operation_id=marker_native_id or secondary_native_id,
                detail="; ".join(detail_parts),
            )

        if self._absence_certifier is None:
            detail = "target operation marker absent; absence alone is not proof of non-commit"
            if secondary_detail:
                detail += f"; {secondary_detail}"
            return TargetCommitProbeEvidence(
                provider="fabric_warehouse",
                resolution=UnknownOutcomeResolution.UNRESOLVED,
                native_operation_id=secondary_native_id,
                detail=detail,
            )

        absence = self._absence_certifier.certify_absence(request)
        detail_parts = [
            absence.detail
            or (
                "independent absence evidence certifies retry safety"
                if absence.safe_to_retry
                else "independent absence evidence does not certify retry safety"
            )
        ]
        if secondary_detail:
            detail_parts.append(secondary_detail)
        if not absence.safe_to_retry:
            return TargetCommitProbeEvidence(
                provider="fabric_warehouse",
                resolution=UnknownOutcomeResolution.UNRESOLVED,
                evidence_reference=absence.evidence_reference,
                native_operation_id=absence.native_operation_id or secondary_native_id,
                detail="; ".join(detail_parts),
            )
        return TargetCommitProbeEvidence(
            provider="fabric_warehouse",
            resolution=UnknownOutcomeResolution.NOT_COMMITTED,
            evidence_reference=absence.evidence_reference,
            native_operation_id=absence.native_operation_id or secondary_native_id,
            detail="; ".join(detail_parts),
        )
