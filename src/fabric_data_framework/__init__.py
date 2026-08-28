"""Reusable contracts for the enterprise Microsoft Fabric data framework."""

from .apply.replace import ReplaceGuardPolicy
from .capture.full import FullSnapshotEvidence
from .config import (
    ApplyStrategy,
    CaptureStrategy,
    Criticality,
    DataQualityPolicy,
    DatasetConfig,
    DatasetStatus,
    EffectiveDatasetConfig,
    LoadPolicy,
    OrchestrationPolicy,
    OverrideField,
    PipelineStatus,
    ReconciliationPolicy,
    RunMode,
    RuntimeOverride,
    SourceConfig,
    TargetConfig,
    WatermarkConfig,
    resolve_effective_config,
)
from .contracts.execution_plan import (
    ExecutionKind,
    ExecutionPlan,
    ExecutionRole,
    ExecutionUnit,
    build_default_execution_plan,
)
from .dispatcher import (
    DatasetDispatchOutcome,
    DatasetDispatchRequest,
    OrchestrationIntegrityError,
    PipelineDispatchResult,
    dispatch_datasets,
)
from .execution import execute_full_replace

__all__ = [
    "ApplyStrategy",
    "CaptureStrategy",
    "Criticality",
    "DataQualityPolicy",
    "DatasetConfig",
    "DatasetDispatchOutcome",
    "DatasetDispatchRequest",
    "DatasetStatus",
    "EffectiveDatasetConfig",
    "ExecutionKind",
    "ExecutionPlan",
    "ExecutionRole",
    "ExecutionUnit",
    "FullSnapshotEvidence",
    "LoadPolicy",
    "OrchestrationIntegrityError",
    "OrchestrationPolicy",
    "OverrideField",
    "PipelineDispatchResult",
    "PipelineStatus",
    "ReconciliationPolicy",
    "ReplaceGuardPolicy",
    "RunMode",
    "RuntimeOverride",
    "SourceConfig",
    "TargetConfig",
    "WatermarkConfig",
    "build_default_execution_plan",
    "dispatch_datasets",
    "execute_full_replace",
    "resolve_effective_config",
]

__version__ = "0.4.0"
