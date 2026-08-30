"""Fabric Warehouse session-termination proof for absent target markers.

This provider-specific contract is intentionally narrow. An absent target marker may
resolve to NOT_COMMITTED only when the framework retained the exact Warehouse session
identity before target execution, an independent Admin-capable connection observes that
same session with an open transaction, terminates that exact session, verifies the exact
connection is no longer observable, and the target commit probe subsequently re-reads
and still finds no marker.

Session disappearance by itself is not proof: the session might already have committed.
Query Insights is not used for this proof because its completed-query/session history is
eventually visible rather than an immediate no-late-commit guarantee.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import Field
from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

from ..config import FrozenModel
from .fabric_warehouse import FabricWarehouseAbsenceEvidence
from .target_probe import TargetCommitProbeRequest


class FabricWarehouseSessionBinding(FrozenModel):
    """Exact connection/session identity captured on the target execution connection."""

    session_id: int = Field(ge=1)
    connection_id: UUID

    @property
    def evidence_reference(self) -> str:
        return (
            "fabric-warehouse-session:"
            f"{self.connection_id}:{self.session_id}"
        )


class FabricWarehouseSessionState(FrozenModel):
    """Admin-side observation of the exact bound Warehouse connection/session."""

    session_id: int = Field(ge=1)
    connection_id: UUID
    open_transaction_count: int = Field(ge=0)


@runtime_checkable
class FabricWarehouseSessionAuthority(Protocol):
    """Provider authority that can inspect and terminate one exact Warehouse session."""

    def observe(
        self,
        binding: FabricWarehouseSessionBinding,
    ) -> FabricWarehouseSessionState | None:
        """Return the exact live session state or ``None`` when it is not observable."""

    def terminate(self, binding: FabricWarehouseSessionBinding) -> None:
        """Terminate the exact session and roll back its active transaction."""


class SqlAlchemyFabricWarehouseSessionAuthority:
    """Fabric Warehouse DMV/KILL implementation backed by a separate Admin connection.

    Microsoft Fabric documents ``sys.dm_exec_connections``, ``sys.dm_exec_sessions``
    and Admin-only ``KILL <session_id>`` for Warehouse. ``KILL`` is executed through an
    AUTOCOMMIT connection because it is a session-control command rather than part of
    the target transaction being certified.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def observe(
        self,
        binding: FabricWarehouseSessionBinding,
    ) -> FabricWarehouseSessionState | None:
        statement = text(
            """
            SELECT
                c.connection_id,
                s.session_id,
                s.open_transaction_count
            FROM sys.dm_exec_connections AS c
            INNER JOIN sys.dm_exec_sessions AS s
                ON c.session_id = s.session_id
            WHERE c.connection_id = :connection_id
              AND s.session_id = :session_id
            """
        )
        with self._engine.connect() as connection:
            row = connection.execute(
                statement,
                {
                    "connection_id": str(binding.connection_id),
                    "session_id": binding.session_id,
                },
            ).mappings().one_or_none()
        if row is None:
            return None
        return FabricWarehouseSessionState(
            session_id=int(row["session_id"]),
            connection_id=UUID(str(row["connection_id"])),
            open_transaction_count=int(row["open_transaction_count"]),
        )

    def terminate(self, binding: FabricWarehouseSessionBinding) -> None:
        # session_id is a validated positive integer, so embedding it cannot introduce
        # arbitrary SQL. T-SQL KILL does not accept a bind parameter for the grammar.
        statement = f"KILL {binding.session_id}"
        with self._engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.exec_driver_sql(statement)


def capture_fabric_warehouse_session_binding(
    connection: Connection,
) -> FabricWarehouseSessionBinding:
    """Capture exact Fabric Warehouse connection/session identity on target connection.

    The query is deliberately executed on the same SQLAlchemy ``Connection`` that owns
    the target transaction. ``@@SPID`` binds the DMV lookup to that session, while the
    provider connection UUID prevents a later reused numeric session ID from being
    mistaken for the original ambiguous transaction.
    """

    row = connection.execute(
        text(
            """
            SELECT TOP (1)
                c.connection_id,
                c.session_id
            FROM sys.dm_exec_connections AS c
            WHERE c.session_id = @@SPID
            """
        )
    ).mappings().one_or_none()
    if row is None:
        raise RuntimeError("Fabric Warehouse session identity could not be captured")
    return FabricWarehouseSessionBinding(
        session_id=int(row["session_id"]),
        connection_id=UUID(str(row["connection_id"])),
    )


