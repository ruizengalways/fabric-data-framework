"""Dataset execution entrypoints and execution backends."""

from .append import AppendExecutionResult, execute_append_batch
from .dataset_runner import DatasetExecutionResult, execute_watermark_scd2
from .full_replace import FullReplaceExecutionResult, execute_full_replace
from .snapshot_diff import SnapshotDiffExecutionResult, execute_snapshot_diff

__all__ = [
    "AppendExecutionResult",
    "DatasetExecutionResult",
    "FullReplaceExecutionResult",
    "SnapshotDiffExecutionResult",
    "execute_append_batch",
    "execute_full_replace",
    "execute_snapshot_diff",
    "execute_watermark_scd2",
]
