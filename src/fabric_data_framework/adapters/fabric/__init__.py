"""Microsoft Fabric physical capture adapters and contracts."""

from .adapter import (
    CopyActivityCaptureAdapter,
    CopyJobCaptureAdapter,
    DataflowGen2CaptureAdapter,
    FabricAdapterExecutionError,
    FabricAdapterRegistry,
    FabricCaptureAdapter,
    SparkJobCaptureAdapter,
)
from .contracts import (
    FabricCaptureRequest,
    FabricCaptureTransport,
    FabricNativeRunEvidence,
    FabricNativeRunStatus,
)

__all__ = [
    "CopyActivityCaptureAdapter",
    "CopyJobCaptureAdapter",
    "DataflowGen2CaptureAdapter",
    "FabricAdapterExecutionError",
    "FabricAdapterRegistry",
    "FabricCaptureAdapter",
    "FabricCaptureRequest",
    "FabricCaptureTransport",
    "FabricNativeRunEvidence",
    "FabricNativeRunStatus",
    "SparkJobCaptureAdapter",
]
