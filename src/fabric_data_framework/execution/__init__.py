"""Dataset execution entrypoints and execution backends."""

from .dataset_runner import DatasetExecutionResult, execute_watermark_scd2
from .full_replace import FullReplaceExecutionResult, execute_full_replace

__all__ = [
    "DatasetExecutionResult",
    "FullReplaceExecutionResult",
    "execute_full_replace",
    "execute_watermark_scd2",
]
