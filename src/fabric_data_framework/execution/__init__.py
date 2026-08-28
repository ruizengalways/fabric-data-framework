"""Dataset execution entrypoints and execution backends."""

from .dataset_runner import DatasetExecutionResult, execute_watermark_scd2
from .full_replace import FullReplaceExecutionResult, execute_full_replace
from .snapshot_diff import SnapshotDiffExecutionResult, execute_snapshot_diff

__all__ = [
    "DatasetExecutionResult",
    "FullReplaceExecutionResult",
    "SnapshotDiffExecutionResult",
    "execute_full_replace",
    "execute_snapshot_diff",
    "execute_watermark_scd2",
]
