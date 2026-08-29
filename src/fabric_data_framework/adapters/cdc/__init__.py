"""Provider CDC envelope adapters.

Canonical CDC correctness remains in :mod:`fabric_data_framework.capture.cdc`.
"""

from .debezium_kafka import (
    DebeziumKafkaAdapterError,
    DebeziumKafkaBatchResult,
    DebeziumKafkaRecord,
    DebeziumSnapshotReadPolicy,
    normalize_debezium_kafka_batch,
)
from .delta_cdf import (
    DELTA_CDF_PROFILE,
    DeltaCDFAdapterError,
    DeltaCDFBatchResult,
    DeltaCDFChangeType,
    DeltaCDFRecord,
    DeltaCDFResumePlan,
    DeltaCDFRetentionGapError,
    delta_cdf_checkpoint,
    normalize_delta_cdf_batch,
    plan_delta_cdf_resume,
)
from .registry import (
    CDCProviderAdapterRegistry,
    DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY,
    DebeziumKafkaCDCAdapter,
    DeltaCDFCDCAdapter,
)
from .resume import (
    DebeziumKafkaCursorCoordinationPlan,
    DebeziumKafkaPartitionCursorAlignment,
    DebeziumKafkaPartitionResume,
    DebeziumKafkaResumeGapError,
    DebeziumKafkaResumePlan,
    KafkaCursorRelation,
    plan_debezium_kafka_cursor_coordination,
    plan_debezium_kafka_resume,
)

__all__ = [
    "CDCProviderAdapterRegistry",
    "DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY",
    "DELTA_CDF_PROFILE",
    "DebeziumKafkaAdapterError",
    "DebeziumKafkaBatchResult",
    "DebeziumKafkaCDCAdapter",
    "DebeziumKafkaCursorCoordinationPlan",
    "DebeziumKafkaPartitionCursorAlignment",
    "DebeziumKafkaPartitionResume",
    "DebeziumKafkaRecord",
    "DebeziumKafkaResumeGapError",
    "DebeziumKafkaResumePlan",
    "DebeziumSnapshotReadPolicy",
    "DeltaCDFAdapterError",
    "DeltaCDFBatchResult",
    "DeltaCDFCDCAdapter",
    "DeltaCDFChangeType",
    "DeltaCDFRecord",
    "DeltaCDFResumePlan",
    "DeltaCDFRetentionGapError",
    "KafkaCursorRelation",
    "delta_cdf_checkpoint",
    "normalize_debezium_kafka_batch",
    "normalize_delta_cdf_batch",
    "plan_debezium_kafka_cursor_coordination",
    "plan_debezium_kafka_resume",
    "plan_delta_cdf_resume",
]
