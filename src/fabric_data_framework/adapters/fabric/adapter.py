"""Fail-closed Microsoft Fabric capture adapter boundary.

The adapter owns provider evidence validation and CaptureReceipt creation.  The
injected transport owns API/SDK/CLI mechanics.  A transport result is never treated
as a successful capture merely because the remote invocation returned normally.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...config import ExecutionEngine, ProgressOwner
from ...contracts.capture_receipt import CaptureReceipt
from ...contracts.execution_plan import ExecutionKind, ExecutionRole
from .contracts import (
    FabricCaptureRequest,
    FabricCaptureTransport,
    FabricNativeRunEvidence,
    FabricNativeRunStatus,
)


class FabricAdapterExecutionError(RuntimeError):
    """Raised when Fabric execution/evidence cannot prove a successful capture."""

    def __init__(
        self,
        message: str,
        *,
        evidence: FabricNativeRunEvidence | None = None,
    ) -> None:
        super().__init__(message)
        self.evidence = evidence


_FORBIDDEN_CAPTURE_ROLES = frozenset(
    {
        ExecutionRole.APPLY,
        ExecutionRole.PUBLISH,
        ExecutionRole.RECONCILE,
        ExecutionRole.COMMIT_STATE,
        ExecutionRole.FINALIZE,
    }
)


class FabricCaptureAdapter:
    """Translate one compiled capture unit into verified framework evidence."""

    def __init__(
        self,
        *,
        execution_engine: ExecutionEngine,
        execution_kind: ExecutionKind,
        transport: FabricCaptureTransport,
    ) -> None:
        if execution_engine in {
            ExecutionEngine.AUTO,
            ExecutionEngine.EXTERNAL_CDC,
            ExecutionEngine.SQL,
            ExecutionEngine.CUSTOM,
        }:
            raise ValueError(
                f"{execution_engine.value} is not a concrete Fabric capture adapter engine"
            )
        self.execution_engine = execution_engine
        self.execution_kind = execution_kind
        self.transport = transport

    def _validate_request(self, request: FabricCaptureRequest) -> None:
        if request.execution_engine is not self.execution_engine:
            raise ValueError(
                f"request engine {request.execution_engine.value} does not match adapter "
                f"engine {self.execution_engine.value}"
            )
        if request.execution_unit.execution_kind is not self.execution_kind:
            raise ValueError(
                f"execution unit kind {request.execution_unit.execution_kind.value} does "
                f"not match adapter kind {self.execution_kind.value}"
            )
        roles = frozenset(request.execution_unit.roles)
        required = {ExecutionRole.EXTRACT, ExecutionRole.STAGE}
        if not required.issubset(roles):
            raise ValueError("Fabric capture adapter requires EXTRACT and STAGE roles")
        forbidden = roles.intersection(_FORBIDDEN_CAPTURE_ROLES)
        if forbidden:
            values = ", ".join(sorted(role.value for role in forbidden))
            raise ValueError(
                "Fabric capture adapter cannot execute downstream lifecycle roles: "
                f"{values}"
            )
        if request.progress_owner is ProgressOwner.EXTERNAL:
            raise ValueError("Fabric capture adapter cannot use EXTERNAL progress ownership")

    def _validate_success_evidence(
        self,
        request: FabricCaptureRequest,
        evidence: FabricNativeRunEvidence,
    ) -> None:
        if evidence.status is not FabricNativeRunStatus.SUCCEEDED:
            raise FabricAdapterExecutionError(
                f"Fabric capture {evidence.native_run_id} ended with status "
                f"{evidence.status.value}",
                evidence=evidence,
            )
        if evidence.execution_kind is not self.execution_kind:
            raise FabricAdapterExecutionError(
                f"Fabric run {evidence.native_run_id} reported execution kind "
                f"{evidence.execution_kind.value}; expected {self.execution_kind.value}",
                evidence=evidence,
            )
        if evidence.landing_reference != request.landing_reference:
            raise FabricAdapterExecutionError(
                f"Fabric run {evidence.native_run_id} landed at "
                f"{evidence.landing_reference!r}; expected {request.landing_reference!r}",
                evidence=evidence,
            )
        if (
            request.source_reference is not None
            and evidence.source_reference is not None
            and evidence.source_reference != request.source_reference
        ):
            raise FabricAdapterExecutionError(
                f"Fabric run {evidence.native_run_id} source reference does not match request",
                evidence=evidence,
            )
        if request.snapshot_id is not None and evidence.snapshot_id != request.snapshot_id:
            raise FabricAdapterExecutionError(
                f"Fabric run {evidence.native_run_id} snapshot identity does not match request",
                evidence=evidence,
            )

        # Framework-owned bounded movement must prove that the requested physical
        # source range is the range that actually ran.  Native-progress engines may
        # instead report their own checkpoint/boundary in the receipt.
        if request.progress_owner is ProgressOwner.FRAMEWORK:
            for field_name in ("source_lower_bound", "source_upper_bound"):
                requested = getattr(request, field_name)
                if requested is None:
                    continue
                observed = getattr(evidence, field_name)
                if observed != requested:
                    raise FabricAdapterExecutionError(
                        f"Fabric run {evidence.native_run_id} {field_name}={observed!r}; "
                        f"expected {requested!r}",
                        evidence=evidence,
                    )

    def execute(self, request: FabricCaptureRequest) -> CaptureReceipt:
        """Invoke the transport and return a receipt only for verified success."""

        self._validate_request(request)
        evidence = self.transport.invoke_capture(request)
        self._validate_success_evidence(request, evidence)

        return CaptureReceipt(
            dataset_run_id=request.dataset_run_id,
            dataset_id=request.dataset_id,
            capture_strategy=request.capture_strategy,
            execution_engine=request.execution_engine,
            progress_owner=request.progress_owner,
            native_run_id=evidence.native_run_id,
            source_reference=evidence.source_reference or request.source_reference,
            landing_reference=evidence.landing_reference,
            rows_read=evidence.rows_read,
            rows_written=evidence.rows_written,
            source_lower_bound=(
                evidence.source_lower_bound
                if evidence.source_lower_bound is not None
                else request.source_lower_bound
            ),
            source_upper_bound=(
                evidence.source_upper_bound
                if evidence.source_upper_bound is not None
                else request.source_upper_bound
            ),
            snapshot_id=evidence.snapshot_id,
            complete_snapshot=evidence.complete_snapshot,
            external_checkpoint_reference=evidence.external_checkpoint_reference,
            schema_version=evidence.schema_version,
            started_at=evidence.started_at,
            completed_at=evidence.completed_at,
        )


class CopyJobCaptureAdapter(FabricCaptureAdapter):
    def __init__(self, transport: FabricCaptureTransport) -> None:
        super().__init__(
            execution_engine=ExecutionEngine.FABRIC_COPY_JOB,
            execution_kind=ExecutionKind.FABRIC_COPY_JOB,
            transport=transport,
        )


class CopyActivityCaptureAdapter(FabricCaptureAdapter):
    def __init__(self, transport: FabricCaptureTransport) -> None:
        super().__init__(
            execution_engine=ExecutionEngine.FABRIC_COPY_ACTIVITY,
            execution_kind=ExecutionKind.FABRIC_COPY_ACTIVITY,
            transport=transport,
        )


class DataflowGen2CaptureAdapter(FabricCaptureAdapter):
    def __init__(self, transport: FabricCaptureTransport) -> None:
        super().__init__(
            execution_engine=ExecutionEngine.DATAFLOW_GEN2,
            execution_kind=ExecutionKind.DATAFLOW_GEN2,
            transport=transport,
        )


class SparkJobCaptureAdapter(FabricCaptureAdapter):
    def __init__(self, transport: FabricCaptureTransport) -> None:
        super().__init__(
            execution_engine=ExecutionEngine.SPARK,
            execution_kind=ExecutionKind.SPARK_JOB_DEFINITION,
            transport=transport,
        )


class FabricAdapterRegistry:
    """Explicit adapter registry; no implicit network/client construction."""

    def __init__(self, adapters: Iterable[FabricCaptureAdapter] = ()) -> None:
        self._by_engine: dict[ExecutionEngine, FabricCaptureAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    @property
    def supported_engines(self) -> frozenset[ExecutionEngine]:
        return frozenset(self._by_engine)

    def register(self, adapter: FabricCaptureAdapter) -> None:
        if adapter.execution_engine in self._by_engine:
            raise ValueError(
                f"Fabric capture adapter already registered for "
                f"{adapter.execution_engine.value}"
            )
        self._by_engine[adapter.execution_engine] = adapter

    def resolve(self, engine: ExecutionEngine) -> FabricCaptureAdapter:
        try:
            return self._by_engine[engine]
        except KeyError as exc:
            raise KeyError(f"no Fabric capture adapter registered for {engine.value}") from exc

    def execute(self, request: FabricCaptureRequest) -> CaptureReceipt:
        return self.resolve(request.execution_engine).execute(request)


__all__ = [
    "CopyActivityCaptureAdapter",
    "CopyJobCaptureAdapter",
    "DataflowGen2CaptureAdapter",
    "FabricAdapterExecutionError",
    "FabricAdapterRegistry",
    "FabricCaptureAdapter",
    "SparkJobCaptureAdapter",
]
