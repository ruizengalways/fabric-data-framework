"""Dataset execution entrypoints and execution backends."""

from .append import AppendExecutionResult, execute_append_batch
from .dataset_runner import DatasetExecutionResult, execute_watermark_scd2
from .full_replace import FullReplaceExecutionResult, execute_full_replace
from .pipeline_child import (
    FabricPipelineChildExecutor,
    FabricPipelineChildRequest,
    FabricPipelineChildResult,
    execute_pipeline_child,
    pipeline_child_request_from_parameters,
    validate_pipeline_child_request,
)
from .snapshot_diff import SnapshotDiffExecutionResult, execute_snapshot_diff

__all__ = [
    "AppendExecutionResult",
    "DatasetExecutionResult",
    "FabricPipelineChildExecutor",
    "FabricPipelineChildRequest",
    "FabricPipelineChildResult",
    "FullReplaceExecutionResult",
    "SnapshotDiffExecutionResult",
    "execute_append_batch",
    "execute_full_replace",
    "execute_pipeline_child",
    "execute_snapshot_diff",
    "execute_watermark_scd2",
    "pipeline_child_request_from_parameters",
    "validate_pipeline_child_request",
]
