"""Provider-specific physical execution adapters.

Reusable data semantics stay outside this package. Adapters translate an already
compiled execution unit into provider-specific invocation/evidence contracts.
"""

from .fabric import (
    FabricAdapterExecutionError,
    FabricAdapterRegistry,
    FabricCaptureAdapter,
    FabricCaptureRequest,
    FabricCaptureTransport,
    FabricNativeRunEvidence,
    FabricNativeRunStatus,
)

__all__ = [
    "FabricAdapterExecutionError",
    "FabricAdapterRegistry",
    "FabricCaptureAdapter",
    "FabricCaptureRequest",
    "FabricCaptureTransport",
    "FabricNativeRunEvidence",
    "FabricNativeRunStatus",
]
