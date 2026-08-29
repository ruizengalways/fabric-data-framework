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
    delta_cdf_checkpoint,
    normalize_delta_cdf_batch,
)
from .registry import (
    CDCProviderAdapterRegistry,
    DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY,
    DebeziumKafkaCDCAdapter,
    DeltaCDFCDCAdapter,
)
from .resume import (
    DebeziumKafkaPartitionResume,
    DebeziumKafkaResumeGapError,
    DebeziumKafkaResumePlan,
    plan_debezium_kafka_resume,
)

__all__ = [
    "CDCProviderAdapterRegistry",
    "DEFAULT_CDC_PROVIDER_ADAPTER_REGISTRY",
    "DELTA_CDF_PROFILE",
    "DebeziumKafkaAdapterError",
    "DebeziumKafkaBatchResult",
    "DebeziumKafkaCDCAdapter",
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
    "delta_cdf_checkpoint",
    "normalize_debezium_kafka_batch",
    "normalize_delta_cdf_batch",
    "plan_debezium_kafka_resume",
]
