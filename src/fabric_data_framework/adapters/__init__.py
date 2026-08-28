"""Provider-specific physical execution adapters.

Reusable data semantics stay outside this package. Adapters translate provider
invocation/envelope evidence into stable framework contracts.
"""

from .cdc import (
    DebeziumKafkaAdapterError,
    DebeziumKafkaBatchResult,
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
    "CopyActivityCaptureAdapter",
    "CopyJobCaptureAdapter",
    "DataflowGen2CaptureAdapter",
    "DebeziumKafkaAdapterError",
    "DebeziumKafkaBatchResult",
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