class FabricWarehouseSessionTerminationAbsenceCertifier:
    """Certify retry safety only from an observed open transaction that is terminated.

    This class does **not** inspect marker rows. ``FabricWarehouseTargetCommitProbe``
    remains responsible for the primary marker check and, critically, a second marker
    read after this certifier returns. Therefore ``safe_to_retry=True`` means only that
    the exact previously captured session had an open transaction and that exact session
    was terminated and disappeared; final NOT_COMMITTED still requires post-termination
    marker absence.
    """

    def __init__(
        self,
        *,
        binding: FabricWarehouseSessionBinding,
        authority: FabricWarehouseSessionAuthority,
    ) -> None:
        self._binding = binding
        self._authority = authority

    def certify_absence(
        self,
        request: TargetCommitProbeRequest,
    ) -> FabricWarehouseAbsenceEvidence:
        del request  # semantic identity is enforced by the surrounding marker probe

        try:
            before = self._authority.observe(self._binding)
        except Exception as exc:
            return FabricWarehouseAbsenceEvidence(
                safe_to_retry=False,
                evidence_reference=self._binding.evidence_reference,
                detail=f"Warehouse session observation failed: {type(exc).__name__}",
            )

        if before is None:
            return FabricWarehouseAbsenceEvidence(
                safe_to_retry=False,
                evidence_reference=self._binding.evidence_reference,
                detail=(
                    "exact Warehouse session is no longer observable; disappearance alone "
                    "cannot distinguish commit from rollback"
                ),
            )
        if (
            before.session_id != self._binding.session_id
            or before.connection_id != self._binding.connection_id
        ):
            return FabricWarehouseAbsenceEvidence(
                safe_to_retry=False,
                evidence_reference=self._binding.evidence_reference,
                detail="observed Warehouse session identity does not match retained binding",
            )
        if before.open_transaction_count < 1:
            return FabricWarehouseAbsenceEvidence(
                safe_to_retry=False,
                evidence_reference=self._binding.evidence_reference,
                detail=(
                    "exact Warehouse session has no observable open transaction; "
                    "cannot prove rollback of the ambiguous target transaction"
                ),
            )

        try:
            self._authority.terminate(self._binding)
        except Exception as exc:
            return FabricWarehouseAbsenceEvidence(
                safe_to_retry=False,
                evidence_reference=self._binding.evidence_reference,
                detail=f"Warehouse session termination failed: {type(exc).__name__}",
            )

        try:
            after = self._authority.observe(self._binding)
        except Exception as exc:
            return FabricWarehouseAbsenceEvidence(
                safe_to_retry=False,
                evidence_reference=self._binding.evidence_reference,
                detail=f"post-termination session observation failed: {type(exc).__name__}",
            )

        if after is not None:
            return FabricWarehouseAbsenceEvidence(
                safe_to_retry=False,
                evidence_reference=self._binding.evidence_reference,
                detail=(
                    "exact Warehouse session remains observable after termination; "
                    "rollback completion is not proven"
                ),
            )

        return FabricWarehouseAbsenceEvidence(
            safe_to_retry=True,
            evidence_reference=self._binding.evidence_reference,
            detail=(
                "exact Warehouse session had an open transaction, was terminated, and is "
                "no longer observable; final retry safety still requires a second absent "
                "target-marker read"
            ),
        )


__all__ = [
    "FabricWarehouseSessionAuthority",
    "FabricWarehouseSessionBinding",
    "FabricWarehouseSessionState",
    "FabricWarehouseSessionTerminationAbsenceCertifier",
    "SqlAlchemyFabricWarehouseSessionAuthority",
    "capture_fabric_warehouse_session_binding",
]
