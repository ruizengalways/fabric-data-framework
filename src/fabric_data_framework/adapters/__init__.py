"""Provider-specific physical execution adapters.

Reusable data semantics stay outside this package. Adapters translate provider
invocation/envelope evidence into stable framework contracts.
"""

from .cdc import (
    CDCProviderAdapterRegistry,
    DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY,
    DebeziumKafkaAdapterError,
    DebeziumKafkaBatchResult,
    DebeziumKafkaCDCAdapter,
    DebeziumKafkaPartitionResume,
    DebeziumKafkaRecord,
    DebeziumKafkaResumeGapError,
    DebeziumKafkaResumePlan,
    DebeziumSnapshotReadPolicy,
    normalize_debezium_kafka_batch,
    plan_debezium_kafka_resume,
)
from .fabric import (
    CopyActivityCaptureAdapter,
    CopyJobCaptureAdapter,
    DataflowGen2CaptureAdapter,
    FabricAdapterExecutionError,
    FabricAdapterRegistry,
    FabricCaptureAdapter,
    FabricCaptureRequest,
    FabricCaptureTransport,
    FabricNativeRunEvidence,
    FabricNativeRunStatus,
    SparkJobCaptureAdapter,
)

__all__ = [
    "CDCProviderAdapterRegistry",
    "CopyActivityCaptureAdapter",
    "CopyJobCaptureAdapter",
    "DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY",
    "DataflowGen2CaptureAdapter",
    "DebeziumKafkaAdapterError",
    "DebeziumKafkaBatchResult",
    "DebeziumKafkaCDCAdapter",
    "DebeziumKafkaPartitionResume",
    "DebeziumKafkaRecord",
    "DebeziumKafkaResumeGapError",
    "DebeziumKafkaResumePlan",
    "DebeziumSnapshotReadPolicy",
    "FabricAdapterExecutionError",
    "FabricAdapterRegistry",
    "FabricCaptureAdapter",
    "FabricCaptureRequest",
    "FabricCaptureTransport",
    "FabricNativeRunEvidence",
    "FabricNativeRunStatus",
    "SparkJobCaptureAdapter",
    "normalize_debezium_kafka_batch",
    "plan_debezium_kafka_resume",
]
