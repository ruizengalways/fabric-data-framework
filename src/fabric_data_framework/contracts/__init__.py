"""Stable provider-neutral contracts."""

from .capture_receipt import CaptureReceipt
from .dispatch import DatasetDispatchOutcome, DatasetDispatchRequest
from .execution_plan import (
    ExecutionKind,
    ExecutionPlan,
    ExecutionRole,
    ExecutionUnit,
    build_default_execution_plan,
    compile_execution_plan,
)
from .rebuild import (
    FullRebuildStateAdapter,
    FullRebuildStateReplacement,
    FullRebuildStateSnapshot,
    RebuildProgressKind,
)
from .recovery import (
    DatasetAttemptLineage,
    ReprocessRequest,
    ReprocessRequestStatus,
    UnknownOutcomeResolution,
)
from .replay import (
    QuarantineBatchEvidence,
    QuarantineReplayPayload,
    QuarantineReplayPayloadProvider,
    QuarantineReplayPlan,
)
from .target_operation import (
    InvalidTargetOperationTransition,
    TargetOperationJournalEntry,
    TargetOperationReconciliation,
    TargetOperationSpec,
    TargetOperationStatus,
    validate_target_operation_transition,
)

__all__ = [
    "CaptureReceipt",
    "DatasetAttemptLineage",
    "DatasetDispatchOutcome",
    "DatasetDispatchRequest",
    "ExecutionKind",
    "ExecutionPlan",
    "ExecutionRole",
    "ExecutionUnit",
    "FullRebuildStateAdapter",
    "FullRebuildStateReplacement",
    "FullRebuildStateSnapshot",
    "InvalidTargetOperationTransition",
    "QuarantineBatchEvidence",
    "QuarantineReplayPayload",
    "QuarantineReplayPayloadProvider",
    "QuarantineReplayPlan",
    "RebuildProgressKind",
    "ReprocessRequest",
    "ReprocessRequestStatus",
    "TargetOperationJournalEntry",
    "TargetOperationReconciliation",
    "TargetOperationSpec",
    "TargetOperationStatus",
    "UnknownOutcomeResolution",
    "build_default_execution_plan",
    "compile_execution_plan",
    "validate_target_operation_transition",
]
