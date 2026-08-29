"""Microsoft Fabric physical adapters, REST transports and contracts."""

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
from .pipeline import (
    FabricPipelineBinding,
    FabricPipelineInvocation,
    FabricPipelineTransport,
    FabricRestPipelineTransport,
)
from .rest import (
    FABRIC_API_V1,
    FabricJobInstance,
    FabricJobStart,
    FabricJobStatus,
    FabricRestClient,
    FabricRestError,
)

__all__ = [
    "FABRIC_API_V1",
    "CopyActivityCaptureAdapter",
    "CopyJobCaptureAdapter",
    "DataflowGen2CaptureAdapter",
    "FabricAdapterExecutionError",
    "FabricAdapterRegistry",
    "FabricCaptureAdapter",
    "FabricCaptureRequest",
    "FabricCaptureTransport",
    "FabricJobInstance",
    "FabricJobStart",
    "FabricJobStatus",
    "FabricNativeRunEvidence",
    "FabricNativeRunStatus",
    "FabricPipelineBinding",
    "FabricPipelineInvocation",
    "FabricPipelineTransport",
    "FabricRestClient",
    "FabricRestError",
    "FabricRestPipelineTransport",
    "SparkJobCaptureAdapter",
]
