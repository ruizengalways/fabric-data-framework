"""Reusable contracts for the enterprise Microsoft Fabric data framework."""

from .apply.replace import ReplaceGuardPolicy
from .apply.scd1 import (
    SCD1ApplyPolicy,
    SCD1ApplyResult,
    SCD1ConflictError,
    SCD1OrderingError,
    StaleRecordAction,
    apply_scd1,
)
from .apply.snapshot_diff import SnapshotDiffPolicy
from .capture.full import FullSnapshotEvidence
from .capture.snapshot import SnapshotEvidence
from .config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    EffectiveDatasetConfig,
    ExecutionEngine,
    ExecutionPolicy,
    ExtensionConfig,
    LoadPolicy,
    OrchestrationPolicy,
    OverrideField,
    PipelineStatus,
    ProgressOwner,
    ReconciliationPolicy,
    RunMode,
    RuntimeOverride,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
    resolve_effective_config,
)
from .contracts import (
    CaptureReceipt,
    ExecutionKind,
    ExecutionPlan,
    ExecutionRole,
    ExecutionUnit,
    build_default_execution_plan,
    compile_execution_plan,
)
from .dispatcher import (
    DatasetDispatchOutcome,
    DatasetDispatchRequest,
    OrchestrationIntegrityError,
    PipelineDispatchResult,
    dispatch_datasets,
)
from .execution import execute_full_replace, execute_snapshot_diff
from .extensions import ExtensionKind, ExtensionRegistry
from .metadata import CapabilityRegistry, UnsupportedExecutionCombination

__all__ = [
    "ApplyStrategy",
    "CapabilityRegistry",
    "CaptureReceipt",
    "CaptureStrategy",
    "Criticality",
    "DataQualityPolicy",
    "DatasetConfig",
    "DatasetDispatchOutcome",
    "DatasetDispatchRequest",
    "DatasetStatus",
    "EffectiveDatasetConfig",
    "ExecutionEngine",
    "ExecutionKind",
    "ExecutionPlan",
    "ExecutionPolicy",
    "ExecutionRole",
    "ExecutionUnit",
    "ExtensionConfig",
    "ExtensionKind",
    "ExtensionRegistry",
    "FullSnapshotEvidence",
    "LoadPolicy",
    "OrchestrationIntegrityError",
    "OrchestrationPolicy",
    "OverrideField",
    "PipelineDispatchResult",
    "PipelineStatus",
    "ProgressOwner",
    "ReconciliationPolicy",
    "ReplaceGuardPolicy",
    "RunMode",
    "RuntimeOverride",
    "SCD1ApplyPolicy",
    "SCD1ApplyResult",
    "SCD1ConflictError",
    "SCD1OrderingError",
    "SnapshotDiffPolicy",
    "SnapshotEvidence",
    "SourceConfig",
    "StaleRecordAction",
    "TargetConfig",
    "UnsupportedExecutionCombination",
    "WatermarkConfig",
    "apply_scd1",
    "build_default_execution_plan",
    "compile_execution_plan",
    "dispatch_datasets",
    "execute_full_replace",
    "execute_snapshot_diff",
    "resolve_effective_config",
]

__version__ = "0.4.0"
